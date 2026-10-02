-- Apply in a dedicated Supabase project using its SQL Editor or server connection.
-- No app passwords are stored here: Supabase Auth handles them.

begin;

create table if not exists public.pace_profiles (
    user_id uuid primary key references auth.users(id) on delete cascade,
    username text not null unique check (username ~ '^[a-z0-9][a-z0-9_.-]{2,31}$'),
    created_at timestamptz not null default now()
);
create table if not exists public.pace_garmin_connections (
    user_id uuid primary key references public.pace_profiles(user_id) on delete cascade,
    credentials_ciphertext text not null,
    session_ciphertext text,
    revision uuid not null default gen_random_uuid(),
    updated_at timestamptz not null default now()
);
create table if not exists public.pace_sync_jobs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.pace_profiles(user_id) on delete cascade,
    credentials_revision uuid not null,
    status text not null default 'running' check (status in ('running','finalizing','complete','failed')),
    next_offset integer not null default 0 check (next_offset >= 0),
    lease_owner uuid,
    lease_expires_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (id, user_id)
);
create unique index if not exists pace_one_active_sync
    on public.pace_sync_jobs(user_id) where status in ('running','finalizing');
create table if not exists public.pace_import_batches (
    job_id uuid not null,
    user_id uuid not null,
    start_offset integer not null,
    records jsonb not null check (jsonb_typeof(records) = 'array'),
    primary key (job_id, start_offset),
    foreign key (job_id, user_id) references public.pace_sync_jobs(id, user_id) on delete cascade
);
create table if not exists public.pace_snapshots (
    user_id uuid primary key references public.pace_profiles(user_id) on delete cascade,
    job_id uuid not null,
    payload jsonb not null,
    updated_at timestamptz not null default now(),
    foreign key (job_id, user_id) references public.pace_sync_jobs(id, user_id)
);
create table if not exists public.pace_auth_attempts (
    fingerprint text not null,
    kind text not null check (kind in ('login','signup')),
    window_start timestamptz not null default now(),
    attempts integer not null default 1,
    primary key (fingerprint, kind)
);

-- Defense in depth: browsers cannot access any of these tables or RPCs.
-- Every server query also binds a Supabase-verified user ID.
alter table public.pace_profiles enable row level security;
alter table public.pace_garmin_connections enable row level security;
alter table public.pace_sync_jobs enable row level security;
alter table public.pace_import_batches enable row level security;
alter table public.pace_snapshots enable row level security;
alter table public.pace_auth_attempts enable row level security;
revoke all on public.pace_profiles, public.pace_garmin_connections,
    public.pace_sync_jobs, public.pace_import_batches, public.pace_snapshots,
    public.pace_auth_attempts from anon, authenticated;
grant all on public.pace_profiles, public.pace_garmin_connections,
    public.pace_sync_jobs, public.pace_import_batches, public.pace_snapshots,
    public.pace_auth_attempts to service_role;

create or replace function public.pace_auth_attempt(p_fingerprint text, p_kind text)
returns boolean language plpgsql set search_path = '' as $$
declare attempt public.pace_auth_attempts; window_length interval;
begin
    window_length := case when p_kind = 'signup' then interval '1 hour' else interval '5 minutes' end;
    insert into public.pace_auth_attempts(fingerprint, kind) values (p_fingerprint, p_kind)
    on conflict (fingerprint, kind) do update set
        attempts = case when pace_auth_attempts.window_start < now() - window_length then 1 else pace_auth_attempts.attempts + 1 end,
        window_start = case when pace_auth_attempts.window_start < now() - window_length then now() else pace_auth_attempts.window_start end
    returning * into attempt;
    delete from public.pace_auth_attempts where window_start < now() - interval '1 day';
    return attempt.attempts <= case when p_kind = 'signup' then 10 else 30 end;
end $$;

create or replace function public.pace_create_profile(p_user uuid, p_username text, p_credentials text)
returns void language plpgsql set search_path = '' as $$
begin
    insert into public.pace_profiles(user_id, username) values (p_user, p_username);
    insert into public.pace_garmin_connections(user_id, credentials_ciphertext) values (p_user, p_credentials);
end $$;

create or replace function public.pace_update_garmin(p_user uuid, p_credentials text)
returns void language plpgsql set search_path = '' as $$
begin
    perform 1 from public.pace_garmin_connections where user_id = p_user for update;
    update public.pace_garmin_connections set credentials_ciphertext = p_credentials,
        session_ciphertext = null, revision = gen_random_uuid(), updated_at = now() where user_id = p_user;
    delete from public.pace_snapshots where user_id = p_user;
    delete from public.pace_sync_jobs where user_id = p_user;
end $$;

create or replace function public.pace_save_session(p_user uuid, p_session text)
returns void language plpgsql set search_path = '' as $$
begin
    update public.pace_garmin_connections set session_ciphertext = p_session, updated_at = now() where user_id = p_user;
end $$;

create or replace function public.pace_begin_sync(p_user uuid, p_revision uuid)
returns jsonb language plpgsql set search_path = '' as $$
declare job public.pace_sync_jobs; revision uuid;
begin
    select c.revision into revision from public.pace_garmin_connections c where user_id = p_user for update;
    if revision is distinct from p_revision then raise exception 'connection_changed'; end if;
    select * into job from public.pace_sync_jobs where user_id = p_user and status in ('running','finalizing');
    if found then return to_jsonb(job); end if;
    if exists (select 1 from public.pace_snapshots where user_id = p_user and updated_at > now() - interval '1 minute') then
        raise exception 'refresh_cooldown';
    end if;
    insert into public.pace_sync_jobs(user_id, credentials_revision) values (p_user, p_revision) returning * into job;
    return to_jsonb(job);
end $$;

create or replace function public.pace_claim_sync(p_user uuid, p_job uuid, p_worker uuid)
returns jsonb language plpgsql set search_path = '' as $$
declare job public.pace_sync_jobs;
begin
    select * into job from public.pace_sync_jobs where id = p_job and user_id = p_user for update;
    if not found or job.status = 'failed' then raise exception 'sync_not_found'; end if;
    if job.status = 'complete' then return to_jsonb(job); end if;
    if job.lease_expires_at > now() then return null; end if;
    update public.pace_sync_jobs set lease_owner = p_worker, lease_expires_at = now() + interval '90 seconds',
        updated_at = now() where id = p_job returning * into job;
    return to_jsonb(job);
end $$;

create or replace function public.pace_append_sync(p_user uuid, p_job uuid, p_worker uuid,
    p_offset integer, p_records jsonb, p_session text)
returns jsonb language plpgsql set search_path = '' as $$
declare job public.pace_sync_jobs;
begin
    -- Always lock connection before job, matching credential updates and finalization.
    perform 1 from public.pace_garmin_connections where user_id = p_user for update;
    select * into job from public.pace_sync_jobs where id = p_job and user_id = p_user for update;
    if not found or job.status <> 'running' or job.lease_owner is distinct from p_worker
       or job.lease_expires_at <= now() or job.next_offset <> p_offset
       or not exists (select 1 from public.pace_garmin_connections where user_id = p_user and revision = job.credentials_revision)
    then raise exception 'sync_changed'; end if;
    if jsonb_array_length(p_records) > 0 then
        insert into public.pace_import_batches(job_id, user_id, start_offset, records)
            values (p_job, p_user, p_offset, p_records);
    end if;
    update public.pace_garmin_connections set session_ciphertext = p_session where user_id = p_user;
    update public.pace_sync_jobs set next_offset = next_offset + jsonb_array_length(p_records),
        status = case when jsonb_array_length(p_records) = 0 then 'finalizing' else 'running' end,
        lease_owner = null, lease_expires_at = null, updated_at = now()
        where id = p_job returning * into job;
    return to_jsonb(job);
end $$;

create or replace function public.pace_finish_sync(p_user uuid, p_job uuid, p_worker uuid, p_payload jsonb)
returns void language plpgsql set search_path = '' as $$
declare job public.pace_sync_jobs; record_count bigint;
begin
    perform 1 from public.pace_garmin_connections where user_id = p_user for update;
    select * into job from public.pace_sync_jobs where id = p_job and user_id = p_user for update;
    if not found or job.status <> 'finalizing' or job.lease_owner is distinct from p_worker
       or job.lease_expires_at <= now()
       or not exists (select 1 from public.pace_garmin_connections where user_id = p_user and revision = job.credentials_revision)
    then raise exception 'sync_changed'; end if;
    select coalesce(sum(jsonb_array_length(records)), 0) into record_count from public.pace_import_batches where job_id = p_job and user_id = p_user;
    if record_count <> job.next_offset or record_count <> (p_payload->'meta'->>'activity_count_fetched')::bigint then
        raise exception 'incomplete_history';
    end if;
    insert into public.pace_snapshots(user_id, job_id, payload) values (p_user, p_job, p_payload)
    on conflict (user_id) do update set job_id = excluded.job_id, payload = excluded.payload, updated_at = now();
    update public.pace_sync_jobs set status = 'complete', lease_owner = null, lease_expires_at = null,
        updated_at = now() where id = p_job;
    delete from public.pace_sync_jobs where user_id = p_user and id <> p_job;
end $$;

create or replace function public.pace_release_sync(p_user uuid, p_job uuid, p_worker uuid)
returns void language sql set search_path = '' as $$
    update public.pace_sync_jobs set lease_owner = null, lease_expires_at = null
    where id = p_job and user_id = p_user and lease_owner = p_worker;
$$;

-- RPCs default to executable by PUBLIC; explicitly close that path.
revoke execute on function public.pace_auth_attempt(text,text),
    public.pace_create_profile(uuid,text,text), public.pace_update_garmin(uuid,text),
    public.pace_save_session(uuid,text), public.pace_begin_sync(uuid,uuid),
    public.pace_claim_sync(uuid,uuid,uuid), public.pace_append_sync(uuid,uuid,uuid,integer,jsonb,text),
    public.pace_finish_sync(uuid,uuid,uuid,jsonb), public.pace_release_sync(uuid,uuid,uuid)
    from public, anon, authenticated;
grant execute on function public.pace_auth_attempt(text,text),
    public.pace_create_profile(uuid,text,text), public.pace_update_garmin(uuid,text),
    public.pace_save_session(uuid,text), public.pace_begin_sync(uuid,uuid),
    public.pace_claim_sync(uuid,uuid,uuid), public.pace_append_sync(uuid,uuid,uuid,integer,jsonb,text),
    public.pace_finish_sync(uuid,uuid,uuid,jsonb), public.pace_release_sync(uuid,uuid,uuid)
    to service_role;

-- Publish the completed schema to the Data API after the transaction commits.
notify pgrst, 'reload schema';
commit;

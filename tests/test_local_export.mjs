import test from "node:test";
import assert from "node:assert/strict";
import { parseLocalExport } from "../viz/local-export.mjs";

test("accepts a generated activity export", () => {
  const payload = { activities: [{ date: "2026-10-03", distance_km: 5 }], meta: { generated_at: "2026-10-03T00:00:00Z" } };
  assert.deepEqual(parseLocalExport(JSON.stringify(payload)), payload);
});

test("rejects malformed JSON and unrelated files with recovery guidance", () => {
  assert.throws(() => parseLocalExport("{"), /not valid JSON/);
  assert.throws(() => parseLocalExport("null"), /does not contain Garmin activities/);
  assert.throws(() => parseLocalExport('{"activities": {}}'), /does not contain Garmin activities/);
});

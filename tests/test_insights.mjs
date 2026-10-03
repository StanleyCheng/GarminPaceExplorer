import test from "node:test";
import assert from "node:assert/strict";
import { INSIGHTS, buildInsight, median, prepareActivities, selectActivities, summaryFor } from "../viz/insights.mjs";

const record = (date, distance_km, pace_s_per_km, extra = {}) => ({
  date, distance_km, pace_s_per_km, duration_s: distance_km * pace_s_per_km,
  avg_hr: 145, elevation_m: 15, vo2max: 52, activity_type: "running", ...extra,
});
const state = (insight, extra = {}) => ({ year: 2026, startMonth: 1, endMonth: 12,
  activityType: "run", distanceBucket: "all", weeklyUnit: "distance",
  bestDistance: "5", insight, ...extra });
const today = new Date("2026-10-03T12:00:00Z");

test("preparation rejects malformed dates without crashing", () => {
  const activities = prepareActivities([
    record("2026-01-01", 5, 300), record("2026-13-01", 5, 300),
    record("2026-02-30", 5, 300), record("bad", 5, 300),
  ]);
  assert.equal(activities.length, 1);
  assert.equal(activities[0].activity_class, "run");
});

test("period average weights activities and the new pace cutoff applies to old snapshots", () => {
  const activities = prepareActivities([
    record("2026-01-02", 5, 180, { avg_hr: null }),
    record("2026-02-02", 5, 300),
    record("2026-02-03", 5, 1200),
    record("2026-02-04", 5, 1201),
  ]);
  const summary = summaryFor(activities);
  assert.equal(summary.activityCount, 3);
  assert.equal(summary.totalDistance, 15);
  assert.equal(summary.averagePace, 560);
  assert.equal(median([180, 300, 1200]), 300);
});

test("activity and distance filters apply before every view", () => {
  const activities = prepareActivities([
    record("2026-01-02", 4, 300), record("2026-01-03", 8, 330),
    record("2026-01-04", 8, 900, { activity_type: "hiking" }),
    record("2025-01-04", 8, 330),
  ]);
  assert.equal(selectActivities(activities, state("volume", { distanceBucket: "5-10" })).length, 1);
  assert.equal(selectActivities(activities, state("volume", { activityType: "all", distanceBucket: "5-10" })).length, 2);
});

test("all ten views produce a chart and keep counts consistent", () => {
  const activities = prepareActivities([
    record("2024-01-02", 5, 320), record("2025-01-02", 5, 310),
    record("2026-01-02", 5, 300), record("2026-01-09", 10, 330),
    record("2026-02-02", 21, 390),
  ]);
  assert.equal(INSIGHTS.length, 10);
  for (const view of INSIGHTS) {
    const result = buildInsight(activities, state(view.id), { today });
    assert.ok(result.traces.length > 0, `${view.id} should have a trace`);
    assert.ok(result.layout, `${view.id} should have a layout`);
    assert.equal(result.summary.activityCount, 3);
    assert.equal(result.rows.length, 12);
  }
});

test("weekly volume includes empty weeks and changes unit", () => {
  const activities = prepareActivities([record("2026-01-02", 5, 300), record("2026-01-30", 10, 300)]);
  const distance = buildInsight(activities, state("volume", { endMonth: 1 }), { today });
  assert.ok(distance.traces[0].y.includes(0));
  const hours = buildInsight(activities, state("volume", { endMonth: 1, weeklyUnit: "hours" }), { today });
  assert.ok(Math.abs(hours.traces[0].y.reduce((a, b) => a + b, 0) - 1.2) < 1e-9);
});

test("year comparison truncates previous years at the same current calendar day", () => {
  const activities = prepareActivities([
    record("2025-10-02", 5, 300), record("2025-10-04", 7, 300),
    record("2026-10-02", 6, 300),
  ]);
  const result = buildInsight(activities, state("compare"), { today });
  const priorDistance = result.traces.find((trace) => trace.name === "2025" && trace.yaxis === "y2");
  assert.equal(priorDistance.y[9], 5);
});

test("best view uses whole running activities near the target distance", () => {
  const activities = prepareActivities([
    record("2026-01-02", 5, 300), record("2026-02-02", 5.1, 290),
    record("2026-03-02", 6, 250),
    record("2026-04-02", 5, 400, { activity_type: "walking" }),
  ]);
  const result = buildInsight(activities, state("best", { activityType: "all" }), { today });
  assert.equal(result.traces[0].y.length, 2);
  assert.deepEqual(result.traces[1].y, [25, 24.65]);
});

test("missing HR only removes a point from the effort view", () => {
  const activities = prepareActivities([record("2026-01-02", 5, 300, { avg_hr: null })]);
  assert.equal(buildInsight(activities, state("effort"), { today }).traces.length, 0);
  assert.equal(buildInsight(activities, state("volume"), { today }).summary.totalDistance, 5);
});

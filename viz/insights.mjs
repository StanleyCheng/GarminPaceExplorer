// Pure activity calculations and chart specifications. No account or DOM state lives here.
export const MIN_PACE_SECONDS = 180;
export const MAX_PACE_SECONDS = 1200;
export const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
export const INSIGHTS = [
  { id: "volume", label: "Volume", title: "Weekly training volume", description: "Distance or hours each week, with a four-week average and session counts." },
  { id: "pace", label: "Pace", title: "Comparable-run pace", description: "Individual paces and a 28-day median. Choose a distance range for a fairer comparison." },
  { id: "compare", label: "Years", title: "Year-over-year progress", description: "Monthly pace and cumulative distance against the two previous years." },
  { id: "effort", label: "Effort", title: "Pace and heart rate", description: "See the pace of runs at similar average heart rates. Terrain and conditions also matter." },
  { id: "calendar", label: "Calendar", title: "Activity calendar", description: "Daily distance reveals training rhythm and gaps." },
  { id: "endurance", label: "Long runs", title: "Long-run progression", description: "The longest activity each week and the mix of short, medium, and long sessions." },
  { id: "vo2max", label: "VO₂ max", title: "VO₂ max estimate", description: "Monthly median of Garmin's recorded estimate, with unavailable months left blank." },
  { id: "distribution", label: "Spread", title: "Pace distribution", description: "Median and variation within each month, beyond a single average." },
  { id: "climbing", label: "Climbing", title: "Climbing and pace", description: "Weekly elevation gain and the pace of hillier activities." },
  { id: "best", label: "Best", title: "Best recorded whole activities", description: "Recorded duration of runs near a chosen distance, and the best so far." },
];

const DAY_MS = 86_400_000;
const BLUE = "#4472c4";
const GREEN = "#217346";
const NAVY = "#1f4e78";
const LIGHT_BLUE = "#a9c4e5";
const MUTED = "#5d6f7e";

const finite = (value) => typeof value === "number" && Number.isFinite(value);
const sum = (values) => values.reduce((total, value) => total + value, 0);
const mean = (values) => values.length ? sum(values) / values.length : null;
const round = (value, digits = 1) => Number(value.toFixed(digits));
const isoDate = (date) => date.toISOString().slice(0, 10);
const asDate = (value) => new Date(`${value}T00:00:00Z`);
const addDays = (value, days) => isoDate(new Date(asDate(value).getTime() + days * DAY_MS));
const validPace = (activity) => finite(activity.pace_s_per_km)
  && activity.pace_s_per_km >= MIN_PACE_SECONDS && activity.pace_s_per_km <= MAX_PACE_SECONDS;

export function formatPace(value) {
  if (!finite(value)) return "—";
  const seconds = Math.round(value);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

export function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

export function activityClass(type) {
  const key = String(type || "").toLowerCase();
  if (key.includes("run")) return "run";
  if (key.includes("hik")) return "hike";
  if (key.includes("walk")) return "walk";
  return "other";
}

export function prepareActivities(records) {
  return records.filter((record) => {
    if (!record || typeof record !== "object" || typeof record.date !== "string") return false;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(record.date) || !finite(record.distance_km)
        || !validPace(record)) return false;
    const date = asDate(record.date);
    return Number.isFinite(date.getTime()) && isoDate(date) === record.date;
  }).map((record) => ({ ...record, year: Number(record.date.slice(0, 4)),
    month: Number(record.date.slice(5, 7)), activity_class: activityClass(record.activity_type) }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

function inDistanceRange(distance, bucket) {
  if (bucket === "all") return true;
  const ranges = { "<3": [0, 3], "3-5": [3, 5], "5-10": [5, 10],
    "10-15": [10, 15], "15-25": [15, 25], "25-40": [25, 40], "40+": [40, Infinity] };
  const [lower, upper] = ranges[bucket] || [0, Infinity];
  return distance >= lower && distance < upper;
}

export function selectActivities(activities, state, includeYear = true) {
  return activities.filter((activity) => (!includeYear || activity.year === Number(state.year))
    && activity.month >= state.startMonth && activity.month <= state.endMonth
    && (state.activityType === "all" || activity.activity_class === state.activityType)
    && inDistanceRange(activity.distance_km, state.distanceBucket));
}

export function summaryFor(activities) {
  const paces = activities.filter(validPace).map((activity) => activity.pace_s_per_km);
  return { activityCount: activities.length, averagePace: mean(paces),
    totalDistance: sum(activities.map((activity) => activity.distance_km)),
    activeDays: new Set(activities.map((activity) => activity.date)).size,
    monthsPlotted: new Set(activities.filter(validPace).map((activity) => activity.month)).size };
}

export function monthlyRows(activities, state) {
  return MONTH_NAMES.map((name, index) => {
    const month = index + 1;
    const selected = month >= state.startMonth && month <= state.endMonth;
    const records = selected ? activities.filter((activity) => activity.month === month) : [];
    return { name, selected, pace: mean(records.filter(validPace).map((activity) => activity.pace_s_per_km)),
      distance: sum(records.map((activity) => activity.distance_km)), count: records.length };
  });
}

function periodBounds(state, today) {
  const year = Number(state.year);
  const first = `${year}-${String(state.startMonth).padStart(2, "0")}-01`;
  const finalDay = new Date(Date.UTC(year, state.endMonth, 0));
  const last = isoDate(finalDay);
  const current = isoDate(today);
  return [first, year === today.getFullYear() && current < last ? current : last];
}

function weekStart(value) {
  const date = asDate(value);
  const day = (date.getUTCDay() + 6) % 7;
  return addDays(value, -day);
}

function weeklyGroups(activities, state, today) {
  const [first, last] = periodBounds(state, today);
  if (last < first) return [];
  const grouped = new Map();
  for (const activity of activities) {
    const key = weekStart(activity.date);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(activity);
  }
  const weeks = [];
  for (let key = weekStart(first); key <= last; key = addDays(key, 7)) {
    weeks.push({ date: key, activities: grouped.get(key) || [] });
  }
  return weeks;
}

function paceAxis(paces, domain) {
  const values = paces.filter(finite);
  const minimum = values.length ? Math.max(MIN_PACE_SECONDS, Math.min(...values) - 25) : MIN_PACE_SECONDS;
  const maximum = values.length ? Math.min(MAX_PACE_SECONDS, Math.max(...values) + 25) : 600;
  const tickStart = Math.ceil(minimum / 60) * 60;
  const ticks = [];
  for (let tick = tickStart; tick <= maximum; tick += 60) ticks.push(tick);
  return { title: { text: "min/km", font: { size: 11 } }, range: [maximum, minimum],
    tickvals: ticks, ticktext: ticks.map(formatPace), gridcolor: "#e4eaf0",
    zeroline: false, ...(domain ? { domain } : {}) };
}

function baseLayout(narrow) {
  return { autosize: true, paper_bgcolor: "#ffffff", plot_bgcolor: "#ffffff",
    font: { family: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', color: MUTED, size: 11 },
    margin: narrow ? { l: 48, r: 15, t: 24, b: 42 } : { l: 60, r: 26, t: 34, b: 52 },
    hovermode: "closest", showlegend: false, dragmode: false,
    xaxis: { gridcolor: "#edf1f5", zeroline: false },
    yaxis: { gridcolor: "#e4eaf0", zeroline: false } };
}

function noData(message, narrow) {
  return { traces: [], layout: { ...baseLayout(narrow), annotations: [{ text: message,
    x: 0.5, y: 0.5, xref: "paper", yref: "paper", showarrow: false,
    font: { size: 14, color: MUTED } }] }, note: message };
}

function volumeInsight(activities, state, today, narrow) {
  const weeks = weeklyGroups(activities, state, today);
  const hours = state.weeklyUnit === "hours";
  const values = weeks.map((week) => sum(week.activities.map((activity) => hours ?
    (finite(activity.duration_s) ? activity.duration_s / 3600 : 0) : activity.distance_km)));
  const average = values.map((_, index) => round(mean(values.slice(Math.max(0, index - 3), index + 1)), 1));
  const counts = weeks.map((week) => week.activities.length);
  return { traces: [
    { type: "bar", name: hours ? "Weekly hours" : "Weekly kilometres",
      x: weeks.map((week) => week.date), y: values.map((v) => round(v, 1)),
      customdata: counts, marker: { color: LIGHT_BLUE },
      hovertemplate: `Week of %{x}<br>%{y:.1f} ${hours ? "h" : "km"}<br>%{customdata} activities<extra></extra>` },
    { type: "scatter", mode: "lines", x: weeks.map((week) => week.date), y: average,
      line: { color: GREEN, width: 3 }, name: "Four-week average",
      hovertemplate: `Four-week average: %{y:.1f} ${hours ? "h" : "km"}<extra></extra>` },
  ], layout: { ...baseLayout(narrow), yaxis: { title: hours ? "Hours" : "Kilometres", rangemode: "tozero" },
    showlegend: true, legend: { orientation: "h", y: 1.12, x: 0 } },
  note: "Each bar is one Monday–Sunday week, including weeks with no activities. The green line averages four weeks." };
}

function comparablePaceInsight(activities, narrow) {
  const records = activities.filter(validPace);
  if (!records.length) return noData("No valid pace activities match these filters.", narrow);
  const rolling = records.map((activity) => {
    const start = addDays(activity.date, -27);
    const window = records.filter((entry) => entry.date >= start && entry.date <= activity.date);
    return window.length >= 2 ? median(window.map((entry) => entry.pace_s_per_km)) : null;
  });
  return { traces: [
    { type: "scatter", mode: "markers", name: "Activities", x: records.map((a) => a.date),
      y: records.map((a) => a.pace_s_per_km),
      customdata: records.map((a) => [formatPace(a.pace_s_per_km), round(a.distance_km, 2)]),
      marker: { color: LIGHT_BLUE, size: 7, opacity: 0.8 },
      hovertemplate: "%{x}<br>%{customdata[0]} /km · %{customdata[1]} km<extra></extra>" },
    { type: "scatter", mode: "lines", name: "28-day median", x: records.map((a) => a.date),
      y: rolling, customdata: rolling.map(formatPace), line: { color: BLUE, width: 3 }, connectgaps: false,
      hovertemplate: "28-day median: %{customdata} /km<extra></extra>" },
  ], layout: { ...baseLayout(narrow), yaxis: paceAxis(records.map((a) => a.pace_s_per_km)),
    showlegend: true, legend: { orientation: "h", y: 1.12 } },
  note: "Lower pace is faster. The line needs at least two activities within 28 days; choose a distance range to compare like with like." };
}

function comparisonInsight(allActivities, state, today, narrow) {
  const endYear = Number(state.year);
  const years = [endYear - 2, endYear - 1, endYear];
  const colors = [LIGHT_BLUE, GREEN, BLUE];
  const isCurrent = endYear === today.getFullYear();
  const currentMonth = today.getMonth() + 1;
  const currentDay = today.getDate();
  const traces = [];
  years.forEach((year, index) => {
    const records = selectActivities(allActivities, { ...state, year });
    const monthly = MONTH_NAMES.map((_, monthIndex) => {
      const month = monthIndex + 1;
      if (isCurrent && month > currentMonth) return [];
      return records.filter((activity) => activity.month === month
        && (!isCurrent || month < currentMonth || Number(activity.date.slice(8)) <= currentDay));
    });
    if (!monthly.some((items) => items.length)) return;
    const paces = monthly.map((items) => mean(items.filter(validPace).map((item) => item.pace_s_per_km)));
    let cumulative = 0;
    const totals = monthly.map((items, monthIndex) => {
      if (monthIndex + 1 < state.startMonth || monthIndex + 1 > state.endMonth
          || (isCurrent && monthIndex + 1 > currentMonth)) return null;
      cumulative += sum(items.map((item) => item.distance_km));
      return round(cumulative);
    });
    const months = MONTH_NAMES.map((_, i) => i + 1);
    traces.push({ type: "scatter", mode: "lines+markers", name: String(year), x: months, y: paces,
      customdata: paces.map(formatPace),
      xaxis: "x", yaxis: "y", line: { color: colors[index], width: 2.5 },
      hovertemplate: `${year} · month %{x}<br>%{customdata} /km<extra></extra>` });
    traces.push({ type: "scatter", mode: "lines", name: String(year), x: months, y: totals,
      xaxis: "x2", yaxis: "y2", line: { color: colors[index], width: 2.5 },
      showlegend: false, hovertemplate: `${year} · month %{x}<br>%{y:.1f} km accumulated<extra></extra>` });
  });
  if (!traces.length) return noData("No activities in this year or the previous two years.", narrow);
  const paceValues = traces.filter((_, index) => index % 2 === 0).flatMap((trace) => trace.y);
  return { traces, layout: { ...baseLayout(narrow), showlegend: true,
    legend: { orientation: "h", y: 1.1 }, hovermode: "x unified",
    xaxis: { domain: [0, 1], anchor: "y", tickvals: [1, 3, 5, 7, 9, 11], ticktext: ["Jan", "Mar", "May", "Jul", "Sep", "Nov"], showticklabels: false },
    yaxis: paceAxis(paceValues, [0.57, 1]),
    xaxis2: { domain: [0, 1], anchor: "y2", tickvals: [1, 3, 5, 7, 9, 11], ticktext: ["Jan", "Mar", "May", "Jul", "Sep", "Nov"] },
    yaxis2: { domain: [0, 0.39], title: "km", rangemode: "tozero", gridcolor: "#e4eaf0" },
    margin: narrow ? { l: 48, r: 10, t: 30, b: 38 } : { l: 60, r: 26, t: 38, b: 45 } },
  note: "Top: monthly average pace (lower is faster). Bottom: cumulative distance from the selected start month. For the current year, prior years stop at the same calendar day." };
}

function effortInsight(activities, narrow) {
  const records = activities.filter((activity) => validPace(activity) && finite(activity.avg_hr)
    && activity.avg_hr >= 30 && activity.avg_hr <= 230);
  if (!records.length) return noData("No activities with both valid pace and heart rate match these filters.", narrow);
  return { traces: [{ type: "scatter", mode: "markers", x: records.map((a) => a.avg_hr),
    y: records.map((a) => a.pace_s_per_km),
    customdata: records.map((a) => [a.date, round(a.distance_km, 2), formatPace(a.pace_s_per_km)]),
    marker: { color: records.map((a, index) => index), colorscale: [[0, LIGHT_BLUE], [1, NAVY]],
      showscale: false, size: 8, opacity: 0.78 },
    hovertemplate: "%{customdata[0]}<br>%{x} bpm · %{customdata[2]} /km<br>%{customdata[1]} km<extra></extra>" }],
    layout: { ...baseLayout(narrow), xaxis: { title: "Average heart rate (bpm)" },
      yaxis: paceAxis(records.map((a) => a.pace_s_per_km)) },
    note: `${records.length} activities have both metrics. Lighter points are earlier; darker points are later. Average heart rate is an effort indicator, not a controlled comparison.` };
}

function calendarInsight(activities, state, today, narrow) {
  const [first, last] = periodBounds(state, today);
  if (last < first) return noData("This period has not started yet.", narrow);
  const starts = [];
  for (let value = weekStart(first); value <= last; value = addDays(value, 7)) starts.push(value);
  const byDate = new Map();
  for (const activity of activities) byDate.set(activity.date,
    (byDate.get(activity.date) || 0) + activity.distance_km);
  const dates = Array.from({ length: 7 }, (_, day) => starts.map((start) => addDays(start, day)));
  const z = dates.map((row) => row.map((date) => date >= first && date <= last ? round(byDate.get(date) || 0) : null));
  const activeDays = [...byDate.values()].filter((distance) => distance > 0).length;
  return { traces: [{ type: "heatmap", x: starts.map((_, i) => i),
    y: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], z, customdata: dates,
    colorscale: [[0, "#edf4fa"], [0.25, "#b9d8e4"], [0.6, "#78bfa2"], [1, GREEN]],
    zmin: 0, showscale: false, xgap: 2, ygap: 2,
    hovertemplate: "%{customdata}<br>%{z:.1f} km<extra></extra>" }],
    layout: { ...baseLayout(narrow), margin: { l: 42, r: 14, t: 22, b: 35 },
      xaxis: { tickmode: "array", tickvals: starts.map((_, i) => i).filter((i) => i % 4 === 0),
        ticktext: starts.filter((_, i) => i % 4 === 0).map((date) => date.slice(5)), fixedrange: true, showgrid: false },
      yaxis: { autorange: "reversed", fixedrange: true, showgrid: false } },
    note: `${activeDays} active days in this selection. Swipe the calendar horizontally for later weeks. Blank cells fall outside the selected period; pale cells are days with no activity.`,
    minWidth: 840 };
}

function enduranceInsight(activities, state, today, narrow) {
  const weeks = weeklyGroups(activities, state, today);
  const x = weeks.map((week) => week.date);
  const groups = [
    { name: "Under 5 km", color: LIGHT_BLUE, lower: 0, upper: 5 },
    { name: "5–15 km", color: BLUE, lower: 5, upper: 15 },
    { name: "15 km or more", color: GREEN, lower: 15, upper: Infinity },
  ];
  const traces = [{ type: "scatter", mode: "lines+markers", name: "Longest session", x,
    y: weeks.map((week) => week.activities.length ? Math.max(...week.activities.map((a) => a.distance_km)) : null),
    xaxis: "x", yaxis: "y", line: { color: NAVY, width: 2.5 }, connectgaps: false,
    hovertemplate: "Week of %{x}<br>Longest: %{y:.1f} km<extra></extra>" }];
  groups.forEach((group) => traces.push({ type: "bar", name: group.name, x, xaxis: "x2", yaxis: "y2",
    y: weeks.map((week) => week.activities.filter((a) => a.distance_km >= group.lower && a.distance_km < group.upper).length),
    marker: { color: group.color }, hovertemplate: `${group.name}<br>Week of %{x}: %{y} activities<extra></extra>` }));
  return { traces, layout: { ...baseLayout(narrow), barmode: "stack", showlegend: true,
    legend: { orientation: "h", y: 1.13 },
    xaxis: { domain: [0, 1], anchor: "y", showticklabels: false },
    yaxis: { domain: [0.56, 1], title: "Longest km", rangemode: "tozero" },
    xaxis2: { domain: [0, 1], anchor: "y2" },
    yaxis2: { domain: [0, 0.38], title: "Sessions", rangemode: "tozero" } },
    note: "Top: longest single activity per week. Bottom: session counts by distance. Empty weeks remain visible." };
}

function vo2Insight(activities, state, narrow) {
  const months = MONTH_NAMES.map((_, index) => index + 1);
  const values = months.map((month) => median(activities.filter((activity) => activity.month === month
    && finite(activity.vo2max) && activity.vo2max > 0).map((activity) => activity.vo2max)));
  if (!values.some(finite)) return noData("No Garmin VO₂ max estimates match this selection.", narrow);
  return { traces: [{ type: "scatter", mode: "lines+markers", x: months, y: values,
    line: { color: BLUE, width: 3 }, marker: { size: 8 }, connectgaps: false,
    hovertemplate: "Month %{x}<br>Median estimate: %{y:.1f}<extra></extra>" }],
    layout: { ...baseLayout(narrow), xaxis: { tickvals: months, ticktext: MONTH_NAMES.map((month) => month.slice(0, 3)) },
      yaxis: { title: "ml/kg/min", gridcolor: "#e4eaf0" } },
    note: "Garmin's estimated VO₂ max, summarized by monthly median. Gaps mean no estimate was recorded." };
}

function distributionInsight(activities, narrow) {
  const months = MONTH_NAMES.map((month) => month.slice(0, 3));
  const traces = months.map((month, index) => ({ type: "box", name: month,
    y: activities.filter((activity) => activity.month === index + 1 && validPace(activity))
      .map((activity) => activity.pace_s_per_km),
    marker: { color: BLUE, size: 5 }, line: { color: NAVY }, boxpoints: "outliers", showlegend: false,
    hovertemplate: `${month}<br>%{y:.0f} s/km<extra></extra>` })).filter((trace) => trace.y.length);
  if (!traces.length) return noData("No pace activities match this selection.", narrow);
  return { traces, layout: { ...baseLayout(narrow), yaxis: paceAxis(traces.flatMap((trace) => trace.y)),
    xaxis: { categoryorder: "array", categoryarray: months } },
    note: "The centre line is the median; boxes show the middle half of activities. Months with one activity have no spread." };
}

function climbingInsight(activities, state, today, narrow) {
  const weeks = weeklyGroups(activities, state, today);
  const hillRecords = activities.filter((activity) => finite(activity.elevation_m)
    && activity.elevation_m >= 0 && activity.distance_km > 0 && validPace(activity));
  const traces = [{ type: "bar", x: weeks.map((week) => week.date), y: weeks.map((week) =>
    round(sum(week.activities.filter((activity) => finite(activity.elevation_m) && activity.elevation_m >= 0)
      .map((activity) => activity.elevation_m)), 0)),
    marker: { color: LIGHT_BLUE }, xaxis: "x", yaxis: "y",
    hovertemplate: "Week of %{x}<br>%{y:.0f} m gained<extra></extra>" },
  { type: "scatter", mode: "markers", x: hillRecords.map((a) => round(a.elevation_m / a.distance_km, 1)),
    y: hillRecords.map((a) => a.pace_s_per_km), xaxis: "x2", yaxis: "y2",
    customdata: hillRecords.map((a) => [a.date, formatPace(a.pace_s_per_km)]),
    marker: { color: GREEN, size: 7, opacity: 0.65 },
    hovertemplate: "%{customdata[0]}<br>%{x} m/km · %{customdata[1]} /km<extra></extra>" }];
  return { traces, layout: { ...baseLayout(narrow),
    xaxis: { domain: [0, 1], anchor: "y", showticklabels: false },
    yaxis: { domain: [0.55, 1], title: "Metres gained", rangemode: "tozero" },
    xaxis2: { domain: [0, 1], anchor: "y2", title: "Climbing (m/km)" },
    yaxis2: paceAxis(hillRecords.map((a) => a.pace_s_per_km), [0, 0.37]) },
    note: "Top: weekly recorded elevation gain. Bottom: whole-activity pace versus metres climbed per kilometre. This is not grade-adjusted pace." };
}

function bestInsight(activities, state, narrow) {
  const target = Number(state.bestDistance);
  const tolerance = Math.max(0.15, target * 0.03);
  const records = activities.filter((activity) => activity.activity_class === "run"
    && finite(activity.duration_s) && activity.duration_s > 0
    && Math.abs(activity.distance_km - target) <= tolerance && validPace(activity));
  if (!records.length) return noData(`No runs within ${round(tolerance, 2)} km of ${target} km match this selection.`, narrow);
  let best = Infinity;
  const bestTimes = records.map((activity) => {
    best = Math.min(best, activity.duration_s / 60);
    return round(best, 2);
  });
  return { traces: [
    { type: "scatter", mode: "markers", name: "Recorded activity", x: records.map((a) => a.date),
      y: records.map((a) => round(a.duration_s / 60, 2)),
      customdata: records.map((a) => round(a.distance_km, 2)),
      marker: { color: LIGHT_BLUE, size: 8 },
      hovertemplate: "%{x}<br>%{y:.1f} min · %{customdata} km<extra></extra>" },
    { type: "scatter", mode: "lines", name: "Best so far", x: records.map((a) => a.date),
      y: bestTimes, line: { color: GREEN, width: 3, shape: "hv" },
      hovertemplate: "Best so far: %{y:.1f} min<extra></extra>" },
  ], layout: { ...baseLayout(narrow), showlegend: true, legend: { orientation: "h", y: 1.12 },
    yaxis: { title: "Recorded duration (min)", gridcolor: "#e4eaf0" } },
    note: `Whole running activities within ±${round(tolerance, 2)} km of ${target} km in the selected period. Duration is Garmin's activity duration, not an official race result or a split PR.` };
}

export function buildInsight(activities, state, options = {}) {
  const today = options.today || new Date();
  const narrow = Boolean(options.narrow);
  const selected = selectActivities(activities, state);
  const builders = {
    volume: () => volumeInsight(selected, state, today, narrow),
    pace: () => comparablePaceInsight(selected, narrow),
    compare: () => comparisonInsight(activities, state, today, narrow),
    effort: () => effortInsight(selected, narrow),
    calendar: () => calendarInsight(selected, state, today, narrow),
    endurance: () => enduranceInsight(selected, state, today, narrow),
    vo2max: () => vo2Insight(selected, state, narrow),
    distribution: () => distributionInsight(selected, narrow),
    climbing: () => climbingInsight(selected, state, today, narrow),
    best: () => bestInsight(selected, state, narrow),
  };
  if (!builders[state.insight]) throw new Error("Unknown insight view");
  return { ...builders[state.insight](), selected, summary: summaryFor(selected), rows: monthlyRows(selected, state) };
}

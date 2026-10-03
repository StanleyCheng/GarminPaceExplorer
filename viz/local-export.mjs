export function parseLocalExport(text) {
  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    throw new Error("This file is not valid JSON.");
  }
  if (!payload || typeof payload !== "object" || !Array.isArray(payload.activities)) {
    throw new Error("This file does not contain Garmin activities.");
  }
  return payload;
}

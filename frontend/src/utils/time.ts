export function formatRelativeTime(value: string, now = Date.now()): string {
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) return "Unknown time";
  const minutes = Math.max(0, Math.floor((now - parsed) / 60000));
  if (minutes < 1) return "Just now";
  if (minutes < 60) return minutes + "m";
  if (minutes < 24 * 60) return Math.floor(minutes / 60) + "h";
  const today = new Date(now);
  const yesterday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1);
  const date = new Date(parsed);
  if (date.toDateString() === yesterday.toDateString()) return "Yesterday";
  return date.toLocaleDateString(undefined, {month: "short", day: "numeric"});
}
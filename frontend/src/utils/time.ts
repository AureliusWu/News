import {ui} from "../locales/zh-CN";

const fullDateTime = new Intl.DateTimeFormat("zh-CN", {
  year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  second: "2-digit", hourCycle: "h23", timeZoneName: "short"
});

export function formatDateTime(value: string): string {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? fullDateTime.format(parsed) : ui.time.unknown;
}

export function formatRelativeTime(value: string, now = Date.now()): string {
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) return ui.time.unknown;
  const minutes = Math.max(0, Math.floor((now - parsed) / 60000));
  if (minutes < 1) return ui.time.justNow;
  if (minutes < 60) return ui.time.minutes(minutes);
  if (minutes < 24 * 60) return ui.time.hours(Math.floor(minutes / 60));
  const today = new Date(now);
  const yesterday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1);
  const date = new Date(parsed);
  if (date.toDateString() === yesterday.toDateString()) return ui.time.yesterday;
  return date.toLocaleDateString("zh-CN", {
    ...(date.getFullYear() !== today.getFullYear() ? {year: "numeric" as const} : {}),
    month: "long", day: "numeric"
  });
}

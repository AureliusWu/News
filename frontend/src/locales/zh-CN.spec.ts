import {describe, expect, it} from "vitest";
import {ui, categoryLabel, languageLabel, regionLabel} from "./zh-CN";
import {formatDateTime, formatRelativeTime} from "../utils/time";

describe("Simplified Chinese presentation", () => {
  it.each([
    ["world", "国际"], ["japan", "日本"], ["middle-east", "中东"], ["US", "美国"]
  ])("maps region %s without changing the code", (code, expected) => {
    expect(regionLabel(code)).toBe(expected);
  });
  it.each([
    ["business", "财经"], ["technology", "科技"], ["science", "科学"]
  ])("maps category %s", (code, expected) => expect(categoryLabel(code)).toBe(expected));
  it.each([
    ["en", "英语"], ["ja", "日语"], ["zh-CN", "简体中文"], ["zh-Hant", "繁体中文"]
  ])("maps language %s", (code, expected) => expect(languageLabel(code)).toBe(expected));
  it.each(["unlisted-code", "constructor", "__proto__"])("preserves unknown code %s", code => {
    expect(regionLabel(code)).toBe(code);
    expect(categoryLabel(code)).toBe(code);
    expect(languageLabel(code)).toBe(code);
  });
  it("keeps snapshot generation time and source coverage explicit", () => {
    const text = ui.snapshot.summary(ui.snapshot.cached, "2026/09/21 GMT+8 17:45:00", 32, 38);
    expect(text).toContain("缓存快照（可能已过时）");
    expect(text).toContain("快照更新：2026/09/21 GMT+8 17:45:00");
    expect(text).toContain("可用来源：32/38");
    expect(text).toContain("非实时，可能延迟");
  });
  it("formats full dates in Chinese with the browser timezone", () => {
    const value = "2026-09-21T09:45:00Z";
    const zone = new Intl.DateTimeFormat("zh-CN", {timeZoneName: "short"})
      .formatToParts(new Date(value)).find(part => part.type === "timeZoneName")!.value;
    expect(formatDateTime(value)).toContain("2026");
    expect(formatDateTime(value)).toContain(zone);
    expect(formatDateTime("not-a-date")).toBe("时间未知");
  });
  it("uses local calendar dates and retains the year for older reporting", () => {
    const now = new Date(2026, 8, 21, 12).getTime();
    expect(formatRelativeTime(new Date(2026, 8, 20, 0).toISOString(), now)).toBe("昨天");
    expect(formatRelativeTime(new Date(2026, 8, 18, 0).toISOString(), now)).toBe("9月18日");
    expect(formatRelativeTime(new Date(2025, 8, 18, 0).toISOString(), now)).toBe("2025年9月18日");
  });
});

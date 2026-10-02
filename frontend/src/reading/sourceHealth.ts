export interface SourceHealth {
  id: string;
  name: string;
  publisher: string;
  health: "PASS" | "FAIL";
  entry_count: number;
  latest_entry: string | null;
  notes: string | null;
}
export interface HealthReport {checked_at: string; sources: SourceHealth[]}
export function parseHealthReport(value: unknown): HealthReport {
  if (!value || typeof value !== "object") throw new Error("来源报告格式不正确。");
  const report = value as HealthReport;
  if (!Number.isFinite(Date.parse(report.checked_at)) || Date.parse(report.checked_at) > Date.now() + 300000
      || !Array.isArray(report.sources) || !report.sources.length || report.sources.length > 500) throw new Error("来源报告缺少有效时间或来源列表。");
  const ids = new Set<string>();
  const sources = report.sources.map(s => {
    if (!s || typeof s.id !== "string" || !s.id || ids.has(s.id)
        || typeof s.name !== "string" || typeof s.publisher !== "string" || !["PASS", "FAIL"].includes(s.health)
        || !Number.isSafeInteger(s.entry_count) || s.entry_count < 0
        || !(s.latest_entry === null || (typeof s.latest_entry === "string" && Number.isFinite(Date.parse(s.latest_entry))))
        || !(s.notes === null || typeof s.notes === "string")) throw new Error("来源报告包含无效记录。");
    ids.add(s.id);
    return {id: s.id, name: s.name, publisher: s.publisher, health: s.health,
      entry_count: s.entry_count, latest_entry: s.latest_entry, notes: s.notes};
  });
  return {checked_at: report.checked_at, sources};
}
export function healthDescription(source: SourceHealth): string {
  if (source.health === "PASS") return "采集正常";
  if (/No valid articles/.test(source.notes || "")) return "无近期合规条目（不能据此判定网站不可用）";
  if (/timeout/i.test(source.notes || "")) return "采集超时";
  if (/HTTP (401|403|429)/.test(source.notes || "")) return "上游限制访问";
  if (/HTTP 404/.test(source.notes || "")) return "订阅地址不存在";
  return "采集失败，原因见记录";
}

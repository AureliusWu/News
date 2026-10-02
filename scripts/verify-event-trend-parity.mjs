import {execFileSync} from "node:child_process";
import {createRequire} from "node:module";
import {fileURLToPath, pathToFileURL} from "node:url";
import {resolve, dirname, sep} from "node:path";
import {mkdirSync, writeFileSync} from "node:fs";
import {isDeepStrictEqual} from "node:util";

const root = fileURLToPath(new URL("../", import.meta.url));
const require = createRequire(new URL("../frontend/package.json", import.meta.url));
const {build} = await import(pathToFileURL(require.resolve("esbuild")).href);
const compiled = await build({entryPoints: [resolve(root, "frontend/src/events/trends.ts")],
  bundle: true, platform: "node", format: "esm", target: "es2022", write: false, logLevel: "silent"});
const {buildTrends} = await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString("base64")}`);
const python = process.env.NEWS_PYTHON || resolve(root, "backend/.venv/Scripts/python.exe");
const fixtures = JSON.parse(execFileSync(python, ["scripts/snapshot/event_trend_cases.py"],
  {cwd: root, encoding: "utf8", maxBuffer: 16 * 1024 * 1024}));
const cases = fixtures.map(c => ({name: c.name, pass: isDeepStrictEqual(
  buildTrends(c.index, c.snapshot, c.policy, c.evaluated_at), c.expected)}));
const report = {schema_version: 1, checked_at: new Date().toISOString(), method_version: "recent-publisher-activity-v1",
  synthetic_only: true, cases, gate_pass: cases.every(c => c.pass)};
const at = process.argv.indexOf("--report");
if (at !== -1) {
  const target = resolve(root, process.argv[at + 1] || "");
  if (!target.toLowerCase().startsWith((root.endsWith(sep) ? root : root + sep).toLowerCase())) throw new Error("Report must remain within News workspace");
  mkdirSync(dirname(target), {recursive: true}); writeFileSync(target, JSON.stringify(report, null, 2) + "\n");
}
console.log(JSON.stringify(report));
if (!report.gate_pass) process.exitCode = 1;

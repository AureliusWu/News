import {mkdirSync, writeFileSync} from "node:fs";
import {execFileSync} from "node:child_process";
import {resolve} from "node:path";

const base = new URL("https://aureliuswu.github.io/News/");
const observedAt = new Date();
async function get(path, optional = false) {
  const start = performance.now();
  const response = await fetch(new URL(path, base), {cache:"no-store", signal:AbortSignal.timeout(25000)});
  const body = await response.text();
  if (Buffer.byteLength(body) > 8 * 1024 * 1024) throw new Error(path + ": oversized response");
  if (!response.ok && !(optional && response.status === 404)) throw new Error(path + ": HTTP " + response.status);
  return {status:response.status, elapsed_ms:Math.round(performance.now()-start), bytes:Buffer.byteLength(body), body};
}
const observation = {schema_version:1, observed_at:observedAt.toISOString(), base_url:base.href,
  acceptance:{seven_day_gate:"NOT_EVALUATED",browser_gate:"NOT_EVALUATED",physical_device_gate:"NOT_EVALUATED"}};
try {
  const html = await get("");
  observation.html = {status:html.status,elapsed_ms:html.elapsed_ms,language_zh_cn:/lang=["']zh-CN["']/.test(html.body),
    scripts:[...html.body.matchAll(/assets\/[^"' ]+\.js/g)].map(m=>m[0])};
  const news = await get("data/news.json"), data = JSON.parse(news.body);
  const health = await get("data/source-health.json"), sourceHealth = JSON.parse(health.body);
  const age = (observedAt.getTime()-Date.parse(data.generated_at))/3600000;
  observation.snapshot = {status:news.status,elapsed_ms:news.elapsed_ms,bytes:news.bytes,
    generated_at:data.generated_at,snapshot_id:data.snapshot_id,version:data.meta?.version,
    content_sha256:data.content_sha256,article_count:data.articles?.length,
    age_hours:Number.isFinite(age)?age:null,freshness_2h_pass:Number.isFinite(age)&&age>=-5/60&&age<=2,
    collector_gate_pass:data.health?.gate_pass===true};
  observation.source_health = {checked_at:sourceHealth.checked_at,generated_at:sourceHealth.generated_at,
    same_generation:data.snapshot_id
      ? ["snapshot_id","generated_at","content_sha256"].every(key=>sourceHealth[key]===data[key])
      : sourceHealth.checked_at===data.generated_at,
    summary:sourceHealth.summary??sourceHealth.health};
  const releaseResponse = await get("release.json",true);
  const release = releaseResponse.status===200 ? JSON.parse(releaseResponse.body) : null;
  observation.release = {status:releaseResponse.status,version:release?.version??null,
    source_revision:release?.source_revision??null,formal_release:release?.formal_release??null};
  let history=[],historyError=null;
  try {
    history=JSON.parse(execFileSync("gh",["run","list","--repo","AureliusWu/News","--workflow","deploy-gh-pages.yml","--limit","100",
      "--json","databaseId,conclusion,event,createdAt,updatedAt,headSha"],{encoding:"utf8",timeout:30000}));
  } catch(error) {historyError=String(error.message).slice(0,500);}
  const runs=history.filter(r=>r.event==="schedule"&&Date.parse(r.createdAt)>=observedAt.getTime()-7*86400000)
    .sort((a,b)=>Date.parse(a.createdAt)-Date.parse(b.createdAt));
  const gaps=runs.slice(1).map((r,i)=>(Date.parse(r.createdAt)-Date.parse(runs[i].createdAt))/3600000);
  observation.scheduling={run_count_7d:runs.length,intervals_hours:gaps,max_interval_hours:gaps.length?Math.max(...gaps):null,
    caveat:"Run intervals are not independent snapshot-age observations and do not establish seven-day freshness.",error:historyError};
  observation.workflow_history=history;
} catch(error) {
  observation.transport_error=String(error.message).slice(0,500);
  process.exitCode=1;
}
const directory=resolve(process.argv[2]||"artifacts/v1-observations");
mkdirSync(directory,{recursive:true});
const path=resolve(directory,observedAt.toISOString().replaceAll(":","-")+".json");
writeFileSync(path,JSON.stringify(observation,null,2)+"\n");
console.log(JSON.stringify({path,html:observation.html,snapshot:observation.snapshot,release:observation.release,
  source_health:observation.source_health,transport_error:observation.transport_error,
  scheduling:observation.scheduling?{...observation.scheduling,intervals_hours:undefined}:undefined},null,2));

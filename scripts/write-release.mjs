import {readFileSync, existsSync, mkdirSync, writeFileSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {readAiPolicy} from "./ai-feature-policy.mjs";
import {validateReleaseApproval, validateReleaseCandidate} from "./release-approval.mjs";
const root = new URL("../", import.meta.url);
const {version} = JSON.parse(readFileSync(new URL("frontend/package.json", root), "utf8"));
const aiPolicy = readAiPolicy(root);
const sourceRevision = process.env.NEWS_SOURCE_REVISION || process.env.GITHUB_SHA || 'local-uncommitted';
const candidatePath = new URL('release-candidate.json',root);
const candidate = existsSync(candidatePath) && validateReleaseCandidate(version,JSON.parse(readFileSync(candidatePath,'utf8')));
const acceptancePath = process.env.NEWS_RELEASE_ACCEPTANCE_FILE;
const approval = acceptancePath
  ? validateReleaseApproval(version,JSON.parse(readFileSync(acceptancePath,'utf8')))
  : candidate ? null : validateReleaseApproval(version, /^\d+\.\d+\.\d+$/.test(version)
    ? JSON.parse(readFileSync(new URL("release-acceptance.json", root), "utf8")) : undefined);
if (approval?.approval === 'verified-release' && approval.source_revision !== sourceRevision)
  throw new Error('Verified release receipt must match the actual build source SHA.');
const waived = approval?.approval === 'owner-approved-release-with-warnings';
const release = {schema_version: 1, version, stage: `V${version}${approval ? waived ? '-with-waivers' : '' : '-candidate'}`, formal_release: Boolean(approval),
  release_status: approval ? waived ? "RELEASED_WITH_WARNINGS" : "RELEASED" : "CANDIDATE",
  acceptance: approval ? {mode: approval.approval, accepted_by: approval.accepted_by,
    accepted_on: approval.accepted_on, waivers: approval.waivers,
    gates: approval.gates,
    record: `https://github.com/AureliusWu/News/blob/main/docs/V${version}_${waived ? 'RELEASE_WAIVERS' : 'HANDOFF'}.md`} : null,
  source_revision: sourceRevision, built_at: new Date().toISOString(), data_schema_version: 1,
  ai_content_generation: aiPolicy};
mkdirSync(new URL("frontend/public/", root), {recursive: true});
const target = new URL("frontend/public/release.json", root);
writeFileSync(target, `${JSON.stringify(release, null, 2)}\n`);
console.log(`Release metadata: ${fileURLToPath(target)} (${version}; ${release.source_revision})`);

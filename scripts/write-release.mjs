import {readFileSync, mkdirSync, writeFileSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {readAiPolicy} from "./ai-feature-policy.mjs";
import {validateReleaseApproval} from "./release-approval.mjs";
const root = new URL("../", import.meta.url);
const {version} = JSON.parse(readFileSync(new URL("frontend/package.json", root), "utf8"));
const aiPolicy = readAiPolicy(root);
const approval = validateReleaseApproval(version, /^\d+\.\d+\.\d+$/.test(version)
  ? JSON.parse(readFileSync(new URL("release-acceptance.json", root), "utf8")) : undefined);
const release = {schema_version: 1, version, stage: approval ? "V1.0.0-with-waivers" : version.startsWith("0.9.") ? "M5-candidate" : version.startsWith("0.5.") ? "M3-preview" : version.startsWith("0.4.") ? "M2-preview" : "M1-preview", formal_release: Boolean(approval),
  release_status: approval ? "RELEASED_WITH_WARNINGS" : "CANDIDATE",
  acceptance: approval ? {mode: approval.approval, accepted_by: approval.accepted_by,
    accepted_on: approval.accepted_on, waivers: approval.waivers,
    record: "https://github.com/AureliusWu/News/blob/main/docs/V1.0.0_RELEASE_WAIVERS.md"} : null,
  source_revision: process.env.GITHUB_SHA || "local-uncommitted", built_at: new Date().toISOString(), data_schema_version: 1,
  ai_content_generation: aiPolicy};
mkdirSync(new URL("frontend/public/", root), {recursive: true});
const target = new URL("frontend/public/release.json", root);
writeFileSync(target, `${JSON.stringify(release, null, 2)}\n`);
console.log(`Release metadata: ${fileURLToPath(target)} (${version}; ${release.source_revision})`);

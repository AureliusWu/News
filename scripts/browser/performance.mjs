import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {join} from 'node:path';
import {manifest, output, requireIsolatedCI, siteURL, startSite} from './server.mjs';

requireIsolatedCI();
const data = await manifest();
const directory = join(output, 'performance');
await mkdir(directory, {recursive: true});
function controlsMatch(settings, preset) {
  const desktop = preset === 'desktop';
  return settings?.formFactor === (desktop ? 'desktop' : 'mobile') &&
    settings.throttlingMethod === 'simulate' &&
    settings.screenEmulation?.mobile === !desktop &&
    settings.screenEmulation.width === (desktop ? 1350 : 412) &&
    settings.screenEmulation.height === (desktop ? 940 : 823) &&
    settings.screenEmulation.deviceScaleFactor === (desktop ? 1 : 1.75) &&
    settings.throttling?.rttMs === (desktop ? 40 : 150) &&
    settings.throttling.throughputKbps === (desktop ? 10240 : 1638.4) &&
    settings.throttling.cpuSlowdownMultiplier === (desktop ? 1 : 4) &&
    settings.blockedUrlPatterns?.includes('https://*');
}
const samples = [];
for (const preset of ['desktop', 'mobile']) {
  for (let sample = 1; sample <= 5; sample++) {
    const order = (sample + (preset === 'mobile' ? 1 : 0)) % 2 ? ['baseline', 'candidate'] : ['candidate', 'baseline'];
    for (const variant of order) {
      const name = `${preset}-${sample}-${variant}`;
      const reportPath = join(directory, `${name}.json`);
      const server = await startSite(data[variant], name);
      let exitCode;
      try {
        exitCode = await new Promise((resolve, reject) => {
          const args = [fileURLToPath(new URL('./node_modules/lighthouse/cli/index.js', import.meta.url)), siteURL,
            '--only-categories=performance', '--throttling-method=simulate', '--output=json',
            `--output-path=${reportPath}`, '--blocked-url-patterns=https://*', '--chrome-flags=--headless=new', '--quiet'];
          if (preset === 'desktop') args.push('--preset=desktop');
          const child = spawn(process.execPath, args, {stdio: 'inherit'});
          child.on('error', reject);
          child.on('exit', code => resolve(code));
        });
      } finally { await server.stop(); }
      let result = {name, preset, sample, variant, exit_code: exitCode};
      try {
        const bytes = await readFile(reportPath);
        const report = JSON.parse(bytes);
        result = {...result, sha256: createHash('sha256').update(bytes).digest('hex'),
          lighthouse_version: report.lighthouseVersion, user_agent: report.userAgent,
          fetch_time: report.fetchTime, settings: report.configSettings,
          controls_match: controlsMatch(report.configSettings, preset),
          lcp_ms: report.audits['largest-contentful-paint'].numericValue,
          fcp_ms: report.audits['first-contentful-paint'].numericValue,
          tbt_ms: report.audits['total-blocking-time'].numericValue,
          cls: report.audits['cumulative-layout-shift'].numericValue,
          score: report.categories.performance.score,
          runtime_error: report.runtimeError || null, warnings: report.runWarnings || [],
          news_requests: (report.audits['network-requests']?.details?.items || [])
            .filter(item => /\/News\/data\/news(?:\.compact)?\.json$/.test(item.url)),
        };
      } catch (error) { result.read_error = String(error); }
      samples.push(result);
      await writeFile(join(directory, 'samples.json'), JSON.stringify(samples, null, 2) + '\n');
    }
  }
}
const median = values => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
const groups = {};
for (const preset of ['desktop', 'mobile']) {
  groups[preset] = {};
  for (const variant of ['baseline', 'candidate']) {
    const rows = samples.filter(row => row.preset === preset && row.variant === variant);
    const values = rows.map(row => row.lcp_ms);
    groups[preset][variant] = {samples: rows.length, median_lcp_ms: median(values), worst_lcp_ms: Math.max(...values)};
  }
  groups[preset].candidate_median_change_fraction = groups[preset].candidate.median_lcp_ms / groups[preset].baseline.median_lcp_ms - 1;
}
const valid = samples.length === 20 && samples.every(row => row.exit_code === 0 && !row.runtime_error &&
  row.controls_match && Number.isFinite(row.lcp_ms) && row.news_requests.length === 1 && row.news_requests[0].statusCode === 200);
await writeFile(join(directory, 'summary.json'), JSON.stringify({
  observed_at: new Date().toISOString(), all_samples_valid: valid, groups,
  diagnostic_budget_status: ['desktop', 'mobile'].every(preset => groups[preset].candidate.worst_lcp_ms <= 3000)
    ? 'WITHIN_LAB_BUDGET' : 'EXCEEDS_LAB_BUDGET',
  baseline: data.baseline, candidate: data.candidate, inputs: data.inputs,
  design: '5 cold runs per arm and device; alternating AB/BA; same runner/browser and identical decoded frozen news; candidate lossless source dictionary; third-party HTTPS resources blocked in BOTH arms.',
  interpretation: 'Controlled application-startup diagnostic only. Loopback delivery and excluded third-party images do not close production first-screen, interaction or phone gates. No sample removal or retries.',
  formal_release: false,
}, null, 2) + '\n');
if (!valid) process.exitCode = 1;

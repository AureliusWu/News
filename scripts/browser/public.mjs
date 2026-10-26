import {spawn} from 'node:child_process';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {validatePublicRelease} from '../release-receipt.mjs';
import {chromium} from '@playwright/test';
import {requireIsolatedCI} from './server.mjs';
requireIsolatedCI();
const site='https://aureliuswu.github.io/News/';
const revision=process.env.EXPECTED_REVISION;
const expectedStatus=process.env.EXPECTED_RELEASE_STATUS || 'CANDIDATE';
const receipt=expectedStatus==='CANDIDATE'?undefined:JSON.parse(await readFile(new URL('../../docs/releases/V1.1.0_ACCEPTANCE.json',import.meta.url),'utf8'));
if(!/^[a-f0-9]{40}$/.test(revision||'')) throw new Error('Pin the exact deployed application source.');
const directory='artifacts/public-verification';
await mkdir(directory,{recursive:true});
async function identity() {
  const response=await fetch(new URL('release.json',site),{cache:'no-store',signal:AbortSignal.timeout(30000)});
  if(!response.ok) throw new Error(`release.json HTTP ${response.status}`);
  const release=await response.json();
  return validatePublicRelease(release,{version:'1.1.0',revision,status:expectedStatus,receipt});
}
const release=await identity();
await writeFile(join(directory,'release.json'),JSON.stringify(release,null,2)+'\n');
const browser=await chromium.launch({channel:'chrome',chromiumSandbox:true});
const smoke={observed_at:new Date().toISOString(),revision,release_status:expectedStatus,browser:browser.version(),widths:[],page_errors:[]};
try {
  const page=await browser.newPage();
  page.on('pageerror',error=>smoke.page_errors.push(error.message));
  for(const width of [320,390,768,1350]) {
    await page.setViewportSize({width,height:940});
    const response=await page.goto(site,{waitUntil:'domcontentloaded'});
    await page.locator('.news-card').first().waitFor({state:'visible'});
    const layout=await page.evaluate(()=>({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,
      cards:document.querySelectorAll('.news-card').length,footer:document.querySelector('footer')?.textContent}));
    smoke.widths.push({width,status:response.status(),...layout});
    await page.screenshot({path:join(directory,`public-${width}.png`)});
    if(response.status()!==200 || layout.scroll>layout.client || !layout.footer?.includes('V1.1.0') ||
        layout.footer.includes('候选')!==(expectedStatus==='CANDIDATE')) throw new Error('Public layout or release label failed.');
  }
  const first=page.locator('.news-card').first();
  const savedTitle=await first.locator('h2 a').innerText();
  await first.getByRole('button',{name:/^收藏：/}).click();
  await page.reload({waitUntil:'domcontentloaded'});
  await page.locator('.news-card').filter({hasText:savedTitle}).getByRole('button',{name:/^取消收藏：/}).waitFor({state:'visible'});
  await page.getByRole('link',{name:/^我的收藏/}).click();
  await page.locator('.reading-bookmark').filter({hasText:savedTitle}).waitFor({state:'visible'});
  smoke.bookmark_persisted=true;
  await page.locator('header a[href="/News/"]').click();
  await page.getByRole('link',{name:'事件聚合',exact:true}).click();
  const link=page.locator('a[href*="/events/e_"]').first();
  await link.waitFor({state:'visible'});const title=(await link.innerText()).trim();
  await link.click();
  await page.waitForURL(/\/News\/events\/e_[a-f0-9]{24}(?:\?.*)?$/,{waitUntil:'domcontentloaded'});
  await page.getByRole('heading',{name:title,exact:true}).first().waitFor({state:'visible'});
  smoke.event_url=page.url();const response=await page.reload({waitUntil:'domcontentloaded'});
  await page.getByRole('heading',{name:title,exact:true}).first().waitFor({state:'visible'});
  if(page.url()!==smoke.event_url) throw new Error('Direct event reload changed its URL.');
  smoke.deep_link_status=response.status(); // Pages 404 plus rendered SPA remain distinct.
  await page.getByRole('button',{name:'关注事件',exact:true}).click();
  await page.reload({waitUntil:'domcontentloaded'});
  await page.getByRole('button',{name:'取消关注事件',exact:true}).waitFor({state:'visible'});
  smoke.event_follow_persisted=true;
  if(smoke.page_errors.length) throw new Error('Unexpected public application JavaScript error.');
} finally {
  await browser.close();await writeFile(join(directory,'smoke.json'),JSON.stringify(smoke,null,2)+'\n');
}
await identity();
if(process.env.RUN_PUBLIC_PERFORMANCE==='false') process.exit(0);
const samples=[];
for(const preset of ['desktop','mobile']) for(let sample=1;sample<=5;sample++) {
  const before=await identity();const name=`${preset}-${sample}`;const path=join(directory,`${name}.json`);
  const args=[fileURLToPath(new URL('./node_modules/lighthouse/cli/index.js',import.meta.url)),site,
    '--only-categories=performance','--throttling-method=simulate','--output=json',`--output-path=${path}`,
    '--chrome-flags=--headless=new','--quiet'];
  if(preset==='desktop') args.push('--preset=desktop');
  const code=await new Promise((resolve,reject)=>{
    const child=spawn(process.execPath,args,{stdio:'inherit'});child.on('error',reject);child.on('exit',resolve);
  });
  const bytes=await readFile(path);const result=JSON.parse(bytes);const after=await identity();
  samples.push({preset,sample,exit_code:code,observed_at:result.fetchTime,sha256:createHash('sha256').update(bytes).digest('hex'),
    revision:before.source_revision,after_revision:after.source_revision,lcp_ms:result.audits['largest-contentful-paint'].numericValue,
    settings:result.configSettings,warnings:result.runWarnings,runtime_error:result.runtimeError||null,
    news_requests:(result.audits['network-requests']?.details?.items||[]).filter(row=>/\/News\/data\/news(?:\.(?:compact|home))?\.json$/.test(row.url))});
  await writeFile(join(directory,'samples.json'),JSON.stringify(samples,null,2)+'\n');
}
const groups=Object.fromEntries(['desktop','mobile'].map(preset=>{
  const values=samples.filter(row=>row.preset===preset).map(row=>row.lcp_ms).sort((a,b)=>a-b);
  return [preset,{samples:values.length,median_lcp_ms:values[2],worst_lcp_ms:Math.max(...values)}];
}));
const valid=samples.length===10 && samples.every(row=>row.exit_code===0&&!row.runtime_error&&Number.isFinite(row.lcp_ms)&&
  row.settings.throttlingMethod==='simulate' && row.settings.formFactor===row.preset &&
  !row.settings.blockedUrlPatterns?.length && row.news_requests.some(request=>request.statusCode===200));
await writeFile(join(directory,'summary.json'),JSON.stringify({observed_at:new Date().toISOString(),revision,all_samples_valid:valid,groups,
  public_budget_status:Object.values(groups).every(group=>group.worst_lcp_ms<=3000)?'WITHIN_PUBLIC_SAMPLE_BUDGET':'EXCEEDS_PUBLIC_SAMPLE_BUDGET',
  scope:'Actual public HTTPS site, standard runner, third-party images included, five cold runs per device. Separate from frozen-input comparison and physical phone acceptance.',
  formal_release:release.formal_release,release_status:expectedStatus},null,2)+'\n');
if(!valid) process.exitCode=1;

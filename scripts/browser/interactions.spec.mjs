import {test,expect} from '@playwright/test';
import {manifest,siteURL,startSite} from './server.mjs';
const percentile95=values=>[...values].sort((a,b)=>a-b)[Math.ceil(values.length*.95)-1];
for(const preset of ['desktop','mobile']) {
  test(`${preset} core interactions retain visible results within the interaction budget`,async({page,browser},testInfo)=>{
    test.setTimeout(180000);
    const data=await manifest(); const server=await startSite(data.candidate,`interaction-${preset}-${testInfo.project.name}`);
    const groups={};
    async function sample(name,action,ready) {
      await page.evaluate(()=>{
        performance.clearMarks('news-interaction-start');
        document.addEventListener('click',()=>performance.mark('news-interaction-start'),{once:true,capture:true});
      });
      await action(); await ready();
      const value=await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>{
        const start=performance.getEntriesByName('news-interaction-start').at(-1)?.startTime;
        resolve(Number.isFinite(start)?performance.now()-start:null);
      }))));
      (groups[name] ||= []).push(value);
    }
    const settled=async()=>{
      await expect(page.locator('.refresh-button')).toBeEnabled();
      await expect(page.locator('.news-card').first()).toBeVisible();
    };
    try {
      await page.setViewportSize(preset==='mobile'?{width:412,height:823}:{width:1350,height:940});
      await page.goto(siteURL,{waitUntil:'domcontentloaded'});await settled();
      const word=(await page.locator('.news-card h2 a').first().innerText()).slice(0,80);
      for(let i=0;i<20;i++) {
        await sample('bookmark',()=>page.locator('.news-card').first().getByRole('button',{name:/^(取消)?收藏：/}).click(),
          ()=>expect(page.locator('.news-card').first().getByRole('button',{name:/^(取消)?收藏：/})).toHaveAttribute('aria-pressed',i%2?'false':'true'));
      }
      for(let i=0;i<20;i++) {
        await page.locator('.search-form input').fill(i%2?'':word);
        await sample('search',()=>page.locator('.search-form button').click(),settled);
      }
      for(let i=0;i<20;i++) {
        const tab=i%2?page.locator('.topic-tabs button').first():page.locator('.topic-tabs').getByRole('button',{name:'日本',exact:true});
        await sample('region',()=>tab.click(),async()=>{await expect(tab).toHaveAttribute('aria-pressed','true');await settled();});
      }
      await page.locator('.search-form input').fill(word);await page.locator('.search-form button').click();await settled();
      await page.locator('.saved-filters summary').click();
      await page.getByRole('textbox',{name:'方案名称',exact:true}).fill('Interaction reference');
      await page.getByRole('button',{name:'保存当前筛选',exact:true}).click();
      await page.getByRole('combobox',{name:'已存筛选方案',exact:true}).selectOption({label:'Interaction reference'});
      for(let i=0;i<20;i++) {
        await page.getByRole('button',{name:'清除筛选',exact:true}).click();await settled();
        await sample('restore-filter',()=>page.getByRole('button',{name:'应用方案',exact:true}).click(),async()=>{
          await expect(page.locator('.search-form input')).toHaveValue(word);await settled();
        });
      }
      await page.getByRole('button',{name:'清除筛选',exact:true}).click();await settled();
      await page.getByRole('link',{name:'事件聚合',exact:true}).click();
      for(let i=0;i<20;i++) {
        const link=page.locator('.reading-bookmark h2 a').first();await expect(link).toBeVisible();
        const title=await link.innerText();
        await sample('event-detail',()=>link.click(),async()=>{
          await expect(page).toHaveURL(/\/events\/e_/);
          await expect(page.getByRole('heading',{name:title,exact:true}).first()).toBeVisible();
          await expect(page.getByRole('heading',{name:'报道时间线',exact:true})).toBeVisible();
        });
        await page.getByRole('link',{name:'返回事件列表',exact:true}).click();
      }
      const report={schema_version:1,preset,browser:browser.version(),revision:data.candidate.revision,snapshot_id:data.snapshot_id,
        method:'Click capture timestamp to expected visible DOM and two animation frames; includes driver/assertion overhead. Not real-user INP or CPU-throttled phone evidence.',
        budget_ms:200,groups:Object.fromEntries(Object.entries(groups).map(([name,values])=>[name,{samples:values.length,
          raw_ms:values,p95_ms:percentile95(values),worst_ms:Math.max(...values)}]))};
      await testInfo.attach(`${preset}-interactions.json`,{body:JSON.stringify(report,null,2),contentType:'application/json'});
      for(const group of Object.values(report.groups)) {
        expect(group.samples).toBe(20);expect(group.raw_ms.every(Number.isFinite)).toBe(true);expect(group.p95_ms).toBeLessThanOrEqual(200);
      }
    } finally {await server.stop();}
  });
}

import {test,expect} from '@playwright/test';
import {manifest,siteURL,startSite} from './server.mjs';
const percentile95=values=>[...values].sort((a,b)=>a-b)[Math.ceil(values.length*.95)-1];
for(const preset of ['desktop','mobile']) {
  test(`${preset} core interactions retain visible results within the interaction budget`,async({page,browser},testInfo)=>{
    test.setTimeout(180000);
    const data=await manifest(); const server=await startSite(data.candidate,`interaction-${preset}-${testInfo.project.name}`);
    const groups={}; const upperBounds={};
    async function sample(name,action,ready,expected) {
      await page.evaluate(({kind,expected})=>{
        performance.clearMarks('news-interaction-start');
        performance.clearMeasures('news-visible');
        document.addEventListener('click',()=>{
          const start=performance.now();performance.mark('news-interaction-start');let stable=0;
          const visible=()=>{
            const input=document.querySelector('.search-form input');
            const refresh=document.querySelector('.refresh-button');
            const first=document.querySelector('.news-card');
            const newsReady=first && refresh && !refresh.disabled;
            if(kind==='bookmark') return first?.querySelector('button[aria-label^="收藏："],button[aria-label^="取消收藏："]')?.getAttribute('aria-pressed')===expected;
            if(kind==='search'||kind==='restore-filter') return newsReady && input?.value===expected && (!expected || first.querySelector('h2')?.textContent.includes(expected));
            if(kind==='region') return newsReady && document.querySelector('.topic-tabs button[aria-pressed="true"]')?.textContent.trim()===expected;
            return location.pathname.includes('/events/e_') && Array.from(document.querySelectorAll('.reading-page h2')).some(node=>node.textContent===expected)
              && Array.from(document.querySelectorAll('.reading-page h2')).some(node=>node.textContent==='报道时间线');
          };
          const frame=()=>{
            stable=visible()?stable+1:0;
            if(stable===2) performance.measure('news-visible',{start,end:performance.now()});
            else if(performance.now()-start<5000) requestAnimationFrame(frame);
          };requestAnimationFrame(frame);
        },{once:true,capture:true});
      },{kind:name,expected});
      await action(); await ready();
      await page.waitForFunction(()=>performance.getEntriesByName('news-visible','measure').length>0);
      const {value,upper}=await page.evaluate(()=>({value:performance.getEntriesByName('news-visible','measure').at(-1)?.duration,
        upper:performance.now()-performance.getEntriesByName('news-interaction-start').at(-1)?.startTime}));
      (groups[name] ||= []).push(value);
      (upperBounds[name] ||= []).push(upper);
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
          ()=>expect(page.locator('.news-card').first().getByRole('button',{name:/^(取消)?收藏：/})).toHaveAttribute('aria-pressed',i%2?'false':'true'),i%2?'false':'true');
      }
      for(let i=0;i<20;i++) {
        await page.locator('.search-form input').fill(i%2?'':word);
        await sample('search',()=>page.locator('.search-form button').click(),settled,i%2?'':word);
      }
      for(let i=0;i<20;i++) {
        const tab=i%2?page.locator('.topic-tabs button').first():page.locator('.topic-tabs').getByRole('button',{name:'日本',exact:true});
        await sample('region',()=>tab.click(),async()=>{await expect(tab).toHaveAttribute('aria-pressed','true');await settled();},(await tab.innerText()).trim());
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
        },word);
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
        },title);
        await page.getByRole('link',{name:'返回事件列表',exact:true}).click();
      }
      const report={schema_version:1,preset,browser:browser.version(),revision:data.candidate.revision,snapshot_id:data.snapshot_id,
        method:'Browser click capture to the required business DOM stable for two animation frames. Original driver/assertion upper bounds retained separately. Not real-user INP or CPU-throttled phone evidence.',
        driver_upper_bound_ms:upperBounds,
        budget_ms:200,groups:Object.fromEntries(Object.entries(groups).map(([name,values])=>[name,{samples:values.length,
          raw_ms:values,p95_ms:percentile95(values),worst_ms:Math.max(...values)}]))};
      await testInfo.attach(`${preset}-interactions.json`,{body:JSON.stringify(report,null,2),contentType:'application/json'});
      for(const group of Object.values(report.groups)) {
        expect(group.samples).toBe(20);expect(group.raw_ms.every(Number.isFinite)).toBe(true);expect(group.p95_ms).toBeLessThanOrEqual(200);
      }
    } finally {await server.stop();}
  });
}

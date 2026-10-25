import {test as base, expect} from '@playwright/test';
import {manifest, siteURL, startSite} from './server.mjs';

const test = base.extend({
  site: async ({}, use, testInfo) => {
    const data = await manifest();
    let server = await startSite(data.candidate, `${testInfo.project.name}/${testInfo.title}/candidate`);
    try {
      await use({data, switchTo: async variant => {
        await server.stop();
        server = await startSite(data[variant], `${testInfo.project.name}/${testInfo.title}/${variant}`);
      }});
    } finally { await server.stop(); }
  },
});

async function home(page) {
  await page.goto(siteURL, {waitUntil: 'domcontentloaded'});
  await expect(page.locator('.news-card').first()).toBeVisible();
}

async function saveFirst(page) {
  const card = page.locator('.news-card').first();
  const id = await card.getAttribute('data-news-id');
  const title = await card.locator('h2 a').innerText();
  const bookmark = card.getByRole('button', {name: /^收藏：/});
  await bookmark.click();
  await expect(card.getByRole('button', {name: /^取消收藏：/})).toHaveAttribute('aria-pressed', 'true');
  return {id, title};
}

async function assertSaved(page, saved) {
  const card = page.locator('.news-card').filter({has: page.locator(`h2 a`, {hasText: saved.title})}).first();
  await expect(card).toHaveAttribute('data-news-id', saved.id);
  await expect(card.getByRole('button', {name: /^取消收藏：/})).toHaveAttribute('aria-pressed', 'true');
}

async function readyOffline(page) {
  await page.waitForFunction(() => !!navigator.serviceWorker.controller);
  await expect.poll(() => page.evaluate(async () => {
    const url = new URL('data/news.json', new URL('/News/', location.href)).href;
    for (const name of await caches.keys()) {
      if (await (await caches.open(name)).match(url)) return true;
    }
    return false;
  })).toBe(true);
}

test('saved filter survives reload and restores the URL query', async ({page, site}) => {
  await home(page);
  await page.locator('.search-form input').fill('climate');
  await page.locator('.search-form button').click();
  await page.locator('.saved-filters summary').click();
  await page.getByRole('textbox',{name:'方案名称',exact:true}).fill('Climate reading');
  await page.getByRole('button',{name:'保存当前筛选',exact:true}).click();
  await page.goto(siteURL,{waitUntil:'domcontentloaded'});
  await page.locator('.saved-filters summary').click();
  await page.getByRole('combobox',{name:'已存筛选方案',exact:true}).selectOption({label:'Climate reading'});
  await page.getByRole('button',{name:'应用方案',exact:true}).click();
  await expect(page.locator('.search-form input')).toHaveValue('climate');
  await expect(page).toHaveURL(/q=climate/);
});

test('followed event survives direct library reload and preserves its identity', async ({page, site}) => {
  await page.goto(new URL('events',siteURL).href,{waitUntil:'domcontentloaded'});
  const card=page.locator('.reading-bookmark').first();
  const title=await card.locator('h2').innerText();
  await card.getByRole('button',{name:'关注事件',exact:true}).click();
  await expect(card.getByRole('button',{name:'取消关注事件',exact:true})).toHaveAttribute('aria-pressed','true');
  await page.goto(new URL('library',siteURL).href,{waitUntil:'domcontentloaded'});
  const followed=page.locator('.following-card').filter({hasText:title});
  await expect(followed).toBeVisible();
  await expect(followed).toContainText('新增收录 0 篇');
  await page.reload({waitUntil:'domcontentloaded'});
  await expect(page.locator('.following-card').filter({hasText:title})).toBeVisible();
});

test('news bookmark survives reload and is visible in the library', async ({page, browser, site}, testInfo) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await home(page);
  const saved = await saveFirst(page);
  await page.reload({waitUntil: 'domcontentloaded'});
  await assertSaved(page, saved);
  await page.goto(new URL('library', siteURL).href, {waitUntil: 'domcontentloaded'});
  await expect(page.locator('.reading-bookmark').filter({hasText: saved.title})).toBeVisible();
  expect(errors).toEqual([]);
  await testInfo.attach('browser-and-input', {body: JSON.stringify({
    browser: browser.version(), snapshot_id: site.data.snapshot_id, revision: site.data.candidate.revision,
  }), contentType: 'application/json'});
});

test('event navigation and direct detail reload render the selected title', async ({page, site}) => {
  await page.goto(new URL('events', siteURL).href, {waitUntil: 'domcontentloaded'});
  const event = page.locator('a[href*="/events/e_"]').first();
  await expect(event).toBeVisible();
  const title = (await event.innerText()).trim();
  await event.click();
  await expect(page).toHaveURL(/\/News\/events\/e_[a-f0-9]+/);
  await expect(page.getByText(title, {exact: true}).first()).toBeVisible();
  const deepLink = page.url();
  await page.reload({waitUntil: 'domcontentloaded'});
  await expect(page).toHaveURL(deepLink);
  await expect(page.getByText(title, {exact: true}).first()).toBeVisible();
  await expect(page.locator('a[href^="https://"][target="_blank"]').first()).toBeVisible();
});

test('390px layout has no horizontal overflow', async ({page, site}, testInfo) => {
  await page.setViewportSize({width: 390, height: 844});
  await home(page);
  const dimensions = await page.evaluate(() => ({
    client: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
    cards: Array.from(document.querySelectorAll('.news-card')).slice(0, 5).map(card => {
      const rect = card.getBoundingClientRect();
      return {left: rect.left, right: rect.right};
    }),
  }));
  expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client);
  for (const card of dimensions.cards) {
    expect(card.left).toBeGreaterThanOrEqual(0);
    expect(card.right).toBeLessThanOrEqual(dimensions.client);
  }
  await testInfo.attach('mobile-width.png', {body: await page.screenshot(), contentType: 'image/png'});
  await testInfo.attach('dimensions', {body: JSON.stringify(dimensions), contentType: 'application/json'});
});

test('cached client reloads news and bookmarks while offline', async ({page, context, browserName, site}, testInfo) => {
  test.skip(browserName !== 'chromium', 'Service Worker verification is scoped to Chromium in this harness.');
  await home(page);
  const saved = await saveFirst(page);
  await readyOffline(page);
  try {
    await context.setOffline(true);
    const response = await page.reload({waitUntil: 'domcontentloaded'});
    expect(response?.fromServiceWorker()).toBe(true);
    await assertSaved(page, saved);
    await expect(page.locator('.snapshot-banner')).toContainText(/缓存|离线/);
    await page.goto(new URL('library', siteURL).href, {waitUntil: 'domcontentloaded'});
    await expect(page.locator('.reading-bookmark').filter({hasText: saved.title})).toBeVisible();
    await testInfo.attach('offline.png', {body: await page.screenshot(), contentType: 'image/png'});
  } finally { await context.setOffline(false); }
});

test('older candidate upgrades on the same origin without losing its bookmark', async ({page, context, browserName, site}, testInfo) => {
  test.skip(browserName !== 'chromium', 'Service Worker verification is scoped to Chromium in this harness.');
  await site.switchTo('baseline');
  await home(page);
  await expect(page.locator('script[type="module"][src]').first()).toHaveAttribute('src', site.data.baseline.entry);
  const saved = await saveFirst(page);
  await readyOffline(page);
  await site.switchTo('candidate');
  await page.evaluate(async () => { await (await navigator.serviceWorker.ready).update(); });
  await expect.poll(() => page.evaluate(async entry => {
    for (const name of await caches.keys()) {
      if (await (await caches.open(name)).match(new URL(entry, location.href).href)) return true;
    }
    return false;
  }, site.data.candidate.entry)).toBe(true);
  await page.reload({waitUntil: 'domcontentloaded'});
  await expect(page.locator('script[type="module"][src]').first()).toHaveAttribute('src', site.data.candidate.entry);
  await assertSaved(page, saved);
  await readyOffline(page);
  try {
    await context.setOffline(true);
    const response = await page.reload({waitUntil: 'domcontentloaded'});
    expect(response?.fromServiceWorker()).toBe(true);
    await expect(page.locator('script[type="module"][src]').first()).toHaveAttribute('src', site.data.candidate.entry);
    await assertSaved(page, saved);
  } finally { await context.setOffline(false); }
  await testInfo.attach('upgrade-pair', {body: JSON.stringify({
    from: site.data.baseline, to: site.data.candidate,
    trigger: 'registration.update followed by reload; no forced skipWaiting or cleared client storage',
    snapshot_id: site.data.snapshot_id,
    limitation: 'One real older M5 candidate, not an exhaustive legacy-version matrix or physical device.',
  }), contentType: 'application/json'});
});

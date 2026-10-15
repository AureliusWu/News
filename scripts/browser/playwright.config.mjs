import {defineConfig} from '@playwright/test';
import {join} from 'node:path';
import {output, requireIsolatedCI, siteURL} from './server.mjs';

requireIsolatedCI();
export default defineConfig({
  testDir: '.', testMatch: 'acceptance.spec.mjs',
  fullyParallel: false, workers: 1, retries: 0,
  timeout: 90000, globalTimeout: 10 * 60 * 1000,
  expect: {timeout: 20000},
  outputDir: join(output, 'test-results'),
  reporter: [['line'], ['json', {outputFile: join(output, 'playwright.json')}],
    ['html', {outputFolder: join(output, 'playwright-report'), open: 'never'}]],
  use: {baseURL: siteURL, viewport: {width: 1350, height: 940},
    trace: 'retain-on-failure', screenshot: 'only-on-failure', serviceWorkers: 'allow'},
  projects: [
    {name: 'chrome', use: {browserName: 'chromium', channel: 'chrome', launchOptions: {chromiumSandbox: true}}},
    {name: 'firefox', use: {browserName: 'firefox'}},
  ],
});

import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';

test.use({ trace: 'off', screenshot: 'off' });

let cloudSession: { url: string; token: string } | undefined;
test.afterEach(async () => {
  if (!cloudSession) return;
  const { url, token } = cloudSession;
  cloudSession = undefined;
  const response = await fetch(`${url}/api/auth/session`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
  expect(response.ok).toBe(true);
});

test('real Azure reader preserves its synthetic processed post after reload', async ({ page }, testInfo) => {
  const parametersPath = process.env.SIGNAL_CLOUD_PARAMETERS;
  test.skip(!parametersPath, 'Requires protected deployment parameters and an explicitly configured cloud preview.');
  const parameters = JSON.parse(readFileSync(parametersPath!, 'utf8').replace(/^\uFEFF/, ''));
  const outputs = JSON.parse(readFileSync(parametersPath!.replace(/\.parameters\.json$/, '.outputs.json'), 'utf8').replace(/^\uFEFF/, ''));
  const response = await fetch(`${outputs.applicationUrl.value}/api/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ secret: parameters.parameters.loginSecret.value }),
  });
  expect(response.ok).toBe(true);
  const { token } = await response.json() as { token: string };
  cloudSession = { url: outputs.applicationUrl.value, token };
  await page.addInitScript(token => {
    localStorage.setItem('signal-mode', 'live');
    sessionStorage.setItem('signal-session', token);
  }, token);
  page.on('requestfailed', request => {
    const url = new URL(request.url());
    console.error(`Request failed: ${url.origin}${url.pathname}: ${request.failure()?.errorText}`);
  });
  await page.goto('/settings');
  await expect.poll(() => page.evaluate(async () => {
    const fonts = await Promise.all(['ionicons', 'material-community'].map(family => document.fonts.load(`16px "${family}"`)));
    return fonts.every(faces => faces.length > 0 && faces.every(face => face.status === 'loaded'));
  })).toBe(true);
  await expect(page.getByText('Signed in. Your session is stored securely on iOS.', { exact: true })).toBeVisible();
  const discoverTab = page.getByRole('tab', { name: /Discover/ });
  if (await discoverTab.count()) await discoverTab.click();
  else await page.getByTestId('button').and(page.getByRole('button', { name: 'Discover', exact: true })).click();
  await page.getByLabel('Search posts', { exact: true }).fill('SYNTHETIC DEPLOYMENT VERIFICATION');
  await expect(page.getByText('1 insight', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: /^Read / }).first().click();
  await expect(page.getByText('THE ORIGINAL POST', { exact: true })).toBeVisible();
  await expect(page.getByText('[SYNTHETIC DEPLOYMENT VERIFICATION - not a LinkedIn post]', { exact: false })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.reload();
  await expect(page.getByText('THE ORIGINAL POST', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Saved', exact: true }).last()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Mark unread', exact: true })).toBeVisible();
  const screenshot = testInfo.outputPath('azure-reader.png');
  await page.screenshot({ path: screenshot });
  await testInfo.attach('Real Azure reader with labeled synthetic content', { path: screenshot, contentType: 'image/png' });
});

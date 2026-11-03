import { expect, test, type Page } from '@playwright/test';
import posts from '../assets/posts.json';

async function navigate(page: Page, name: string) {
  const tab = page.getByRole('tab', { name: new RegExp(name) });
  if (await tab.count()) await tab.click();
  else await page.getByRole('button', { name, exact: true }).click();
}

function chip(page: Page, name: string) {
  return page.getByTestId('chip').and(page.getByRole('button', { name, exact: true }));
}

async function savedCount(page: Page) {
  return page.evaluate(() => {
    const data = JSON.parse(localStorage.getItem('signal-demo') || '{}') as { posts?: { saved: boolean }[] };
    return data.posts?.filter(post => post.saved).length;
  });
}

async function expectNoOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('signal-mode', 'demo'));
  await page.goto('/');
  await expect(page.getByText('Less noise. More signal.', { exact: true })).toBeVisible();
  await expect.poll(() => savedCount(page)).toBe(posts.filter(post => post.saved).length);
  await page.evaluate(async () => { await document.fonts.ready; });
  const loadedFonts = await page.evaluate(() => {
    const families: string[] = [];
    document.fonts.forEach(font => { if (font.status === 'loaded') families.push(font.family); });
    return families;
  });
  expect(loadedFonts).toEqual(expect.arrayContaining(['ionicons', 'material-community']));
});

test('phone layout, navigation and bookmark touch targets', async ({ page }, testInfo) => {
  const viewport = page.viewportSize()!;
  expect(await page.evaluate(() => ({ width: innerWidth, height: innerHeight }))).toEqual(viewport);
  expect(await page.evaluate(() => devicePixelRatio)).toBe(3);
  await expectNoOverflow(page);
  if (viewport.width === 428) await expect(page.getByRole('tab')).toHaveCount(5);
  else await expect(page.getByRole('button', { name: 'Today', exact: true })).toBeVisible();
  const bookmarks = page.getByRole('button', { name: /^(Save post|Remove bookmark)$/ });
  await expect(bookmarks).toHaveCount(posts.length);
  for (const bookmark of await bookmarks.all()) {
    const bounds = await bookmark.boundingBox();
    expect(bounds?.width).toBeGreaterThanOrEqual(44);
    expect(bounds?.height).toBeGreaterThanOrEqual(44);
  }
  const screenshot = testInfo.outputPath('today.png');
  await page.screenshot({ path: screenshot });
  await testInfo.attach('Today', { path: screenshot, contentType: 'image/png' });
  await page.getByRole('button', { name: 'Search insights', exact: true }).tap();
  await expect(page.getByLabel('Search posts', { exact: true })).toBeVisible();
});

test('Today filters and bookmarks persist across reloads', async ({ page }) => {
  const initial = posts.filter(post => post.saved).length;
  await chip(page, 'Saved').click();
  await expect(page.getByText(`${initial} insights`, { exact: true })).toBeVisible();
  await chip(page, 'Latest').click();
  await expect(page.getByText(`${posts.length} insights`, { exact: true })).toBeVisible();
  await chip(page, 'For you').click();
  await page.getByRole('button', { name: 'Save post', exact: true }).first().click();
  await expect.poll(() => savedCount(page)).toBe(initial + 1);
  await page.reload();
  await expect.poll(() => savedCount(page)).toBe(initial + 1);
  await expect(page.getByRole('button', { name: 'Remove bookmark', exact: true })).toHaveCount(initial + 1);
  await navigate(page, 'Saved');
  await expect(page.getByText(`${initial + 1} insights · Saved content survives feed cleanup`, { exact: true })).toBeVisible();
});

test('search, empty state and clearing search', async ({ page }) => {
  await navigate(page, 'Discover');
  const search = page.getByLabel('Search posts', { exact: true });
  await search.fill('RAG');
  await expect(page.getByText('1 insight', { exact: true })).toBeVisible();
  await search.fill('signal-no-match-184');
  await expect(page.getByText('0 insights', { exact: true })).toBeVisible();
  await expect(page.getByText('No matching posts. Adjust your filters or import a LinkedIn export.', { exact: true })).toBeVisible();
  await search.fill('');
  await expect(page.getByText('4 insights', { exact: true })
    .and(page.locator(':not([aria-hidden="true"] *)'))).toBeVisible();
  await expectNoOverflow(page);
});

test('topic cards, reader and demo explanations', async ({ page }) => {
  await navigate(page, 'Discover');
  await navigate(page, 'Topics');
  await page.getByRole('button', { name: 'Explore RAG', exact: true }).click();
  await expect(page).toHaveURL(/\/discover\?topic=RAG$/);
  await expect(page.getByText('1 insight', { exact: true })).toBeVisible();
  const post = posts.find(post => post.id === 'demo-rag')!;
  await page.getByRole('button', { name: `Read ${post.insight.title}`, exact: true }).first().click();
  await expect(page).toHaveURL(/\/post\/demo-rag$/);
  await expect(page.getByText('THE ORIGINAL POST', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Explain this to me', exact: true }).click();
  await expect(page.getByText('AI-GENERATED EXPLANATIONS', { exact: true })).toBeVisible();
  await expectNoOverflow(page);
  await page.getByRole('button', { name: 'Back to your reading', exact: true }).click();
  await expect(page).toHaveURL(/\/discover\?topic=RAG$/);
});

test('dark mode and large reading text', async ({ page }) => {
  await navigate(page, 'Settings');
  await chip(page, 'dark').click();
  await chip(page, 'large').click();
  await navigate(page, 'Today');
  const post = posts[0]!;
  await page.getByRole('button', { name: `Read ${post.insight.title}`, exact: true }).first().click();
  const original = page.getByText(post.original_text, { exact: true });
  await expect(original).toHaveCSS('font-size', '19px');
  await expect(original).toHaveCSS('line-height', '31px');
  await expect(original).toHaveCSS('color', 'rgb(245, 232, 235)');
  await expectNoOverflow(page);
});

test('source gallery, uncropped images, failures and retry', async ({ page }) => {
  const urls = ['https://signal-e2e.invalid/one.svg', 'https://signal-e2e.invalid/two.svg', 'https://signal-e2e.invalid/retry.svg'];
  let retryReady = false;
  await page.route('https://signal-e2e.invalid/**', async route => {
    if (route.request().url() === urls[2] && !retryReady) {
      await route.fulfill({ status: 404, body: 'Test fixture: image unavailable' });
      return;
    }
    const portrait = route.request().url() === urls[1];
    await route.fulfill({
      contentType: 'image/svg+xml',
      body: `<svg xmlns="http://www.w3.org/2000/svg" width="${portrait ? 600 : 800}" height="${portrait ? 900 : 450}"><rect width="100%" height="100%" fill="#D71920"/></svg>`,
    });
  });
  await page.evaluate(imageUrls => {
    const data = JSON.parse(localStorage.getItem('signal-demo')!);
    data.posts[0].image_urls = imageUrls;
    localStorage.setItem('signal-demo', JSON.stringify(data));
  }, urls);
  await page.reload();
  const post = posts[0]!;
  await page.getByRole('button', { name: `Read ${post.insight.title}`, exact: true }).first().click();
  for (const [index, width] of [[1, 800], [2, 600]]) {
    const image = page.getByRole('img', { name: `Source image ${index} of 3 for ${post.insight.title}`, exact: true });
    await image.scrollIntoViewIfNeeded();
    await expect(image).toHaveJSProperty('naturalWidth', width);
    await expect(image).toHaveCSS('object-fit', 'contain');
  }
  await page.getByText('THE ORIGINAL POST', { exact: true }).scrollIntoViewIfNeeded();
  await expect(page.getByText('Source image unavailable. The link may have expired.', { exact: true })).toBeVisible();
  retryReady = true;
  await page.getByRole('button', { name: 'Retry source image', exact: true }).click();
  const restored = page.getByRole('img', { name: `Source image 3 of 3 for ${post.insight.title}`, exact: true });
  await expect(restored).toHaveJSProperty('naturalWidth', 800);
  await expectNoOverflow(page);
});

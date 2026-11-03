import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.SIGNAL_E2E_URL || 'http://localhost:8081',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'iphone-13-pro-max',
      use: { ...devices['iPhone 13 Pro Max'], viewport: { width: 428, height: 926 } },
    },
    {
      name: 'iphone-13-pro-max-landscape',
      use: { ...devices['iPhone 13 Pro Max'], viewport: { width: 926, height: 428 } },
    },
  ],
  webServer: process.env.SIGNAL_E2E_URL ? undefined : {
    command: 'npx expo start --web --localhost --port 8081',
    url: 'http://localhost:8081',
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});

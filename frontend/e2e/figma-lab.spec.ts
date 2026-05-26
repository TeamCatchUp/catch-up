import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { FIGMA_LAB_CASES } from '../src/app/(dev)/figma-lab/_registry/cases';

function isKnownDevHarnessNoise(message: string) {
  return message === 'Failed to load resource: net::ERR_NETWORK_ACCESS_DENIED' || message === 'Event';
}

function collectBrowserErrors(page: Page) {
  const browserErrors: string[] = [];

  page.on('console', (message) => {
    if (message.type() === 'error' && !isKnownDevHarnessNoise(message.text())) {
      browserErrors.push(message.text());
    }
  });
  page.on('pageerror', (error) => {
    if (!isKnownDevHarnessNoise(error.message)) {
      browserErrors.push(error.message);
    }
  });

  return browserErrors;
}

test.describe('figma lab', () => {
  test('renders the empty registry state without browser errors', async ({ page }) => {
    const browserErrors = collectBrowserErrors(page);

    await page.goto('/figma-lab');

    await expect(page.getByText('Figma Lab', { exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: '등록된 Figma Lab case가 없습니다' })).toBeVisible();
    expect(browserErrors).toEqual([]);
  });

  test('renders every registered case without browser errors', async ({ page }) => {
    const browserErrors = collectBrowserErrors(page);

    for (const item of FIGMA_LAB_CASES) {
      await page.goto(`/figma-lab?case=${item.id}`);
      await expect(page.getByRole('heading', { name: item.title })).toBeVisible();

      if (item.kind === 'page' && item.targetRoute) {
        const response = await page.goto(item.targetRoute);
        expect(response?.ok(), `${item.id} targetRoute should load successfully`).toBe(true);
      }
    }

    expect(browserErrors).toEqual([]);
  });
});

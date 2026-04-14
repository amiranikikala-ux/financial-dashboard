import { test, expect } from '@playwright/test';
import { mockApiRoutes } from './helpers/api-mock.js';

test.describe('Refresh Button', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page);
    await page.goto('/');
    await expect(page.locator('h1')).toBeVisible();
  });

  test('refresh button exists and is enabled', async ({ page }) => {
    const btn = page.locator('.btn-refresh');
    await expect(btn).toBeVisible();
    await expect(btn).toBeEnabled();
    await expect(btn).toContainText('განახლება');
  });

  test('clicking refresh triggers POST /api/refresh', async ({ page }) => {
    let refreshCalled = false;
    await page.route('**/api/refresh', async (route) => {
      refreshCalled = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'started', message: 'Pipeline started' }),
      });
    });

    await page.locator('.btn-refresh').click();
    await page.waitForTimeout(500);
    expect(refreshCalled).toBe(true);
  });

  test('data age label is displayed', async ({ page }) => {
    const ageLabel = page.locator('.refresh-age');
    await expect(ageLabel).toBeVisible();
    await expect(ageLabel).toContainText('წინ');
  });
});

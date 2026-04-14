import { test, expect } from '@playwright/test';
import { mockApiError } from './helpers/api-mock.js';
import { MOCK_SUPPLIERS, MOCK_STATUS } from './helpers/mock-data.js';

test.describe('API Error Handling', () => {
  test('shows error banner on API failure', async ({ page }) => {
    await mockApiError(page, 500);
    await page.goto('/');

    const errorBanner = page.locator('[role="alert"]');
    await expect(errorBanner).toBeVisible({ timeout: 10_000 });
    await expect(errorBanner).toContainText('შეცდომა');
  });

  test('retry button triggers new API call', async ({ page }) => {
    await mockApiError(page, 500);
    await page.goto('/');
    const errorBanner = page.locator('[role="alert"]');
    await expect(errorBanner).toBeVisible({ timeout: 10_000 });

    const retryBtn = errorBanner.locator('button', { hasText: 'თავიდან ცდა' });
    await expect(retryBtn).toBeVisible();

    const [request] = await Promise.all([
      page.waitForRequest((req) => req.url().includes('/api/data')),
      retryBtn.click(),
    ]);

    expect(request.url()).toContain('/api/data');
  });
});

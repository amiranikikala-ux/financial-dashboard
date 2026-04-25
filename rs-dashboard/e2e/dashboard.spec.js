import { test, expect } from '@playwright/test';
import { mockApiRoutes } from './helpers/api-mock.js';

test.describe('Dashboard — Load & Header', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page);
    await page.goto('/');
  });

  test('page loads with correct title', async ({ page }) => {
    await expect(page.locator('h1.brand-name')).toHaveText('ჯეო ფუდთაიმი');
  });

  test('header shows period picker when data loaded', async ({ page }) => {
    // .header-period-badge was replaced by DateTimeCalendarPicker (Packet F).
    // The new trigger shows "ყველა პერიოდი" by default, with a 📅 icon.
    const trigger = page.locator('.dtcp-trigger').first();
    await expect(trigger).toBeVisible();
    await expect(trigger).toContainText('ყველა პერიოდი');
  });

  test('header stats show bank and paid totals', async ({ page }) => {
    await expect(page.locator('.header-stats-compact')).toBeVisible();
    await expect(page.locator('.header-stats-compact')).toContainText('ბანკი');
  });

  test('refresh button is visible in header', async ({ page }) => {
    await expect(page.locator('.refresh-status')).toBeVisible();
    await expect(page.locator('.btn-refresh')).toBeVisible();
  });

  test('refresh button shows data age', async ({ page }) => {
    await expect(page.locator('.refresh-age')).toBeVisible();
    await expect(page.locator('.refresh-age')).toContainText('წინ');
  });

  test('default tab is suppliers', async ({ page }) => {
    await expect(page.locator('.tab-btn.active')).toContainText('მომწოდებლები');
  });

  test('loading state disappears after data loads', async ({ page }) => {
    await expect(page.locator('.loading')).not.toBeVisible();
  });
});

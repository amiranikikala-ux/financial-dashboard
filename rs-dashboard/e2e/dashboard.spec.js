import { test, expect } from '@playwright/test';
import { mockApiRoutes } from './helpers/api-mock.js';

test.describe('Dashboard — Load & Header', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page);
    await page.goto('/');
  });

  test('page loads with correct title', async ({ page }) => {
    await expect(page.locator('h1')).toHaveText('RS Dashboard');
  });

  test('subtitle is visible', async ({ page }) => {
    await expect(page.locator('.subtitle')).toContainText('ფინანსური ანალიზი');
  });

  test('header shows period badge when data loaded', async ({ page }) => {
    await expect(page.locator('.header-period-badge')).toBeVisible();
    await expect(page.locator('.header-period-badge')).toContainText('2025');
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

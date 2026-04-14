import { test, expect } from '@playwright/test';
import { mockApiRoutes } from './helpers/api-mock.js';

test.describe('Supplier Modal', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page);
    await page.goto('/');
    await expect(page.locator('h1')).toBeVisible();
  });

  test('supplier table rows are visible', async ({ page }) => {
    const rows = page.locator('.table-premium tbody tr');
    await expect(rows).toHaveCount(2);
  });

  test('clicking supplier row opens modal', async ({ page }) => {
    const firstRow = page.locator('.table-premium tbody tr').first();
    await firstRow.click();
    const modal = page.locator('[role="dialog"]');
    await expect(modal).toBeVisible({ timeout: 5000 });
  });

  test('modal displays supplier name', async ({ page }) => {
    const firstRow = page.locator('.table-premium tbody tr').first();
    await firstRow.click();
    const title = page.locator('#supplier-modal-title');
    await expect(title).toBeVisible();
    await expect(title).toContainText('მეორე მომწოდებელი');
  });

  test('modal displays tax ID', async ({ page }) => {
    const firstRow = page.locator('.table-premium tbody tr').first();
    await firstRow.click();
    const taxIdEl = page.locator('.supplier-modal-taxid');
    await expect(taxIdEl.first()).toContainText('222222222');
  });

  test('modal displays 3 KPI cards', async ({ page }) => {
    const firstRow = page.locator('.table-premium tbody tr').first();
    await firstRow.click();
    const kpis = page.locator('.supplier-modal-kpi');
    await expect(kpis).toHaveCount(3);
  });

  test('modal KPI labels are correct', async ({ page }) => {
    const firstRow = page.locator('.table-premium tbody tr').first();
    await firstRow.click();
    await expect(page.locator('.kpi-label').nth(0)).toContainText('რეალური ჯამი');
    await expect(page.locator('.kpi-label').nth(1)).toContainText('სულ გადახდილი');
    await expect(page.locator('.kpi-label').nth(2)).toContainText('დავალიანება');
  });

  test('modal has Payment split section', async ({ page }) => {
    const firstRow = page.locator('.table-premium tbody tr').first();
    await firstRow.click();
    await expect(page.locator('.supplier-modal-section-title', { hasText: 'Payment split' })).toBeVisible();
  });

  test('modal has Aging section', async ({ page }) => {
    const firstRow = page.locator('.table-premium tbody tr').first();
    await firstRow.click();
    await expect(page.locator('.supplier-modal-section-title', { hasText: 'Aging' })).toBeVisible();
  });

  test('modal has Payment Ratio gauge', async ({ page }) => {
    const firstRow = page.locator('.table-premium tbody tr').first();
    await firstRow.click();
    await expect(page.locator('.ratio-gauge')).toBeVisible();
  });

  test('close button (✕) closes modal', async ({ page }) => {
    const firstRow = page.locator('.table-premium tbody tr').first();
    await firstRow.click();
    const modal = page.locator('[role="dialog"]');
    await expect(modal).toBeVisible();

    await page.locator('.supplier-modal-close').click();
    await expect(modal).not.toBeVisible();
  });

  test('bottom "დახურვა" button closes modal', async ({ page }) => {
    const firstRow = page.locator('.table-premium tbody tr').first();
    await firstRow.click();
    const modal = page.locator('[role="dialog"]');
    await expect(modal).toBeVisible();

    await page.locator('.supplier-modal-close-btn').click();
    await expect(modal).not.toBeVisible();
  });

  test('Escape key closes modal', async ({ page }) => {
    const firstRow = page.locator('.table-premium tbody tr').first();
    await firstRow.click();
    const modal = page.locator('[role="dialog"]');
    await expect(modal).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(modal).not.toBeVisible();
  });

  test('backdrop click closes modal', async ({ page }) => {
    const firstRow = page.locator('.table-premium tbody tr').first();
    await firstRow.click();
    const modal = page.locator('[role="dialog"]');
    await expect(modal).toBeVisible();

    await page.locator('.supplier-modal-backdrop').click({ position: { x: 10, y: 10 } });
    await expect(modal).not.toBeVisible();
  });

  test('clicking second supplier shows different name', async ({ page }) => {
    const secondRow = page.locator('.table-premium tbody tr').nth(1);
    await secondRow.click();
    const title = page.locator('#supplier-modal-title');
    await expect(title).toContainText('ტესტ მომწოდებელი');
  });

  test('modal shows imported products reference section', async ({ page }) => {
    const firstRow = page.locator('.table-premium tbody tr').first();
    await firstRow.click();
    await expect(
      page.locator('.supplier-modal-section-title', { hasText: /შემოტანილი პროდუქცია|reference/ })
    ).toBeVisible({ timeout: 5000 });
  });

  test('modal shows truth section', async ({ page }) => {
    const firstRow = page.locator('.table-premium tbody tr').first();
    await firstRow.click();
    await expect(
      page.locator('.supplier-modal-section-title', { hasText: 'Strict supplier truth' })
    ).toBeVisible();
  });
});

import { test, expect } from '@playwright/test';
import { mockApiRoutes } from './helpers/api-mock.js';

test.describe('Export Button — Suppliers Tab', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page);
    await page.goto('/');
    await expect(page.locator('h1')).toBeVisible();
  });

  test('Excel download button is visible on suppliers tab', async ({ page }) => {
    const btn = page.locator('.btn-download-xlsx');
    await expect(btn).toBeVisible();
    await expect(btn).toContainText('Excel ჩამოტვირთვა');
  });

  test('Excel download button is enabled when suppliers exist', async ({ page }) => {
    const btn = page.locator('.btn-download-xlsx');
    await expect(btn).toBeEnabled();
  });

  test('CSV download button exists but disabled with no local payments', async ({ page }) => {
    const btn = page.locator('.btn-download-csv');
    await expect(btn).toBeVisible();
    await expect(btn).toBeDisabled();
  });
});

test.describe('Export Button — Analytics Tab', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page);
    await page.goto('/#analytics');
    await expect(page.locator('.tab-btn.active')).toContainText('ანალიტიკა');
  });

  test('ExportButton is visible on analytics tab', async ({ page }) => {
    const btn = page.locator('.btn-download-xlsx');
    await expect(btn).toBeVisible();
    await expect(btn).toContainText('Excel ჩამოტვირთვა');
  });
});

test.describe('Export Button — Ratios Tab', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page);
    await page.goto('/#ratios');
    await expect(page.locator('.tab-btn.active')).toContainText('კოეფ.');
  });

  test('ExportButton is visible on ratios tab', async ({ page }) => {
    const btn = page.locator('.btn-download-xlsx');
    await expect(btn).toBeVisible();
  });
});

test.describe('Export Button — Forecast Tab', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page);
    await page.goto('/#forecast');
    await expect(page.locator('.tab-btn.active')).toContainText('პროგნოზი');
  });

  test('ExportButton is visible on forecast tab', async ({ page }) => {
    const btn = page.locator('.btn-download-xlsx');
    await expect(btn).toBeVisible();
  });
});

test.describe('Export Button — Budget Tab', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page);
    await page.goto('/#budget');
    await expect(page.locator('.tab-btn.active')).toContainText('ბიუჯეტი');
  });

  test('ExportButton is visible on budget tab', async ({ page }) => {
    const btn = page.locator('.btn-download-xlsx');
    await expect(btn).toBeVisible();
  });
});

test.describe('Export Button — Working Capital Tab', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page);
    await page.goto('/#working_capital');
    await expect(page.locator('.tab-btn.active')).toContainText('კაპიტალი');
  });

  test('ExportButton is visible on working capital tab', async ({ page }) => {
    const btn = page.locator('.btn-download-xlsx');
    await expect(btn).toBeVisible();
  });
});

test.describe('Export Button — Retail Sales Tab', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page);
    await page.goto('/#retail_sales');
    await expect(page.locator('.tab-btn.active')).toContainText('გაყიდვები');
  });

  test('ExportButton is visible on retail sales tab', async ({ page }) => {
    const btn = page.locator('.btn-download-xlsx');
    await expect(btn).toBeVisible();
  });
});

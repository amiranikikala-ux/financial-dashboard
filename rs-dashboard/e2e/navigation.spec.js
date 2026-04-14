import { test, expect } from '@playwright/test';
import { mockApiRoutes } from './helpers/api-mock.js';

const TABS = [
  { id: 'suppliers', label: 'მომწოდებლები' },
  { id: 'waybills', label: 'ზედნადებები' },
  { id: 'analytics', label: 'ანალიტიკა' },
  { id: 'cashflow', label: 'ბანკი' },
  { id: 'imported_products', label: 'პროდუქცია' },
  { id: 'retail_sales', label: 'გაყიდვები' },
  { id: 'pnl', label: 'P&L' },
  { id: 'working_capital', label: 'კაპიტალი' },
  { id: 'ratios', label: 'კოეფ.' },
  { id: 'forecast', label: 'პროგნოზი' },
  { id: 'budget', label: 'ბიუჯეტი' },
  { id: 'valuation', label: 'შეფასება' },
  { id: 'executive', label: 'Executive' },
  { id: 'insights', label: 'ინსაითები' },
];

test.describe('Tab Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page);
    await page.goto('/');
    await expect(page.locator('h1')).toBeVisible();
  });

  for (const tab of TABS) {
    test(`clicking "${tab.label}" tab activates it and updates hash`, async ({ page }) => {
      const btn = page.locator('.tab-btn', { hasText: tab.label });
      await btn.click();
      await expect(btn).toHaveClass(/active/);
      expect(page.url()).toContain(`#${tab.id}`);
    });
  }

  test('navigating via URL hash loads correct tab', async ({ page }) => {
    await page.goto('/#analytics');
    await expect(page.locator('.tab-btn.active')).toContainText('ანალიტიკა');
  });

  test('invalid hash falls back to suppliers', async ({ page }) => {
    await page.goto('/#nonexistent');
    await expect(page.locator('.tab-btn.active')).toContainText('მომწოდებლები');
  });

  test('all 14 tabs are rendered', async ({ page }) => {
    const tabButtons = page.locator('.tab-btn');
    await expect(tabButtons).toHaveCount(14);
  });

  test('tab groups are visible', async ({ page }) => {
    await expect(page.locator('.tabs-group-label').first()).toContainText('ყოველდღიური');
    await expect(page.locator('.tabs-group-label').nth(1)).toContainText('ანალიტიკური');
  });
});

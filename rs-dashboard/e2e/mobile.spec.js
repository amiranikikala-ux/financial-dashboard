import { test, expect } from '@playwright/test';
import { mockApiRoutes } from './helpers/api-mock.js';

test.describe('Mobile Navigation', () => {
  test.use({ viewport: { width: 375, height: 812 } });

  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page);
    await page.goto('/');
    await expect(page.locator('h1')).toBeVisible();
  });

  test('bottom nav bar is visible on mobile', async ({ page }) => {
    await expect(page.locator('.mobile-bottom-nav')).toBeVisible();
  });

  test('quick tabs are rendered (4 + "more")', async ({ page }) => {
    const navBtns = page.locator('.mobile-bottom-nav .mobile-nav-btn');
    await expect(navBtns).toHaveCount(5);
  });

  test('clicking quick tab navigates', async ({ page }) => {
    const cashBtn = page.locator('.mobile-nav-btn', { hasText: 'ბანკი' });
    await cashBtn.click();
    expect(page.url()).toContain('#cashflow');
  });

  test('"more" button opens tab sheet', async ({ page }) => {
    const moreBtn = page.locator('.mobile-nav-btn', { hasText: 'სხვა' });
    await moreBtn.click();
    await expect(page.locator('.mobile-nav-sheet')).toBeVisible();
    await expect(page.locator('.mobile-nav-sheet-title')).toContainText('ტაბები');
  });

  test('tab sheet shows all 14 tabs', async ({ page }) => {
    const moreBtn = page.locator('.mobile-nav-btn', { hasText: 'სხვა' });
    await moreBtn.click();
    const gridBtns = page.locator('.mobile-nav-grid-btn');
    await expect(gridBtns).toHaveCount(14);
  });

  test('selecting tab from sheet navigates and closes sheet', async ({ page }) => {
    const moreBtn = page.locator('.mobile-nav-btn', { hasText: 'სხვა' });
    await moreBtn.click();
    const pnlBtn = page.locator('.mobile-nav-grid-btn', { hasText: 'P&L' });
    await pnlBtn.click();
    expect(page.url()).toContain('#pnl');
    await expect(page.locator('.mobile-nav-sheet')).not.toBeVisible();
  });

  test('overlay click closes sheet', async ({ page }) => {
    const moreBtn = page.locator('.mobile-nav-btn', { hasText: 'სხვა' });
    await moreBtn.click();
    await expect(page.locator('.mobile-nav-sheet')).toBeVisible();
    await page.locator('.mobile-nav-overlay').click({ position: { x: 10, y: 10 } });
    await expect(page.locator('.mobile-nav-sheet')).not.toBeVisible();
  });
});

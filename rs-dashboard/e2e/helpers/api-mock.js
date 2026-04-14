import { getMockForTab, MOCK_STATUS } from './mock-data.js';

/**
 * Intercept all /api/* routes and return mock data.
 * Call this at the start of each test to isolate from backend.
 */
export async function mockApiRoutes(page) {
  await page.route('**/api/data**', async (route) => {
    const url = new URL(route.request().url());
    const tab = url.searchParams.get('tab') || 'suppliers';
    const body = getMockForTab(tab);
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
  });

  await page.route('**/api/status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_STATUS),
    });
  });

  await page.route('**/api/refresh', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'started', message: 'Pipeline regeneration started' }),
    });
  });
}

/**
 * Mock API to return errors for testing error handling.
 */
export async function mockApiError(page, statusCode = 500) {
  await page.route('**/api/data**', async (route) => {
    await route.fulfill({
      status: statusCode,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Test error response' }),
    });
  });

  await page.route('**/api/status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_STATUS),
    });
  });
}

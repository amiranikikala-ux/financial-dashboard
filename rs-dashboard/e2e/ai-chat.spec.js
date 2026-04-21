import { test, expect } from '@playwright/test';
import { mockApiRoutes } from './helpers/api-mock.js';

test.describe('AI Chat Assistant — Phase 1 MVP', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page);
    await page.goto('/');
    // Wait for initial data load to finish so ChatAssistant is mounted.
    await expect(page.locator('.loading')).toBeHidden();
  });

  test('floating chat button is visible', async ({ page }) => {
    await expect(page.getByTestId('chat-fab')).toBeVisible();
    await expect(page.getByTestId('chat-panel')).toHaveCount(0);
  });

  test('clicking the chat button opens the panel with welcome content', async ({ page }) => {
    await page.getByTestId('chat-fab').click();
    const panel = page.getByTestId('chat-panel');
    await expect(panel).toBeVisible();
    await expect(panel).toContainText('AI ასისტენტი');
    await expect(panel).toContainText('Claude Sonnet 4.6');
    await expect(panel).toContainText('ფინანსური ასისტენტი');
    await expect(page.getByTestId('chat-input')).toBeVisible();
    await expect(page.getByTestId('chat-send')).toBeDisabled();
  });

  test('sending a message renders user bubble + assistant reply with source attribution', async ({ page }) => {
    await page.getByTestId('chat-fab').click();
    const input = page.getByTestId('chat-input');
    await input.fill('რამდენი მომწოდებელი გვყავს?');
    await expect(page.getByTestId('chat-send')).toBeEnabled();
    await page.getByTestId('chat-send').click();

    // User bubble appears immediately.
    await expect(page.getByTestId('chat-msg-user')).toContainText('რამდენი მომწოდებელი გვყავს?');

    // Assistant bubble renders the mock reply.
    const assistantMsg = page.getByTestId('chat-msg-assistant');
    await expect(assistantMsg).toContainText('ტესტური პასუხი');
    await expect(assistantMsg).toContainText('წყარო: data.json → suppliers');

    // Input is cleared, composer ready for next turn.
    await expect(input).toHaveValue('');

    // Source attribution is present and expandable.
    const sourceToggle = page.locator('.chat-msg__sources-toggle');
    await expect(sourceToggle).toBeVisible();
    await expect(sourceToggle).toContainText('წყაროები (1)');
    await sourceToggle.click();
    await expect(page.locator('.chat-msg__source code').first()).toContainText('data.json:suppliers');

    // Usage badge shows token counts.
    await expect(page.locator('.chat-msg__usage')).toContainText('50in');
    await expect(page.locator('.chat-msg__usage')).toContainText('20out');
  });

  test('Enter submits, Shift+Enter adds newline', async ({ page }) => {
    await page.getByTestId('chat-fab').click();
    const input = page.getByTestId('chat-input');

    // Shift+Enter must not submit.
    await input.fill('line 1');
    await input.press('Shift+Enter');
    await input.type('line 2');
    await expect(input).toHaveValue(/line 1[\s\S]+line 2/);
    await expect(page.getByTestId('chat-msg-user')).toHaveCount(0);

    // Plain Enter submits.
    await input.press('Enter');
    await expect(page.getByTestId('chat-msg-user')).toHaveCount(1);
  });

  test('reset button clears transcript', async ({ page }) => {
    await page.getByTestId('chat-fab').click();
    await page.getByTestId('chat-input').fill('ტესტი');
    await page.getByTestId('chat-send').click();
    await expect(page.getByTestId('chat-msg-assistant')).toBeVisible();

    await page.getByTestId('chat-panel').getByRole('button', { name: 'გასუფთავება' }).click();
    await expect(page.getByTestId('chat-msg-user')).toHaveCount(0);
    await expect(page.getByTestId('chat-msg-assistant')).toHaveCount(0);
    // Welcome samples re-appear on empty state.
    await expect(page.locator('.chat-panel__sample').first()).toBeVisible();
  });

  test('Escape closes the panel', async ({ page }) => {
    await page.getByTestId('chat-fab').click();
    await expect(page.getByTestId('chat-panel')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('chat-panel')).toHaveCount(0);
  });

  test('sample prompt click sends the prompt', async ({ page }) => {
    await page.getByTestId('chat-fab').click();
    const firstSample = page.locator('.chat-panel__sample').first();
    const sampleText = (await firstSample.textContent())?.trim() || '';
    expect(sampleText.length).toBeGreaterThan(0);
    await firstSample.click();
    await expect(page.getByTestId('chat-msg-user')).toContainText(sampleText);
    await expect(page.getByTestId('chat-msg-assistant')).toContainText('ტესტური პასუხი');
  });

  test('chat hook uses streaming endpoint (/api/chat/stream)', async ({ page }) => {
    const streamRequests = [];
    page.on('request', (req) => {
      if (req.url().includes('/api/chat/stream')) {
        streamRequests.push({
          url: req.url(),
          method: req.method(),
          contentType: req.headers()['content-type'] || '',
        });
      }
    });

    await page.getByTestId('chat-fab').click();
    await page.getByTestId('chat-input').fill('streaming smoke');
    await page.getByTestId('chat-send').click();

    await expect(page.getByTestId('chat-msg-assistant')).toContainText('ტესტური პასუხი');
    // Final reply must include the streamed chunks concatenated.
    await expect(page.getByTestId('chat-msg-assistant')).toContainText('streaming smoke');

    expect(streamRequests.length).toBe(1);
    expect(streamRequests[0].method).toBe('POST');
    expect(streamRequests[0].contentType).toContain('application/json');
  });

  test('Investigate toggle sends mode=investigate and renders Cascade copy block', async ({ page }) => {
    // Clear any persisted mode from a prior spec/run so the toggle starts OFF.
    await page.addInitScript(() => {
      try {
        window.localStorage.removeItem('ai-advisor-mode');
      } catch {
        /* no-op */
      }
    });
    await page.reload();
    await expect(page.locator('.loading')).toBeHidden();

    const streamBodies = [];
    page.on('request', (req) => {
      if (req.url().includes('/api/chat/stream')) {
        streamBodies.push(req.postData() || '');
      }
    });

    await page.getByTestId('chat-fab').click();

    // Toggle visible + default OFF (chat mode).
    const toggle = page.getByTestId('chat-mode-toggle');
    await expect(toggle).toBeVisible();
    await expect(toggle).toHaveAttribute('aria-pressed', 'false');
    await expect(toggle).toHaveAttribute('data-mode', 'chat');

    // Activate Investigate mode.
    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-pressed', 'true');
    await expect(toggle).toHaveAttribute('data-mode', 'investigate');

    // Send a message in investigate mode.
    await page.getByTestId('chat-input').fill('ზედნადები Excel vs data.json');
    await page.getByTestId('chat-send').click();

    // Request body must include mode=investigate.
    await expect.poll(() => streamBodies.length).toBeGreaterThan(0);
    const parsedBody = JSON.parse(streamBodies[0] || '{}');
    expect(parsedBody.mode).toBe('investigate');
    expect(parsedBody.message).toBe('ზედნადები Excel vs data.json');

    // Assistant bubble renders the Cascade brief mock.
    const assistant = page.getByTestId('chat-msg-assistant');
    await expect(assistant).toContainText('აღმოჩენა');
    await expect(assistant).toHaveAttribute('data-mode', 'investigate');

    // Cascade copy-paste block appears with toggle + copy button + body text.
    const cascade = page.getByTestId('chat-msg-cascade');
    await expect(cascade).toBeVisible();
    const cascadeBody = page.getByTestId('chat-msg-cascade-body');
    await expect(cascadeBody).toContainText('ფაილი: dashboard_pipeline/supplier_matching.py');
    await expect(cascadeBody).toContainText('ხაზი: 142');
    await expect(cascadeBody).toContainText('გასწორება:');

    // Copy button exists and is clickable (clipboard write may be denied in
    // headless Chromium; we assert on button presence + clickability rather
    // than on clipboard contents for cross-platform reliability).
    const copyBtn = page.getByTestId('chat-msg-cascade-copy');
    await expect(copyBtn).toBeVisible();
    await expect(copyBtn).toBeEnabled();

    // localStorage persists the investigate preference.
    const stored = await page.evaluate(() => window.localStorage.getItem('ai-advisor-mode'));
    expect(stored).toBe('investigate');
  });
});

test.describe('AI Chat FAB — tab-switch resilience regression', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page);
    await page.goto('/');
    await expect(page.locator('.loading')).toBeHidden();
  });

  // Regression guard: the FAB used to intermittently disappear after switching
  // tabs because ChatAssistant was lazy-loaded behind a `<Suspense fallback={null}>`
  // boundary. A slow/missed chunk fetch (Vite HMR, network blip, cache miss)
  // would render the null fallback and leave the user with no chat access
  // until a full page refresh. Fix: eager import — see App.jsx comment block.
  // This test hardens the contract by visiting every major hash route in sequence
  // and re-asserting FAB visibility after each navigation.
  test('FAB stays visible across all tab hash routes without refresh', async ({ page }) => {
    const hashes = [
      '#suppliers',
      '#waybills',
      '#pnl',
      '#working_capital',
      '#ratios',
      '#forecast',
      '#budget',
      '#valuation',
      '#executive',
      '#retail_sales',
      '#imported_products',
      '#dead_stock',
      '#debt_plan',
      '#cashflow',
      '#insights',
      '#analytics',
      '#suppliers', // back to the tab the user originally reported
    ];

    for (const hash of hashes) {
      await page.evaluate((h) => {
        window.location.hash = h;
      }, hash);
      // No hard navigation — just a hash change; the FAB must remain mounted.
      await expect(
        page.getByTestId('chat-fab'),
        `FAB disappeared on ${hash}`,
      ).toBeVisible();
    }
  });

  test('FAB remains visible while global loading spinner is showing', async ({ page }) => {
    // The FAB now lives outside the `showGlobalLoading` ternary, so it must
    // be visible even before initial data finishes loading. This guards the
    // "first paint" case where the user has not seen any tab content yet.
    await page.goto('/#suppliers');
    await expect(page.getByTestId('chat-fab')).toBeVisible();
  });
});

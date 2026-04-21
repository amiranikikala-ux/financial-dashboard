import { getMockForTab, MOCK_STATUS } from './mock-data.js';

/**
 * Build a deterministic mock reply for chat vs investigate mode. Chat mode
 * preserves the legacy string so existing ai-chat E2E tests pass unchanged.
 * Investigate mode returns a Cascade-brief-shaped response (fenced ```text```
 * block whose first line is `ფაილი:` + `ხაზი:` + `გასწორება:`) matching the
 * investigator prompt contract.
 */
function buildMockReply(userMessage, mode) {
  if (mode === 'investigate') {
    return [
      `🔍 აღმოჩენა: "${userMessage}" — ტესტური შეუსაბამობა.`,
      '',
      '📊 შედარება: Excel რიგი 14, data.json რიგი 12.',
      '',
      '🔎 მიზეზი: regex გამოტოვებს 9-ნიშნა TIN-ებს.',
      '',
      '📋 Cascade-ისთვის (copy-paste):',
      '```text',
      'ფაილი: dashboard_pipeline/supplier_matching.py',
      'ხაზი: 142',
      'პრობლემა: regex გამოტოვებს 9-ნიშნა TIN-ებს',
      'გასწორება: r\'^\\d{11}$\' → r\'^\\d{9}(\\d{2})?$\'',
      'ტესტი: tests/test_supplier_matching.py — ახალი 9-ნიშნა case',
      '```',
    ].join('\n');
  }
  return `ტესტური პასუხი: "${userMessage}" (წყარო: data.json → suppliers)`;
}

function buildMockSources(mode) {
  const baseSources = [
    {
      tool: 'read_data_json',
      arguments: { section: 'suppliers', limit: 2 },
      result_summary: {
        ok: true,
        section: 'suppliers',
        source: 'data.json:suppliers',
        row_count: 2,
        total_count: 2,
        truncated: false,
      },
    },
  ];
  if (mode === 'investigate') {
    baseSources.push({
      tool: 'validate_vs_source',
      arguments: { section: 'suppliers' },
      result_summary: {
        ok: true,
        section: 'suppliers',
        source: 'validate_vs_source:suppliers',
        status: 'mismatch',
      },
    });
  }
  return baseSources;
}

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

  await page.route('**/api/chat', async (route) => {
    let payload = {};
    try {
      payload = JSON.parse(route.request().postData() || '{}');
    } catch {
      payload = {};
    }
    const userMessage = typeof payload.message === 'string' ? payload.message : '';
    const requestedMode =
      typeof payload.mode === 'string' && payload.mode.trim()
        ? payload.mode.trim().toLowerCase()
        : 'chat';
    const mode = requestedMode === 'investigate' ? 'investigate' : 'chat';
    const reply = buildMockReply(userMessage, mode);
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        reply,
        sources: buildMockSources(mode),
        usage: {
          input_tokens: 50,
          output_tokens: 20,
          model: 'claude-sonnet-4-6',
          stop_reason: 'end_turn',
          mode,
        },
        history: [
          { role: 'user', content: userMessage },
          { role: 'assistant', content: [{ type: 'text', text: reply }] },
        ],
      }),
    });
  });

  await page.route('**/api/chat/stream', async (route) => {
    let payload = {};
    try {
      payload = JSON.parse(route.request().postData() || '{}');
    } catch {
      payload = {};
    }
    const userMessage = typeof payload.message === 'string' ? payload.message : '';
    const requestedMode =
      typeof payload.mode === 'string' && payload.mode.trim()
        ? payload.mode.trim().toLowerCase()
        : 'chat';
    const mode = requestedMode === 'investigate' ? 'investigate' : 'chat';
    const reply = buildMockReply(userMessage, mode);

    // Simulate streaming by splitting the reply into three chunks.
    const splitPoint1 = Math.floor(reply.length / 3);
    const splitPoint2 = Math.floor((2 * reply.length) / 3);
    const chunks = [
      reply.slice(0, splitPoint1),
      reply.slice(splitPoint1, splitPoint2),
      reply.slice(splitPoint2),
    ];

    const sources = buildMockSources(mode);
    const usage = {
      input_tokens: 50,
      output_tokens: 20,
      cache_creation_input_tokens: 0,
      cache_read_input_tokens: 0,
      model: 'claude-sonnet-4-6',
      stop_reason: 'end_turn',
      mode,
    };
    const history = [
      { role: 'user', content: userMessage },
      { role: 'assistant', content: [{ type: 'text', text: reply }] },
    ];

    const events = [
      ...chunks
        .filter((c) => c.length > 0)
        .map((c) => ({ type: 'delta', text: c })),
      { type: 'sources', sources },
      { type: 'usage', usage },
      { type: 'history', history },
      { type: 'done', reply, stop_reason: 'end_turn' },
    ];

    const body = events
      .map((ev) => `event: ${ev.type}\ndata: ${JSON.stringify(ev)}\n\n`)
      .join('');

    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body,
      headers: {
        'Cache-Control': 'no-cache',
        'Content-Type': 'text/event-stream',
      },
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

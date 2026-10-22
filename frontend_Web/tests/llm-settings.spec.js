import { test, expect } from '@playwright/test';

test('missing model configuration disables paid connection test', async ({ page }) => {
  let modelCalls = 0;
  await page.route('**/api/**', route => {
    if (new URL(route.request().url()).pathname === '/api/auth/me') return route.fulfill({json:{id:'mock-user',email:'test@example.test',display_name:'Test user',workspaces:[{id:'mock-workspace',name:'Test workspace',role:'owner'}]}});
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/llm/test') modelCalls++;
    const data = path === '/api/health' ? { service: 'ready', database: 'ready' }
      : { configured: false, api_key_configured: false, missing: ['LLM_API_KEY', 'LLM_MODEL'] };
    return route.fulfill({ json: data });
  });
  await page.goto('/settings');
  const panel = page.getByRole('region', { name: 'LLM 接入' });
  await expect(panel).toContainText('尚未配置完成');
  await expect(panel).toContainText('LLM_API_KEY、LLM_MODEL');
  await expect(panel.getByRole('button', { name: '测试模型连接' })).toBeDisabled();
  expect(modelCalls).toBe(0);
});

test('model calls require a click and a later failure clears previous success', async ({ page }) => {
  let modelCalls = 0;
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/**', route => {
    if (new URL(route.request().url()).pathname === '/api/auth/me') return route.fulfill({json:{id:'mock-user',email:'test@example.test',display_name:'Test user',workspaces:[{id:'mock-workspace',name:'Test workspace',role:'owner'}]}});
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/health') return route.fulfill({ json: { service: 'ready', database: 'ready' } });
    if (path === '/api/llm/status') return route.fulfill({ json: {
      configured: true, api_key_configured: true, model: 'team-model',
      base_url: 'https://provider.example/v1', missing: [], error: null
    } });
    if (path === '/api/llm/test') {
      expect(route.request().method()).toBe('POST');
      modelCalls++;
      return modelCalls === 1
        ? route.fulfill({ json: { ok: true, model: 'team-model', content: 'OK', usage: { total_tokens: 9 } } })
        : route.fulfill({ status: 429, json: { detail: '模型服务限流或额度不足' } });
    }
    return route.fulfill({ json: [] });
  });
  await page.goto('/settings');
  const panel = page.getByRole('region', { name: 'LLM 接入' });
  const button = panel.getByRole('button', { name: '测试模型连接' });
  await expect(button).toBeEnabled();
  expect(modelCalls).toBe(0);
  await expect(panel).toContainText('team-model');
  await button.click();
  await expect(panel.getByRole('status')).toContainText('连接成功');
  await expect(panel.getByRole('status')).toContainText('9 tokens');
  await button.click();
  await expect(panel).toContainText('模型服务限流或额度不足');
  await expect(panel.getByRole('status')).toHaveCount(0);
  expect(modelCalls).toBe(2);
  expect(errors).toEqual([]);
});

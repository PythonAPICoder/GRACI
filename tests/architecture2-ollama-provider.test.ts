import { describe, expect, it, vi } from 'vitest';
import { OllamaModelProvider, type ModelProviderFetch } from '../src/architecture2/providers/index.js';

function response(status: number, body: unknown) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

function provider(fetch: ModelProviderFetch, timeoutMs = 50) {
  return new OllamaModelProvider({ endpoint: 'http://ollama.test:11434/', timeoutMs, fetch });
}

describe('Architecture 2 Ollama model provider', () => {
  it('inspects health and version', async () => {
    const fetch = vi.fn(async () => response(200, { version: '0.11.4' }));
    await expect(provider(fetch).inspectHealth()).resolves.toEqual({ status: 'success', value: { version: '0.11.4' } });
    expect(fetch).toHaveBeenCalledWith('http://ollama.test:11434/api/version', expect.objectContaining({ method: 'GET' }));
  });

  it('inspects model inventory', async () => {
    const fetch = vi.fn(async () => response(200, { models: [{ name: 'qwen:latest', modified_at: '2026-08-13T00:00:00Z', size: 42, digest: 'abc' }] }));
    await expect(provider(fetch).inspectInventory()).resolves.toEqual({ status: 'success', value: [
      { name: 'qwen:latest', modifiedAt: '2026-08-13T00:00:00Z', size: 42, digest: 'abc' },
    ] });
  });

  it('performs bounded non-streaming generation with the selected model', async () => {
    const fetch = vi.fn(async () => response(200, { model: 'qwen:latest', response: 'hello', done: true }));
    await expect(provider(fetch).generate({ model: 'qwen:latest', prompt: 'Say hello' })).resolves.toEqual({
      status: 'success', value: { model: 'qwen:latest', response: 'hello', done: true },
    });
    const init = fetch.mock.calls[0]?.[1];
    expect(JSON.parse(init?.body ?? '')).toEqual({ model: 'qwen:latest', prompt: 'Say hello', stream: false });
  });

  it('normalizes a generation timeout as an indeterminate outcome', async () => {
    const fetch: ModelProviderFetch = (_input, init) => new Promise((_resolve, reject) => {
      init.signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true });
    });
    await expect(provider(fetch, 5).generate({ model: 'qwen:latest', prompt: 'slow' })).resolves.toMatchObject({
      status: 'indeterminate_outcome', failure: { code: 'timeout' },
    });
  });

  it('rejects malformed successful responses', async () => {
    await expect(provider(async () => response(200, { response: 42 })).generate({ model: 'qwen:latest', prompt: 'test' }))
      .resolves.toMatchObject({ status: 'non_retryable_failure', failure: { code: 'malformed_response' } });
  });

  it('normalizes retryable and non-retryable HTTP errors', async () => {
    await expect(provider(async () => response(503, {})).inspectHealth()).resolves.toMatchObject({
      status: 'retryable_failure', failure: { code: 'http_503', httpStatus: 503 },
    });
    await expect(provider(async () => response(404, {})).inspectInventory()).resolves.toMatchObject({
      status: 'non_retryable_failure', failure: { code: 'http_404', httpStatus: 404 },
    });
  });

  it('normalizes connection failure as retryable', async () => {
    await expect(provider(async () => { throw new Error('ECONNREFUSED'); }).inspectHealth()).resolves.toMatchObject({
      status: 'retryable_failure', failure: { code: 'connection_failure' },
    });
  });
});

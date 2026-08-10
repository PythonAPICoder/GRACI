import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { OllamaClient } from '../src/services/ollama/client.js';

const mockFetch = vi.fn();

describe('OllamaClient', () => {
  beforeEach(() => {
    mockFetch.mockReset();
    vi.stubGlobal('fetch', mockFetch);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('should initialize with default endpoint', () => {
    const client = new OllamaClient();
    expect(client).toBeDefined();
  });

  it('should accept custom endpoint', () => {
    const customEndpoint = 'http://custom:11434';
    const client = new OllamaClient(customEndpoint);
    expect(client.getEndpoint()).toBe(customEndpoint);
  });

  it('should handle successful health check', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: vi.fn().mockResolvedValue({ version: '0.32.7' }),
    });

    const client = new OllamaClient('http://localhost:11434');
    const result = await client.checkHealth();

    expect(result.success).toBe(true);
    expect(result.error).toBeUndefined();
  });

  it('should handle failed health check with HTTP error', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 503,
      statusText: 'Service Unavailable',
      json: vi.fn(),
    });

    const client = new OllamaClient('http://localhost:11434');
    const result = await client.checkHealth();

    expect(result.success).toBe(false);
    expect(result.error).toContain('HTTP 503');
  });

  it('should handle connectivity error', async () => {
    mockFetch.mockRejectedValue(new Error('Network error'));

    const client = new OllamaClient('http://localhost:11434');
    const result = await client.checkHealth();

    expect(result.success).toBe(false);
    expect(result.error).toContain('Connection failed');
  });

  it('should handle timeout during health check', async () => {
    vi.useFakeTimers();

    mockFetch.mockImplementation((_input: unknown, init?: RequestInit) => {
      return new Promise((_resolve, reject) => {
        init?.signal?.addEventListener(
          'abort',
          () => {
            const abortError = new Error('Request was cancelled');
            abortError.name = 'AbortError';
            reject(abortError);
          },
          { once: true }
        );
      });
    });

    const client = new OllamaClient('http://localhost:11434');
    const resultPromise = client.checkHealth();

    await vi.advanceTimersByTimeAsync(120000);
    const result = await resultPromise;

    expect(result.success).toBe(false);
    expect(result.error).toContain('timeout');
  });

  it('should handle successful inference', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: vi.fn().mockResolvedValue({
        model: 'gpt-oss:20b',
        response: 'G.R.A.C.I. Phase 2 inference verified.',
        done: true,
      }),
    });

    const client = new OllamaClient('http://localhost:11434');
    const result = await client.runInference('gpt-oss:20b', 'test prompt');

    expect(result.success).toBe(true);
    expect(result.response?.response).toBe(
      'G.R.A.C.I. Phase 2 inference verified.'
    );
  });

  it('should handle failed inference with HTTP error', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: vi.fn(),
    });

    const client = new OllamaClient('http://localhost:11434');
    const result = await client.runInference('gpt-oss:20b', 'test prompt');

    expect(result.success).toBe(false);
    expect(result.error).toContain('HTTP 404');
  });

  it('should handle inference error', async () => {
    mockFetch.mockRejectedValue(new Error('Inference error'));

    const client = new OllamaClient('http://localhost:11434');
    const result = await client.runInference('gpt-oss:20b', 'test prompt');

    expect(result.success).toBe(false);
    expect(result.error).toContain('Inference failed');
  });

  it('should handle inference timeout', async () => {
    vi.useFakeTimers();

    mockFetch.mockImplementation((_input: unknown, init?: RequestInit) => {
      return new Promise((_resolve, reject) => {
        init?.signal?.addEventListener(
          'abort',
          () => {
            const abortError = new Error('Request was cancelled');
            abortError.name = 'AbortError';
            reject(abortError);
          },
          { once: true }
        );
      });
    });

    const client = new OllamaClient('http://localhost:11434');
    const resultPromise = client.runInference('gpt-oss:20b', 'test prompt');

    await vi.advanceTimersByTimeAsync(120000);
    const result = await resultPromise;

    expect(result.success).toBe(false);
    expect(result.error).toContain('timeout');
  });

  it('should handle malformed version response in health check', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: vi.fn().mockResolvedValue({ version: '' }),
    });

    const client = new OllamaClient('http://localhost:11434');
    const result = await client.checkHealth();

    expect(result.success).toBe(false);
    expect(result.error).toContain('Malformed version response');
  });

  it('should handle malformed inference response', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: vi.fn().mockResolvedValue({
        model: 'gpt-oss:20b',
      }),
    });

    const client = new OllamaClient('http://localhost:11434');
    const result = await client.runInference('gpt-oss:20b', 'test prompt');

    expect(result.success).toBe(false);
    expect(result.error).toContain('Malformed inference response');
  });

  it('should handle incomplete inference (done not true)', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: vi.fn().mockResolvedValue({
        model: 'gpt-oss:20b',
        response: 'test response',
        done: false,
      }),
    });

    const client = new OllamaClient('http://localhost:11434');
    const result = await client.runInference('gpt-oss:20b', 'test prompt');

    expect(result.success).toBe(false);
    expect(result.error).toContain('done flag not set to true');
  });
});

import {
  MODEL_PROVIDER_CONTRACT_VERSION, type ModelGeneration, type ModelGenerationRequest, type ModelInventoryItem,
  type ModelProvider, type ModelProviderHealth, type ModelProviderResult,
} from './model-provider.js';

export interface FetchResponse {
  readonly ok: boolean;
  readonly status: number;
  json(): Promise<unknown>;
}

export type ModelProviderFetch = (input: string, init: {
  method: 'GET' | 'POST';
  headers?: Record<string, string>;
  body?: string;
  signal: AbortSignal;
}) => Promise<FetchResponse>;

export interface OllamaModelProviderOptions {
  endpoint: string;
  timeoutMs: number;
  fetch: ModelProviderFetch;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isRetryableHttpStatus(status: number): boolean {
  return status === 408 || status === 425 || status === 429 || status >= 500;
}

export class OllamaModelProvider implements ModelProvider {
  readonly contractVersion = MODEL_PROVIDER_CONTRACT_VERSION;
  readonly providerId = 'ollama';
  private readonly endpoint: string;

  constructor(private readonly options: OllamaModelProviderOptions) {
    if (!options.endpoint.trim()) throw new Error('Ollama endpoint must be supplied');
    if (!Number.isFinite(options.timeoutMs) || options.timeoutMs <= 0) throw new Error('Ollama timeoutMs must be positive');
    if (typeof options.fetch !== 'function') throw new Error('Ollama fetch implementation must be supplied');
    this.endpoint = options.endpoint.replace(/\/+$/, '');
  }

  async inspectHealth(): Promise<ModelProviderResult<ModelProviderHealth>> {
    const result = await this.request('/api/version', 'GET', undefined, false);
    if (result.status !== 'success') return result;
    if (!isRecord(result.value) || typeof result.value.version !== 'string' || !result.value.version) {
      return this.malformed('Ollama version response is malformed');
    }
    return { status: 'success', value: { version: result.value.version } };
  }

  async inspectInventory(): Promise<ModelProviderResult<readonly ModelInventoryItem[]>> {
    const result = await this.request('/api/tags', 'GET', undefined, false);
    if (result.status !== 'success') return result;
    if (!isRecord(result.value) || !Array.isArray(result.value.models)) return this.malformed('Ollama inventory response is malformed');
    const models: ModelInventoryItem[] = [];
    for (const value of result.value.models) {
      if (!isRecord(value) || typeof value.name !== 'string' || !value.name
        || (value.modified_at !== undefined && typeof value.modified_at !== 'string')
        || (value.size !== undefined && (typeof value.size !== 'number' || !Number.isFinite(value.size) || value.size < 0))
        || (value.digest !== undefined && typeof value.digest !== 'string')) {
        return this.malformed('Ollama inventory response is malformed');
      }
      models.push({ name: value.name, modifiedAt: value.modified_at as string | undefined,
        size: value.size as number | undefined, digest: value.digest as string | undefined });
    }
    return { status: 'success', value: models };
  }

  async generate(request: ModelGenerationRequest): Promise<ModelProviderResult<ModelGeneration>> {
    if (!request.model.trim() || typeof request.prompt !== 'string') {
      return { status: 'non_retryable_failure', failure: { code: 'invalid_request', summary: 'Model and prompt must be explicitly supplied' } };
    }
    const result = await this.request('/api/generate', 'POST', { model: request.model, prompt: request.prompt, stream: false }, true);
    if (result.status !== 'success') return result;
    if (!isRecord(result.value) || result.value.model !== request.model || typeof result.value.response !== 'string'
      || result.value.done !== true) return this.malformed('Ollama generation response is malformed');
    return { status: 'success', value: { model: result.value.model, response: result.value.response, done: true } };
  }

  private async request(path: string, method: 'GET' | 'POST', body: Record<string, unknown> | undefined,
    timeoutIsIndeterminate: boolean): Promise<ModelProviderResult<unknown>> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.options.timeoutMs);
    let timedOut = false;
    controller.signal.addEventListener('abort', () => { timedOut = true; }, { once: true });
    try {
      const response = await this.options.fetch(`${this.endpoint}${path}`, {
        method, signal: controller.signal,
        ...(body ? { headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) } : {}),
      });
      if (!response.ok) {
        const failure = { code: `http_${response.status}`, summary: `Ollama returned HTTP ${response.status}`, httpStatus: response.status };
        return { status: isRetryableHttpStatus(response.status) ? 'retryable_failure' : 'non_retryable_failure', failure };
      }
      try {
        return { status: 'success', value: await response.json() };
      } catch {
        return this.malformed('Ollama response body is not valid JSON');
      }
    } catch {
      if (timedOut) return { status: timeoutIsIndeterminate ? 'indeterminate_outcome' : 'retryable_failure',
        failure: { code: 'timeout', summary: `Ollama request exceeded ${this.options.timeoutMs}ms` } };
      return { status: 'retryable_failure', failure: { code: 'connection_failure', summary: 'Unable to connect to Ollama' } };
    } finally {
      clearTimeout(timeout);
    }
  }

  private malformed<T>(summary: string): ModelProviderResult<T> {
    return { status: 'non_retryable_failure', failure: { code: 'malformed_response', summary } };
  }
}

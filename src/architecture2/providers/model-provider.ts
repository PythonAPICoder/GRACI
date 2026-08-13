export const MODEL_PROVIDER_CONTRACT_VERSION = 1 as const;

export interface ModelProviderFailure {
  code: string;
  summary: string;
  httpStatus?: number;
}

export type ModelProviderResult<T> =
  | { status: 'success'; value: T }
  | { status: 'retryable_failure'; failure: ModelProviderFailure }
  | { status: 'non_retryable_failure'; failure: ModelProviderFailure }
  | { status: 'indeterminate_outcome'; failure: ModelProviderFailure };

export interface ModelProviderHealth {
  version: string;
}

export interface ModelInventoryItem {
  name: string;
  modifiedAt?: string;
  size?: number;
  digest?: string;
}

export interface ModelGenerationRequest {
  model: string;
  prompt: string;
}

export interface ModelGeneration {
  model: string;
  response: string;
  done: true;
}

export interface ModelProvider {
  readonly contractVersion: typeof MODEL_PROVIDER_CONTRACT_VERSION;
  readonly providerId: string;
  inspectHealth(): Promise<ModelProviderResult<ModelProviderHealth>>;
  inspectInventory(): Promise<ModelProviderResult<readonly ModelInventoryItem[]>>;
  generate(request: ModelGenerationRequest): Promise<ModelProviderResult<ModelGeneration>>;
}

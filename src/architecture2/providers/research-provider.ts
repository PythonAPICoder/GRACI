import type { JsonObject, PrivacyClass, ProviderId, ProviderOfferingId, ResearchRequestId } from '../domain/index.js';
import type { ModelProviderFailure, ModelProviderResult } from './model-provider.js';

export const RESEARCH_PROVIDER_CONTRACT_VERSION = 1 as const;

export interface ResearchProviderRequest {
  requestId: ResearchRequestId;
  question: string;
  purpose: string;
  privacyClass: PrivacyClass;
  idempotencyKey: string;
  deadline: string;
}

export interface ResearchProviderEvidence {
  suppliedAt: string;
  source: string;
  reference: string;
  content: JsonObject;
  integrity?: JsonObject;
}

export interface ResearchProvider {
  readonly contractVersion: typeof RESEARCH_PROVIDER_CONTRACT_VERSION;
  readonly providerId: ProviderId;
  readonly offeringId: ProviderOfferingId;
  research(request: ResearchProviderRequest): Promise<ModelProviderResult<ResearchProviderEvidence>>;
}

export type ResearchProviderFailure = ModelProviderFailure;

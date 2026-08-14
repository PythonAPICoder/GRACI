import type { AttemptId, FailureDiagnosisId, FailureId, JsonObject, TaskId } from '../domain/index.js';

export interface ReconciliationRequest {
  taskId: TaskId;
  attemptId: AttemptId;
  failureId: FailureId;
  diagnosisId: FailureDiagnosisId;
  providerOfferingId?: string;
  computeNodeId?: string;
  operationId: string;
}

export type ReconciliationProviderResult =
  | { conclusion: 'proven_completed'; operationId: string; output: JsonObject; evidence: JsonObject; reason: string }
  | { conclusion: 'proven_not_completed' | 'remains_indeterminate'; operationId: string; evidence: JsonObject; reason: string };

export interface ReconciliationProvider {
  readonly providerId: string;
  readonly providerVersion: number;
  reconcile(request: ReconciliationRequest): Promise<ReconciliationProviderResult>;
}

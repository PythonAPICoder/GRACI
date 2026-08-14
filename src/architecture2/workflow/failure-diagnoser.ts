import { createHash } from 'node:crypto';
import {
  asIdentifier,
  type Approval,
  type Attempt,
  type EventId,
  type Failure,
  type FailureDiagnosis,
  type JsonObject,
  type OfferingLocationId,
  type Task,
  type Verification,
  type FailureId,
} from '../domain/index.js';
import type { Architecture2Persistence } from '../persistence/index.js';

export const PHASE_1L_DIAGNOSIS_POLICY_ID = 'architecture2.phase1l.deterministic';
export const PHASE_1L_DIAGNOSIS_POLICY_VERSION = 1;

export interface FailureDiagnosisEvidence {
  task: Task;
  failure: Failure;
  attempts: readonly Attempt[];
  attempt?: Attempt;
  verification?: Verification;
  approval?: Approval;
  offeringLocationId?: OfferingLocationId;
}

export interface FailureDiagnosisCommand {
  evidence: FailureDiagnosisEvidence;
  eventId: EventId;
  diagnosedAt: string;
  diagnosedBy: string;
  policyId?: string;
  policyVersion?: number;
}

export interface DiagnosePersistedFailureCommand {
  failureId: FailureId;
  eventId: EventId;
  diagnosedAt: string;
  diagnosedBy: string;
  policyId?: string;
  policyVersion?: number;
}

function canonicalize(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(',')}]`;
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${canonicalize(object[key])}`).join(',')}}`;
}

function maxAttempts(task: Task): number {
  const configured = task.retryPolicy.maxAttempts;
  return typeof configured === 'number' && Number.isInteger(configured) && configured >= 1 ? configured : 3;
}

export function existingRetryAuthorized(task: Task, failure: Failure, attemptsUsed: number): boolean {
  if (!failure.retryable || attemptsUsed >= maxAttempts(task)) return false;
  if (failure.classification === 'transient') return true;
  return failure.classification === 'verification_failed' && task.retryPolicy.retryVerificationFailures === true;
}

export function createFailureDiagnosis(command: FailureDiagnosisCommand): FailureDiagnosis {
  const { task, failure, attempts, attempt, verification, approval, offeringLocationId } = command.evidence;
  const policyId = command.policyId ?? PHASE_1L_DIAGNOSIS_POLICY_ID;
  const policyVersion = command.policyVersion ?? PHASE_1L_DIAGNOSIS_POLICY_VERSION;
  const attemptsUsed = attempt
    ? attempt.attemptNumber
    : attempts.filter((value) => Date.parse(value.createdAt) <= Date.parse(failure.createdAt)).length;
  const attemptMatches = failure.attemptId === undefined
    ? attempt === undefined
    : attempt?.id === failure.attemptId && attempt.taskId === failure.taskId;
  const taskMatches = failure.taskId === task.id;
  const verificationMatches = failure.classification !== 'verification_failed' ||
    (verification?.taskId === task.id && verification.attemptId === failure.attemptId && verification.verdict !== 'passed');
  const approvalMatches = failure.classification !== 'approval_required' ||
    (approval?.taskId === task.id && approval.attemptId === failure.attemptId && approval.decision === 'requested');
  const classificationMatches =
    (failure.classification !== 'transient' || failure.category === 'transient_infrastructure') &&
    (failure.classification !== 'verification_failed' || failure.category === 'verification_failure') &&
    (failure.classification !== 'approval_required' || failure.category === 'policy_or_approval') &&
    (failure.classification !== 'external_outcome_indeterminate' || failure.category === 'external_outcome_indeterminate') &&
    (failure.category !== 'external_outcome_indeterminate' || failure.classification === 'external_outcome_indeterminate');
  const reconciledCompletion = verification?.evidence.reconciliationProvenCompleted === true;
  const attemptStatusMatches = !attempt ||
    (failure.classification === 'verification_failed'
      ? attempt.status === 'succeeded' || (attempt.status === 'indeterminate' && reconciledCompletion) :
      failure.classification === 'external_outcome_indeterminate' ? attempt.status === 'indeterminate' :
        attempt.status === 'failed');
  const structurallyValid = taskMatches && attemptMatches && verificationMatches && approvalMatches &&
    classificationMatches && attemptStatusMatches &&
    Boolean(failure.code.trim() && failure.summary.trim()) && Number.isInteger(policyVersion) && policyVersion >= 1 &&
    Boolean(policyId.trim() && command.diagnosedBy.trim()) && !Number.isNaN(Date.parse(command.diagnosedAt));
  const retryable = structurallyValid && existingRetryAuthorized(task, failure, attemptsUsed);

  let outcomeCertainty: FailureDiagnosis['outcomeCertainty'];
  let disposition: FailureDiagnosis['disposition'];
  let diagnosticReason: string;
  if (!structurallyValid) {
    outcomeCertainty = 'insufficient_or_malformed_evidence';
    disposition = 'terminal_failure';
    diagnosticReason = 'authoritative_evidence_missing_or_malformed';
  } else if (failure.category === 'external_outcome_indeterminate' ||
      failure.classification === 'external_outcome_indeterminate' ||
      (attempt?.status === 'indeterminate' && !reconciledCompletion)) {
    outcomeCertainty = 'indeterminate_external_outcome';
    disposition = 'reconciliation_required';
    diagnosticReason = 'external_outcome_cannot_be_proven';
  } else {
    outcomeCertainty = failure.category === 'verification_failure' ? 'proven_completed' : 'proven_unsuccessful';
    if (failure.classification === 'approval_required') {
      disposition = 'approval_required';
      diagnosticReason = 'existing_approval_semantics_required';
    } else if (retryable) {
      disposition = 'retry_same_path';
      diagnosticReason = failure.classification === 'verification_failed'
        ? 'verification_retry_explicitly_enabled' : 'transient_retry_within_attempt_limit';
    } else if (failure.category === 'provider_or_capability_mismatch') {
      disposition = 'alternative_offering_recommended';
      diagnosticReason = 'provider_or_capability_mismatch';
    } else if (failure.category === 'resource_unavailable') {
      disposition = 'alternative_node_recommended';
      diagnosticReason = 'resource_unavailable';
    } else if (failure.category === 'invalid_input_or_precondition') {
      disposition = 'input_revision_required';
      diagnosticReason = 'input_or_precondition_invalid';
    } else if (failure.category === 'execution_defect' && failure.code === 'TASK_GRAPH_STRUCTURE_INVALID') {
      disposition = 'replanning_recommended';
      diagnosticReason = 'task_graph_structure_invalid';
    } else if (failure.category === 'unknown') {
      disposition = 'research_recommended';
      diagnosticReason = 'cause_unknown_with_valid_evidence';
    } else {
      disposition = 'terminal_failure';
      diagnosticReason = retryable ? 'retry_not_authorized' : 'no_phase1l_recovery_authorized';
    }
  }

  const fingerprintInput: JsonObject = {
    failureId: failure.id, taskId: task.id, attemptId: failure.attemptId ?? null, category: failure.category,
    classification: failure.classification, failureRetryable: failure.retryable, code: failure.code,
    retryPolicy: task.retryPolicy, attemptsUsed, attemptStatus: attempt?.status ?? null,
    verificationId: verification?.id ?? null, verificationVerdict: verification?.verdict ?? null,
    reconciliationProvenCompleted: reconciledCompletion,
    approvalId: approval?.id ?? null, approvalDecision: approval?.decision ?? null,
    providerOfferingId: attempt?.providerOfferingId ?? null, computeNodeId: attempt?.computeNodeId ?? null,
    offeringLocationId: offeringLocationId ?? null, policyId, policyVersion,
  };
  const evidenceFingerprint = createHash('sha256').update(canonicalize(fingerprintInput)).digest('hex');
  const identityHash = createHash('sha256').update(`${failure.id}\u0000${policyId}\u0000${policyVersion}`).digest('hex');

  return {
    id: asIdentifier<'FailureDiagnosis'>(`diagnosis-${identityHash.slice(0, 32)}`), failureId: failure.id, taskId: task.id,
    attemptId: failure.attemptId, verificationId: verification?.id, approvalId: approval?.id,
    providerOfferingId: attempt?.providerOfferingId, computeNodeId: attempt?.computeNodeId, offeringLocationId,
    cause: structurallyValid ? failure.category : 'unknown', outcomeCertainty, retryable, disposition,
    retryReason: retryable ? 'existing_retry_policy_authorizes' : 'existing_retry_policy_denies', diagnosticReason,
    policyId, policyVersion, evidenceFingerprint, diagnosedBy: command.diagnosedBy,
    diagnosedAt: command.diagnosedAt, eventId: command.eventId,
  };
}

export function diagnosePersistedFailure(persistence: Architecture2Persistence,
  command: DiagnosePersistedFailureCommand): FailureDiagnosis {
  const failure = persistence.getFailure(command.failureId);
  if (!failure) throw new Error(`Failure not found: ${command.failureId}`);
  const task = persistence.getTask(failure.taskId);
  if (!task) throw new Error(`Failure Task not found: ${failure.taskId}`);
  const attempts = persistence.getAttempts(task.id);
  const attempt = failure.attemptId ? attempts.find((value) => value.id === failure.attemptId) : undefined;
  const verification = failure.classification === 'verification_failed'
    ? persistence.getVerifications(task.id).slice().reverse().find((value) => value.attemptId === failure.attemptId)
    : undefined;
  const approval = failure.classification === 'approval_required'
    ? persistence.getApprovals(task.id).slice().reverse().find((value) => value.attemptId === failure.attemptId && value.decision === 'requested')
    : undefined;
  const diagnosis = createFailureDiagnosis({ evidence: { task, failure, attempts, attempt, verification, approval },
    eventId: command.eventId, diagnosedAt: command.diagnosedAt, diagnosedBy: command.diagnosedBy,
    policyId: command.policyId, policyVersion: command.policyVersion });
  return persistence.recordFailureDiagnosis(diagnosis, { id: command.eventId, aggregateType: 'task', aggregateId: task.id,
    eventType: 'failure.diagnosed', eventVersion: 1, actor: command.diagnosedBy, occurredAt: command.diagnosedAt,
    payload: { failureId: failure.id, diagnosisId: diagnosis.id, disposition: diagnosis.disposition } });
}

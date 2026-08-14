import { createHash } from 'node:crypto';
import { type AuditEventInput, type Failure, type FailureDiagnosis, type JsonObject,
  type ReconciliationDecision, type Task, type Verification } from '../domain/index.js';
import type { Architecture2Persistence } from '../persistence/index.js';
import type { TaskVerifier } from '../verification/index.js';
import { createFailureDiagnosis, PHASE_1L_DIAGNOSIS_POLICY_ID,
  PHASE_1L_DIAGNOSIS_POLICY_VERSION } from '../workflow/failure-diagnoser.js';
import type { ReconciliationProvider, ReconciliationProviderResult } from './contract.js';

export interface ReconciliationCommand {
  id: ReconciliationDecision['id']; diagnosisId: ReconciliationDecision['diagnosisId']; actor: string; decidedAt: string;
  eventId: ReconciliationDecision['eventId']; verificationId: Verification['id'];
  verificationEventId: AuditEventInput['id']; transitionEventId: AuditEventInput['id']; failureId: Failure['id'];
  failureEventId: AuditEventInput['id']; diagnosisEventId: AuditEventInput['id'];
}

function canonicalize(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(',')}]`;
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${canonicalize(object[key])}`).join(',')}}`;
}
const MAX_RECONCILIATION_RESULT_BYTES = 64 * 1024;

function assertJsonValue(value: unknown, label: string, seen = new Set<object>(), depth = 0): void {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return;
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new Error(`${label} contains a non-finite number`);
    return;
  }
  if (typeof value !== 'object') throw new Error(`${label} contains a non-JSON value`);
  if (depth > 32) throw new Error(`${label} exceeds the maximum nesting depth`);
  const object = value as object;
  if (seen.has(object)) throw new Error(`${label} contains a cycle`);
  seen.add(object);
  if (Array.isArray(value)) {
    for (const item of value) assertJsonValue(item, label, seen, depth + 1);
  } else {
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) throw new Error(`${label} contains a non-plain object`);
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      if (!key) throw new Error(`${label} contains an empty key`);
      assertJsonValue(item, label, seen, depth + 1);
    }
  }
  seen.delete(object);
}
function maxAttempts(task: Task): number {
  const value = task.retryPolicy.maxAttempts;
  return typeof value === 'number' && Number.isInteger(value) && value >= 1 ? value : 3;
}
function event(id: AuditEventInput['id'], taskId: Task['id'], eventType: string, actor: string,
  occurredAt: string, payload: JsonObject): AuditEventInput {
  return { id, aggregateType: 'task', aggregateId: taskId, eventType, eventVersion: 1, actor, occurredAt, payload };
}
function validateResult(value: unknown, operationId: string): ReconciliationProviderResult {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Malformed reconciliation response');
  const result = value as Record<string, unknown>;
  if (!['proven_completed', 'proven_not_completed', 'remains_indeterminate'].includes(String(result.conclusion)) ||
      result.operationId !== operationId || !result.evidence || typeof result.evidence !== 'object' ||
      Array.isArray(result.evidence) || typeof result.reason !== 'string' || !result.reason.trim()) {
    throw new Error('Malformed or contradictory reconciliation response');
  }
  if (result.conclusion === 'proven_completed' &&
      (!result.output || typeof result.output !== 'object' || Array.isArray(result.output))) {
    throw new Error('Completed reconciliation response requires bounded output');
  }
  if (result.conclusion !== 'proven_completed' && result.output !== undefined) {
    throw new Error('Contradictory reconciliation response contains output');
  }
  assertJsonValue(result.evidence, 'Reconciliation evidence');
  if (result.conclusion === 'proven_completed') assertJsonValue(result.output, 'Reconciliation output');
  let serialized: string;
  try {
    serialized = JSON.stringify(value);
  } catch (error) {
    throw new Error('Malformed reconciliation response is not serializable', { cause: error });
  }
  if (Buffer.byteLength(serialized, 'utf8') > MAX_RECONCILIATION_RESULT_BYTES) {
    throw new Error('Reconciliation response exceeds the bounded evidence limit');
  }
  return value as ReconciliationProviderResult;
}

export async function reconcileExternalOutcome(persistence: Architecture2Persistence, verifier: TaskVerifier,
  provider: ReconciliationProvider, command: ReconciliationCommand): Promise<ReconciliationDecision> {
  if (!provider.providerId.trim() || !Number.isInteger(provider.providerVersion) || provider.providerVersion < 1) {
    throw new Error('Invalid reconciliation provider identity/version');
  }
  const diagnosis = persistence.getFailureDiagnosisById(command.diagnosisId);
  if (!diagnosis) throw new Error(`Failure diagnosis not found: ${command.diagnosisId}`);
  const prior = persistence.getReconciliationDecisions(diagnosis.id);
  const task = persistence.getTask(diagnosis.taskId);
  const failure = persistence.getFailure(diagnosis.failureId);
  const attempts = task ? persistence.getAttempts(task.id) : [];
  const attempt = attempts.find((value) => value.id === diagnosis.attemptId);
  if (!task || !failure || !attempt || !attempt.idempotencyKey?.trim()) {
    throw new Error('Reconciliation requires exact persisted source and external operation identity');
  }
  let raw: unknown;
  try {
    raw = await provider.reconcile({ taskId: task.id, attemptId: attempt.id, failureId: failure.id,
      diagnosisId: diagnosis.id, providerOfferingId: attempt.providerOfferingId, computeNodeId: attempt.computeNodeId,
      operationId: attempt.idempotencyKey });
  } catch (error) {
    throw new Error('Reconciliation provider failed closed', { cause: error });
  }
  const result = validateResult(raw, attempt.idempotencyKey);
  const fingerprint = createHash('sha256').update(canonicalize(result)).digest('hex');
  const duplicate = prior.find((value) => value.providerId === provider.providerId &&
    value.providerVersion === provider.providerVersion && value.evidenceFingerprint === fingerprint &&
    value.operationId === result.operationId && value.conclusion === result.conclusion);
  if (duplicate) {
    if (duplicate.id !== command.id) throw new Error(`Reconciliation request identity conflict: ${command.id}`);
    return duplicate;
  }
  if (prior.some((value) => value.conclusion !== 'remains_indeterminate')) {
    throw new Error(`Reconciliation authority already concluded: ${diagnosis.attemptId}`);
  }
  if (prior.some((value) => value.id === command.id)) throw new Error(`Reconciliation request identity conflict: ${command.id}`);
  const latestAttempt = attempts.at(-1);
  const latestFailure = task && attempt
    ? persistence.getFailures(task.id).filter((value) => value.attemptId === latestAttempt?.id).at(-1) : undefined;
  const latestDiagnosis = latestFailure ? persistence.getFailureDiagnosis(latestFailure.id,
    PHASE_1L_DIAGNOSIS_POLICY_ID, PHASE_1L_DIAGNOSIS_POLICY_VERSION) : undefined;
  if (task.status !== 'failed' || latestAttempt?.id !== attempt.id || attempt.status !== 'indeterminate' ||
      failure.id !== latestFailure?.id || failure.attemptId !== attempt.id || diagnosis.attemptId !== attempt.id ||
      latestDiagnosis?.id !== diagnosis.id || diagnosis.policyId !== PHASE_1L_DIAGNOSIS_POLICY_ID ||
      diagnosis.policyVersion !== PHASE_1L_DIAGNOSIS_POLICY_VERSION ||
      diagnosis.outcomeCertainty !== 'indeterminate_external_outcome' || diagnosis.disposition !== 'reconciliation_required' ||
      failure.classification !== 'external_outcome_indeterminate') {
    throw new Error('Reconciliation source authority is stale, contradictory, or non-indeterminate');
  }
  if (persistence.getAlternativeRecoveryDecision(diagnosis.id)) throw new Error('Reconciliation source has a recovery action');
  let updated: Task | undefined;
  let verification: Verification | undefined;
  let verificationFailure: Failure | undefined;
  let verificationDiagnosis: FailureDiagnosis | undefined;
  const events: AuditEventInput[] = [event(command.eventId, task.id, 'reconciliation.decided', command.actor,
    command.decidedAt, { diagnosisId: diagnosis.id, conclusion: result.conclusion })];
  let nextAttemptNumber: number | undefined;
  let decisionReason = result.reason;
  if (result.conclusion === 'proven_not_completed') {
    const pendingApproval = persistence.getApprovals(task.id).some((approval) => approval.decision === 'requested');
    if (attempts.length >= maxAttempts(task)) {
      decisionReason = 'proven_not_completed; retry_authority_withheld:attempt_limit_exhausted';
    } else if (pendingApproval) {
      decisionReason = 'proven_not_completed; retry_authority_withheld:approval_required';
    } else {
      nextAttemptNumber = attempt.attemptNumber + 1;
      updated = { ...task, status: 'ready', terminalReason: undefined, completedAt: undefined,
        version: task.version + 1, updatedAt: command.decidedAt };
      events.push(event(command.transitionEventId, task.id, 'task.transitioned', command.actor, command.decidedAt,
        { from: 'failed', to: 'ready', reason: 'reconciliation_proven_not_completed' }));
    }
  } else if (result.conclusion === 'proven_completed') {
    const checked = verifier.verify({ ...task, status: 'verifying' },
      { status: 'succeeded', output: result.output, evidence: result.evidence });
    verification = { id: command.verificationId, taskId: task.id, attemptId: attempt.id, verdict: checked.verdict,
      planVersion: 1, verifier: verifier.verifierId, criterionResults: checked.criterionResults,
      evidence: { ...checked.evidence, reconciliationProvenCompleted: true,
        reconciliationDecisionId: command.id }, createdAt: command.decidedAt };
    events.push(event(command.verificationEventId, task.id, `verification.${verification.verdict}`, command.actor,
      command.decidedAt, { verificationId: verification.id, reconciledAttemptId: attempt.id }));
    if (verification.verdict === 'passed') {
      updated = { ...task, status: 'succeeded', terminalReason: undefined, completedAt: command.decidedAt,
        version: task.version + 1, updatedAt: command.decidedAt };
    } else {
      verificationFailure = { id: command.failureId, taskId: task.id, attemptId: attempt.id,
        category: 'verification_failure', classification: 'verification_failed', code: 'DETERMINISTIC_VERIFICATION_FAILED',
        summary: 'Deterministic verification rejected the reconciled result', details: { verdict: verification.verdict },
        retryable: false, createdAt: command.decidedAt };
      const diagnosisEvent = event(command.diagnosisEventId, task.id, 'failure.diagnosed', command.actor,
        command.decidedAt, { failureId: verificationFailure.id });
      verificationDiagnosis = createFailureDiagnosis({ evidence: { task, failure: verificationFailure, attempts,
        attempt, verification }, eventId: diagnosisEvent.id,
      diagnosedAt: command.decidedAt, diagnosedBy: command.actor });
      events.push(event(command.failureEventId, task.id, 'failure.recorded', command.actor, command.decidedAt,
        { failureId: verificationFailure.id }), diagnosisEvent);
      updated = { ...task, terminalReason: verificationFailure.code, version: task.version + 1,
        updatedAt: command.decidedAt, completedAt: command.decidedAt };
    }
    events.push(event(command.transitionEventId, task.id, 'task.transitioned', command.actor, command.decidedAt,
      { from: 'failed', to: updated.status, reason: 'reconciliation_verification' }));
  }
  const decision: ReconciliationDecision = { id: command.id, taskId: task.id, attemptId: attempt.id,
    failureId: failure.id, diagnosisId: diagnosis.id, providerId: provider.providerId,
    providerVersion: provider.providerVersion, operationId: result.operationId, evidence: result.evidence,
    evidenceFingerprint: fingerprint, conclusion: result.conclusion, reason: decisionReason,
    observationNumber: prior.length + 1, nextAttemptNumber, verificationId: verification?.id,
    actor: command.actor, decidedAt: command.decidedAt, eventId: command.eventId };
  return persistence.recordReconciliationDecision(decision, updated, updated ? task.version : undefined,
    verification, verificationFailure, verificationDiagnosis, events);
}

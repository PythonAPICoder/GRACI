import { createHash } from 'node:crypto';
import { assertIdentifier, type AuditEventInput, type InputRevision, type JsonObject } from '../domain/index.js';
import type { Architecture2Persistence } from '../persistence/index.js';
import { PHASE_1L_DIAGNOSIS_POLICY_ID, PHASE_1L_DIAGNOSIS_POLICY_VERSION } from './failure-diagnoser.js';

export interface AuthorizeInputRevisionCommand {
  id: InputRevision['id'];
  diagnosisId: InputRevision['diagnosisId'];
  revisedInputs: JsonObject;
  actor: string;
  authorizedAt: string;
  eventId: InputRevision['eventId'];
}

function canonicalize(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(',')}]`;
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${canonicalize(object[key])}`).join(',')}}`;
}

function assertPlainJson(value: unknown, seen = new Set<object>()): void {
  if (value === null || typeof value === 'string' || typeof value === 'boolean' ||
      (typeof value === 'number' && Number.isFinite(value))) return;
  if (typeof value !== 'object') throw new Error('Revised inputs must contain only plain JSON values');
  if (seen.has(value)) throw new Error('Revised inputs must not be cyclic');
  seen.add(value);
  if (Array.isArray(value)) for (const item of value) assertPlainJson(item, seen);
  else {
    if (Object.getPrototypeOf(value) !== Object.prototype) throw new Error('Revised inputs must be a plain JSON object');
    for (const item of Object.values(value as Record<string, unknown>)) assertPlainJson(item, seen);
  }
  seen.delete(value);
}

function digest(value: JsonObject): string {
  return createHash('sha256').update(canonicalize(value)).digest('hex');
}

function maxAttempts(value: number | undefined): number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 1 ? value : 3;
}

export function authorizeInputRevision(persistence: Architecture2Persistence,
  command: AuthorizeInputRevisionCommand): InputRevision {
  assertIdentifier(command.id, 'input revision id');
  assertIdentifier(command.diagnosisId, 'failure diagnosis id');
  assertIdentifier(command.eventId, 'input revision event id');
  if (!command.actor.trim()) throw new Error('Input revision actor is required');
  const parsedTime = new Date(command.authorizedAt);
  if (Number.isNaN(parsedTime.valueOf()) || parsedTime.toISOString() !== command.authorizedAt) {
    throw new Error('Input revision authorization time must be canonical UTC');
  }
  assertPlainJson(command.revisedInputs);
  if (command.revisedInputs === null || Array.isArray(command.revisedInputs) ||
      Object.getPrototypeOf(command.revisedInputs) !== Object.prototype) {
    throw new Error('Revised inputs must be a plain JSON object');
  }
  const existing = persistence.getInputRevisionByDiagnosis(command.diagnosisId);
  if (existing) {
    if (existing.id !== command.id || existing.revisedInputsDigest !== digest(command.revisedInputs)) {
      throw new Error(`Input revision authority conflict: ${command.diagnosisId}`);
    }
    return existing;
  }
  const diagnosis = persistence.getFailureDiagnosisById(command.diagnosisId);
  if (!diagnosis) throw new Error(`Failure diagnosis not found: ${command.diagnosisId}`);
  const task = persistence.getTask(diagnosis.taskId);
  const failure = persistence.getFailure(diagnosis.failureId);
  const attempts = task ? persistence.getAttempts(task.id) : [];
  const attempt = attempts.at(-1);
  const latestFailure = task && attempt ? persistence.getFailures(task.id)
    .filter((value) => value.attemptId === attempt.id).at(-1) : undefined;
  const latestDiagnosis = latestFailure ? persistence.getFailureDiagnosis(latestFailure.id,
    PHASE_1L_DIAGNOSIS_POLICY_ID, PHASE_1L_DIAGNOSIS_POLICY_VERSION) : undefined;
  if (!task || !failure || !attempt || task.status !== 'failed' || attempt.status !== 'failed' ||
      failure.id !== latestFailure?.id || failure.attemptId !== attempt.id || diagnosis.attemptId !== attempt.id ||
      latestDiagnosis?.id !== diagnosis.id || diagnosis.policyId !== PHASE_1L_DIAGNOSIS_POLICY_ID ||
      diagnosis.policyVersion !== PHASE_1L_DIAGNOSIS_POLICY_VERSION || diagnosis.disposition !== 'input_revision_required' ||
      diagnosis.outcomeCertainty !== 'proven_unsuccessful') {
    throw new Error('Input revision source authority is stale, contradictory, or ineligible');
  }
  const attemptedInputs = attempt.inputSnapshot.inputs;
  if (attemptedInputs === null || Array.isArray(attemptedInputs) || typeof attemptedInputs !== 'object' ||
      digest(attemptedInputs as JsonObject) !== digest(task.inputs)) {
    throw new Error('Failed Attempt input snapshot does not match current Task inputs');
  }
  if (persistence.getAlternativeRecoveryDecision(diagnosis.id) ||
      persistence.getReconciliationDecisions(diagnosis.id).length > 0) {
    throw new Error('Input revision conflicts with existing recovery authority');
  }
  if (attempts.length >= maxAttempts(task.retryPolicy.maxAttempts)) throw new Error('Input revision Attempt limit exhausted');
  if (persistence.getApprovals(task.id).some((approval) => approval.decision === 'requested')) {
    throw new Error('Input revision cannot bypass pending approval');
  }
  const priorInputsDigest = digest(task.inputs);
  const revisedInputsDigest = digest(command.revisedInputs);
  if (priorInputsDigest === revisedInputsDigest) throw new Error('Input revision must change canonical Task inputs');
  const value: InputRevision = { id: command.id, taskId: task.id, failedAttemptId: attempt.id,
    failureId: failure.id, diagnosisId: diagnosis.id, priorInputs: task.inputs, priorInputsDigest,
    revisedInputs: command.revisedInputs, revisedInputsDigest, nextAttemptNumber: attempt.attemptNumber + 1,
    actor: command.actor, authorizedAt: command.authorizedAt, eventId: command.eventId };
  const updated = { ...task, inputs: command.revisedInputs, status: 'ready' as const, terminalReason: undefined,
    completedAt: undefined, version: task.version + 1, updatedAt: command.authorizedAt };
  const event: AuditEventInput = { id: command.eventId, aggregateType: 'task', aggregateId: task.id,
    eventType: 'input-revision.authorized', eventVersion: 1, actor: command.actor, occurredAt: command.authorizedAt,
    payload: { inputRevisionId: value.id, diagnosisId: diagnosis.id, nextAttemptNumber: value.nextAttemptNumber,
      priorInputsDigest, revisedInputsDigest } };
  return persistence.authorizeInputRevision(value, updated, task.version, event);
}

import {
  asIdentifier,
  type AlternativeRecoveryDecision,
  type AuditEventInput,
  type ChangedConditionEvidence,
  type FailureDiagnosisId,
  type ProviderResolutionRequest,
  type ResourceSchedulingRequest,
  type Task,
} from '../domain/index.js';
import type { Architecture2Persistence } from '../persistence/index.js';
import { DeterministicProviderResolver } from '../providers/index.js';
import { DeterministicResourceScheduler } from '../resources/index.js';
import { PHASE_1L_DIAGNOSIS_POLICY_ID, PHASE_1L_DIAGNOSIS_POLICY_VERSION } from './failure-diagnoser.js';

export interface AlternativeRecoveryCommand {
  id: AlternativeRecoveryDecision['id'];
  diagnosisId: FailureDiagnosisId;
  requestedDisposition: AlternativeRecoveryDecision['requestedDisposition'];
  actor: string;
  decidedAt: string;
  eventId: AlternativeRecoveryDecision['eventId'];
  evidenceId: ChangedConditionEvidence['id'];
  evidenceEventId: ChangedConditionEvidence['eventId'];
  providerRequest?: ProviderResolutionRequest;
  resourceRequest?: ResourceSchedulingRequest;
}

function maxAttempts(task: Task): number {
  const value = task.retryPolicy.maxAttempts;
  return typeof value === 'number' && Number.isInteger(value) && value >= 1 ? value : 3;
}

export function recoverWithAlternative(persistence: Architecture2Persistence,
  command: AlternativeRecoveryCommand): AlternativeRecoveryDecision {
  const existing = persistence.getAlternativeRecoveryDecision(command.diagnosisId);
  if (existing) {
    if (existing.id !== command.id || existing.requestedDisposition !== command.requestedDisposition) {
      throw new Error(`Alternative recovery authority conflict: ${command.diagnosisId}`);
    }
    return existing;
  }
  const diagnosis = persistence.getFailureDiagnosisById(command.diagnosisId);
  if (!diagnosis) throw new Error(`Failure diagnosis not found: ${command.diagnosisId}`);
  const task = persistence.getTask(diagnosis.taskId);
  const failure = persistence.getFailure(diagnosis.failureId);
  const attempts = task ? persistence.getAttempts(task.id) : [];
  const failedAttempt = attempts.at(-1);
  const latestFailure = failedAttempt && task
    ? persistence.getFailures(task.id).filter((value) => value.attemptId === failedAttempt.id).at(-1)
    : undefined;
  const latestDiagnosis = latestFailure ? persistence.getFailureDiagnosis(latestFailure.id,
    PHASE_1L_DIAGNOSIS_POLICY_ID, PHASE_1L_DIAGNOSIS_POLICY_VERSION) : undefined;
  let rejection: string | undefined;
  if (!task || !failure || !failedAttempt || task.status !== 'failed') rejection = 'authoritative_state_not_current';
  else if (diagnosis.policyId !== PHASE_1L_DIAGNOSIS_POLICY_ID || diagnosis.policyVersion !== PHASE_1L_DIAGNOSIS_POLICY_VERSION ||
      diagnosis.disposition !== command.requestedDisposition || diagnosis.outcomeCertainty !== 'proven_unsuccessful') rejection = 'diagnosis_not_authoritative';
  else if (failure.id !== latestFailure?.id || failure.attemptId !== failedAttempt.id ||
      diagnosis.attemptId !== failedAttempt.id || latestDiagnosis?.id !== diagnosis.id) rejection = 'latest_failure_or_attempt_mismatch';
  else if (attempts.length >= maxAttempts(task)) rejection = 'attempt_limit_exhausted';
  else if (persistence.getApprovals(task.id).some((approval) => approval.decision === 'requested')) rejection = 'approval_required';

  let selectedOfferingId = failedAttempt?.providerOfferingId as AlternativeRecoveryDecision['selectedOfferingId'];
  let selectedNodeId: AlternativeRecoveryDecision['selectedNodeId'];
  let selectedLocationId: AlternativeRecoveryDecision['selectedLocationId'];
  let providerResolutionId: AlternativeRecoveryDecision['providerResolutionId'];
  let resourceSchedulingDecisionId: AlternativeRecoveryDecision['resourceSchedulingDecisionId'];
  if (!rejection && command.requestedDisposition === 'alternative_offering_recommended') {
    if (!command.providerRequest || command.resourceRequest) rejection = 'invalid_recovery_request';
    else {
      const request: ProviderResolutionRequest = { ...command.providerRequest,
        excludedOfferingIds: [...(command.providerRequest.excludedOfferingIds ?? []), failedAttempt!.providerOfferingId!]
          .filter(Boolean) as unknown as ProviderResolutionRequest['excludedOfferingIds'] };
      const resolver = new DeterministicProviderResolver(persistence, { nextEvent: (decision) => ({
        id: asIdentifier<'Event'>(`event-${decision.request.id}`), aggregateType: 'provider-resolution',
        aggregateId: decision.request.id, eventType: 'provider-resolution.recorded', eventVersion: 1,
        actor: command.actor, occurredAt: command.decidedAt, payload: { selectedOfferingId: decision.selectedOfferingId ?? null },
      }) });
      const result = resolver.resolve(request);
      providerResolutionId = result.request.id;
      selectedOfferingId = result.selectedOfferingId;
      if (!selectedOfferingId) rejection = 'no_eligible_alternative';
      else {
        const offerings = persistence.getProviderOfferings();
        const failed = offerings.find((value) => value.id === failedAttempt!.providerOfferingId);
        const selected = offerings.find((value) => value.id === selectedOfferingId);
        const sideEffectRank = { none: 0, local: 1, external_reversible: 2, external_consequential: 3 } as const;
        if (!failed || !selected || selected.inputSchemaReference !== failed.inputSchemaReference ||
            selected.outputSchemaReference !== failed.outputSchemaReference || selected.maximumCost > failed.maximumCost ||
            sideEffectRank[selected.sideEffectClass] > sideEffectRank[failed.sideEffectClass] ||
            selected.permissions.some((permission) => !failed.permissions.includes(permission)) ||
            selected.privacyDestinations.some((privacy) => !failed.privacyDestinations.includes(privacy))) {
          rejection = 'material_scope_broadened';
        }
      }
    }
  } else if (!rejection) {
    if (!command.resourceRequest || command.providerRequest || command.resourceRequest.offeringId !== failedAttempt!.providerOfferingId) {
      rejection = 'invalid_recovery_request';
    } else {
      const request: ResourceSchedulingRequest = { ...command.resourceRequest,
        excludedNodeIds: [...(command.resourceRequest.excludedNodeIds ?? []), failedAttempt!.computeNodeId!]
          .filter(Boolean) as unknown as ResourceSchedulingRequest['excludedNodeIds'],
        excludedLocationIds: [...(command.resourceRequest.excludedLocationIds ?? []), diagnosis.offeringLocationId!].filter(Boolean) };
      const scheduler = new DeterministicResourceScheduler();
      const result = scheduler.schedule(request, { nodes: persistence.getNodes(),
        locations: persistence.getOfferingLocations(request.offeringId),
        healthObservations: persistence.getNodes().flatMap((node) => persistence.getNodeHealth(node.id)),
        leases: persistence.getResourceLeases(), circuits: persistence.getCircuits(),
        circuitProbes: persistence.getCircuits().flatMap((circuit) => persistence.getCircuitProbes(circuit.id)) });
      resourceSchedulingDecisionId = result.request.id;
      selectedNodeId = result.selectedNodeId;
      selectedLocationId = result.selectedLocationId;
      if (!selectedNodeId || !selectedLocationId) rejection = 'no_eligible_alternative';
    }
  }

  const authorized = !rejection;
  const evidence: ChangedConditionEvidence | undefined = authorized ? {
    id: command.evidenceId, diagnosisId: diagnosis.id,
    conditionType: command.requestedDisposition === 'alternative_offering_recommended' ? 'provider_offering_changed' : 'resource_binding_changed',
    priorFactReference: command.requestedDisposition === 'alternative_offering_recommended'
      ? `offering:${failedAttempt!.providerOfferingId}` : `node:${failedAttempt!.computeNodeId};location:${diagnosis.offeringLocationId}`,
    changedFactReference: command.requestedDisposition === 'alternative_offering_recommended'
      ? `offering:${selectedOfferingId}` : `node:${selectedNodeId};location:${selectedLocationId}`,
    source: 'architecture2.phase1m.recovery', observedAt: command.decidedAt, eventId: command.evidenceEventId,
  } : undefined;
  const decision: AlternativeRecoveryDecision = {
    id: command.id, diagnosisId: diagnosis.id, failureId: diagnosis.failureId, taskId: diagnosis.taskId,
    failedAttemptId: failedAttempt?.id ?? diagnosis.attemptId!, requestedDisposition: command.requestedDisposition,
    disposition: authorized ? 'authorized' : rejection === 'no_eligible_alternative' ? 'no_candidate' : 'rejected',
    reason: rejection ?? 'alternative_binding_authorized', nextAttemptNumber: authorized ? failedAttempt!.attemptNumber + 1 : undefined,
    failedOfferingId: failedAttempt?.providerOfferingId as AlternativeRecoveryDecision['failedOfferingId'],
    failedNodeId: failedAttempt?.computeNodeId as AlternativeRecoveryDecision['failedNodeId'],
    failedLocationId: diagnosis.offeringLocationId, selectedOfferingId, selectedNodeId, selectedLocationId,
    providerResolutionId, resourceSchedulingDecisionId, changedConditionEvidenceId: evidence?.id,
    actor: command.actor, decidedAt: command.decidedAt, eventId: command.eventId,
  };
  const events: AuditEventInput[] = [];
  if (evidence) events.push({ id: evidence.eventId, aggregateType: 'task', aggregateId: diagnosis.taskId,
    eventType: 'failure.changed-condition-recorded', eventVersion: 1, actor: command.actor,
    occurredAt: command.decidedAt, payload: { diagnosisId: diagnosis.id, evidenceId: evidence.id } });
  events.push({ id: command.eventId, aggregateType: 'task', aggregateId: diagnosis.taskId,
    eventType: 'alternative-recovery.decided', eventVersion: 1, actor: command.actor,
    occurredAt: command.decidedAt, payload: { diagnosisId: diagnosis.id, disposition: decision.disposition } });
  const ready = authorized ? { ...task!, status: 'ready' as const, terminalReason: undefined, completedAt: undefined,
    version: task!.version + 1, updatedAt: command.decidedAt } : undefined;
  return persistence.recordAlternativeRecoveryDecision(decision, evidence, ready, task?.version, events);
}

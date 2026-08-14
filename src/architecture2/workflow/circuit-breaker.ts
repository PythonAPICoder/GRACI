import { createHash } from 'node:crypto';
import { asIdentifier, type AuditEventInput, type CircuitBreakerPolicy, type CircuitEvidence,
  type CircuitProbe, type CircuitRecord, type CircuitTargetType, type CircuitTransition,
  type FailureDiagnosis, type FailureDiagnosisId, type Verification } from '../domain/index.js';
import type { Architecture2Persistence } from '../persistence/index.js';
import { PHASE_1L_DIAGNOSIS_POLICY_ID, PHASE_1L_DIAGNOSIS_POLICY_VERSION } from './failure-diagnoser.js';

export const PHASE_1O_CIRCUIT_POLICY: CircuitBreakerPolicy = {
  id: 'architecture2.phase1o.circuit-breaker', version: 1,
  observationWindowMs: 300_000, failureThreshold: 3, cooldownMs: 60_000,
  qualifyingCategories: ['transient_infrastructure', 'resource_unavailable',
    'provider_or_capability_mismatch', 'execution_defect'],
};

const DEFAULT_QUALIFYING = new Set(PHASE_1O_CIRCUIT_POLICY.qualifyingCategories);

export interface RecordCircuitFailureCommand {
  targetType: CircuitTargetType;
  targetId: string;
  diagnosisId: FailureDiagnosisId;
  evidenceId: CircuitEvidence['id'];
  transitionId: CircuitTransition['id'];
  eventId: CircuitEvidence['eventId'];
  observedAt: string;
  actor: string;
  policy?: CircuitBreakerPolicy;
}

export interface AcquireCircuitProbeCommand {
  circuitId: CircuitRecord['id'];
  probeId: CircuitProbe['id'];
  transitionId: CircuitTransition['id'];
  probeEventId: CircuitProbe['eventId'];
  transitionEventId: CircuitTransition['eventId'];
  requestedAt: string;
  actor: string;
}

export interface RecordCircuitProbeOutcomeCommand {
  probeId: CircuitProbe['id'];
  transitionId: CircuitTransition['id'];
  eventId: CircuitTransition['eventId'];
  recordedAt: string;
  actor: string;
  verification?: Verification;
  failureDiagnosisId?: FailureDiagnosisId;
}

export interface ClaimCircuitProbeCommand {
  probeId: CircuitProbe['id']; taskId: NonNullable<CircuitProbe['taskId']>;
  attemptId: NonNullable<CircuitProbe['attemptId']>; attemptNumber: number;
  providerOfferingId?: CircuitProbe['providerOfferingId']; nodeId?: CircuitProbe['nodeId'];
  locationId?: CircuitProbe['locationId']; providerResolutionId?: CircuitProbe['providerResolutionId'];
  resourceSchedulingDecisionId?: CircuitProbe['resourceSchedulingDecisionId'];
  claimedAt: string; eventId: CircuitProbe['eventId']; actor: string;
}

function event(id: CircuitEvidence['eventId'], circuitId: CircuitRecord['id'], type: string,
  actor: string, occurredAt: string, payload: Record<string, unknown>): AuditEventInput {
  return { id, aggregateType: 'circuit', aggregateId: circuitId, eventType: type, eventVersion: 1,
    actor, occurredAt, payload };
}

function validatePolicy(policy: CircuitBreakerPolicy): void {
  if (!policy.id.trim() || !Number.isInteger(policy.version) || policy.version < 1 ||
      !Number.isInteger(policy.observationWindowMs) || policy.observationWindowMs < 1 ||
      !Number.isInteger(policy.failureThreshold) || policy.failureThreshold < 1 ||
      !Number.isInteger(policy.cooldownMs) || policy.cooldownMs < 1 || policy.qualifyingCategories.length === 0 ||
      policy.qualifyingCategories.some((value) => !DEFAULT_QUALIFYING.has(value)) ||
      new Set(policy.qualifyingCategories).size !== policy.qualifyingCategories.length) throw new Error('Invalid circuit-breaker policy');
}

function utc(value: string, label: string): number {
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed) || !value.endsWith('Z') || new Date(parsed).toISOString() !== value) {
    throw new Error(`Invalid canonical UTC ${label}: ${JSON.stringify(value)}`);
  }
  return parsed;
}

function circuitId(targetType: CircuitTargetType, targetId: string): CircuitRecord['id'] {
  const digest = createHash('sha256').update(`${targetType}\0${targetId}`).digest('hex').slice(0, 32);
  return asIdentifier<'Circuit'>(`circuit-${digest}`);
}

function matchesTarget(diagnosis: ReturnType<Architecture2Persistence['getFailureDiagnosisById']>,
  targetType: CircuitTargetType, targetId: string): boolean {
  if (!diagnosis) return false;
  if (targetType === 'provider_offering') return diagnosis.providerOfferingId === targetId;
  if (targetType === 'node') return diagnosis.computeNodeId === targetId;
  return diagnosis.offeringLocationId === targetId;
}

function requireQualifyingCurrentDiagnosis(persistence: Architecture2Persistence, diagnosisId: FailureDiagnosisId,
  qualifyingCategories: readonly FailureDiagnosis['cause'][] = PHASE_1O_CIRCUIT_POLICY.qualifyingCategories) {
  const diagnosis = persistence.getFailureDiagnosisById(diagnosisId);
  if (!diagnosis || diagnosis.policyId !== PHASE_1L_DIAGNOSIS_POLICY_ID ||
      diagnosis.policyVersion !== PHASE_1L_DIAGNOSIS_POLICY_VERSION ||
      diagnosis.outcomeCertainty !== 'proven_unsuccessful' || !qualifyingCategories.includes(diagnosis.cause)) {
    throw new Error('Diagnosis is not qualifying current Phase 1L circuit evidence');
  }
  const current = persistence.getFailureDiagnosis(diagnosis.failureId,
    PHASE_1L_DIAGNOSIS_POLICY_ID, PHASE_1L_DIAGNOSIS_POLICY_VERSION);
  if (current?.id !== diagnosis.id) throw new Error('Diagnosis is not current Phase 1L authority');
  return diagnosis;
}

export function circuitRoutingState(circuit: CircuitRecord | undefined, requestedAt: string):
  'available' | 'open' | 'probe_required' {
  if (!circuit || circuit.state === 'closed') return 'available';
  if (circuit.state === 'half_open') return 'probe_required';
  if (!circuit.cooldownUntil || !Number.isFinite(Date.parse(circuit.cooldownUntil)) ||
      !Number.isFinite(Date.parse(requestedAt))) throw new Error(`Malformed circuit timing: ${circuit.id}`);
  return circuit.cooldownUntil && Date.parse(requestedAt) >= Date.parse(circuit.cooldownUntil) ? 'probe_required' : 'open';
}

export function recordCircuitFailure(persistence: Architecture2Persistence,
  command: RecordCircuitFailureCommand): CircuitRecord {
  const policy = command.policy ?? PHASE_1O_CIRCUIT_POLICY;
  validatePolicy(policy);
  const diagnosis = requireQualifyingCurrentDiagnosis(persistence, command.diagnosisId, policy.qualifyingCategories);
  const observedAt = utc(command.observedAt, 'circuit evidence timestamp');
  if (observedAt !== utc(diagnosis.diagnosedAt, 'diagnosis timestamp')) {
    throw new Error('Circuit evidence timestamp must equal its authoritative diagnosis timestamp');
  }
  const failure = persistence.getFailure(diagnosis.failureId);
  if (!failure || observedAt < utc(failure.createdAt, 'Failure timestamp')) {
    throw new Error('Circuit evidence predates its authoritative Failure');
  }
  if (!matchesTarget(diagnosis, command.targetType, command.targetId)) throw new Error('Diagnosis does not attribute the circuit target');
  const id = circuitId(command.targetType, command.targetId);
  const current = persistence.getCircuits().find((value) => value.id === id);
  const start = Date.parse(command.observedAt) - policy.observationWindowMs;
  const count = (current ? persistence.getCircuitEvidence(id) : [])
    .filter((value) => Date.parse(value.observedAt) >= start && Date.parse(value.observedAt) <= Date.parse(command.observedAt)).length + 1;
  const opens = (!current || current.state === 'closed') && count >= policy.failureThreshold;
  const evidence: CircuitEvidence = { id: command.evidenceId, circuitId: id, diagnosisId: diagnosis.id,
    observedAt: command.observedAt, eventId: command.eventId };
  const transition: CircuitTransition | undefined = opens ? { id: command.transitionId, circuitId: id,
    fromState: 'closed', toState: 'open', reason: 'failure_threshold_reached', diagnosisId: diagnosis.id,
    occurredAt: command.observedAt, eventId: command.eventId } : undefined;
  return persistence.recordCircuitEvidence(command.targetType, command.targetId, diagnosis, policy, evidence, transition,
    event(command.eventId, id, opens ? 'circuit.opened' : 'circuit.evidence-recorded', command.actor,
      command.observedAt, { diagnosisId: diagnosis.id, count, threshold: policy.failureThreshold }));
}

export function acquireCircuitProbe(persistence: Architecture2Persistence, command: AcquireCircuitProbeCommand): CircuitProbe {
  utc(command.requestedAt, 'probe authorization timestamp');
  const probe: CircuitProbe = { id: command.probeId, circuitId: command.circuitId, status: 'active',
    authorizedAt: command.requestedAt, eventId: command.probeEventId };
  const transition: CircuitTransition = { id: command.transitionId, circuitId: command.circuitId,
    fromState: 'open', toState: 'half_open', reason: 'cooldown_elapsed_probe_authorized', probeId: probe.id,
    occurredAt: command.requestedAt, eventId: command.transitionEventId };
  return persistence.acquireCircuitProbe(command.circuitId, probe, transition, [
    event(command.probeEventId, command.circuitId, 'circuit.probe-authorized', command.actor, command.requestedAt,
      { probeId: probe.id }),
    event(command.transitionEventId, command.circuitId, 'circuit.half-opened', command.actor, command.requestedAt,
      { probeId: probe.id }),
  ]);
}

export function claimCircuitProbe(persistence: Architecture2Persistence, command: ClaimCircuitProbeCommand): CircuitProbe {
  utc(command.claimedAt, 'probe claim timestamp');
  const current = persistence.getCircuits().flatMap((circuit) => persistence.getCircuitProbes(circuit.id))
    .find((value) => value.id === command.probeId);
  if (!current) throw new Error(`Circuit probe not found: ${command.probeId}`);
  if (utc(command.claimedAt, 'probe claim timestamp') < utc(current.authorizedAt, 'probe authorization timestamp')) {
    throw new Error('Circuit probe claim predates its authorization');
  }
  const probe: CircuitProbe = { ...current, status: 'claimed', claimedAt: command.claimedAt,
    taskId: command.taskId, attemptId: command.attemptId, attemptNumber: command.attemptNumber,
    providerOfferingId: command.providerOfferingId, nodeId: command.nodeId, locationId: command.locationId,
    providerResolutionId: command.providerResolutionId,
    resourceSchedulingDecisionId: command.resourceSchedulingDecisionId };
  return persistence.claimCircuitProbe(probe, event(command.eventId, probe.circuitId, 'circuit.probe-claimed',
    command.actor, command.claimedAt, { probeId: probe.id, taskId: probe.taskId, attemptId: probe.attemptId }));
}

export function recordCircuitProbeOutcome(persistence: Architecture2Persistence,
  command: RecordCircuitProbeOutcomeCommand): CircuitRecord {
  if (Boolean(command.verification) === Boolean(command.failureDiagnosisId)) {
    throw new Error('Probe outcome requires exactly one Verification or qualifying Failure Diagnosis');
  }
  const probe = persistence.getCircuits().flatMap((circuit) => persistence.getCircuitProbes(circuit.id))
    .find((value) => value.id === command.probeId);
  if (!probe) throw new Error(`Circuit probe not found: ${command.probeId}`);
  const verificationRecord = command.verification;
  const recordedAt = utc(command.recordedAt, 'probe outcome timestamp');
  const circuit = persistence.getCircuits().find((value) => value.id === probe.circuitId);
  if (!circuit) throw new Error(`Circuit not found: ${probe.circuitId}`);
  if (!probe.claimedAt || recordedAt < utc(probe.claimedAt, 'probe claim timestamp')) {
    throw new Error('Circuit probe outcome predates its claim');
  }
  const diagnosis = command.failureDiagnosisId
    ? requireQualifyingCurrentDiagnosis(persistence, command.failureDiagnosisId, circuit.qualifyingCategories) : undefined;
  if (diagnosis && !matchesTarget(diagnosis, circuit.targetType, circuit.targetId)) {
    throw new Error('Probe failure diagnosis does not attribute the circuit target');
  }
  const closes = verificationRecord?.verdict === 'passed';
  if (verificationRecord && !closes) throw new Error('Only a passing normal Verification closes a circuit');
  const transition: CircuitTransition = { id: command.transitionId, circuitId: probe.circuitId,
    fromState: 'half_open', toState: closes ? 'closed' : 'open',
    reason: closes ? 'probe_verification_passed' : 'probe_qualifying_failure', probeId: probe.id,
    verificationId: verificationRecord?.id, diagnosisId: diagnosis?.id, occurredAt: command.recordedAt,
    eventId: command.eventId };
  return persistence.recordCircuitProbeOutcome(probe.id, verificationRecord, diagnosis, transition,
    [event(command.eventId, probe.circuitId, closes ? 'circuit.closed' : 'circuit.reopened', command.actor,
      command.recordedAt, { probeId: probe.id })]);
}

export function inspectCircuits(persistence: Architecture2Persistence) {
  return persistence.getCircuits().map((circuit) => ({ circuit,
    transitions: persistence.getCircuitTransitions(circuit.id), evidence: persistence.getCircuitEvidence(circuit.id),
    probes: persistence.getCircuitProbes(circuit.id) }));
}

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { DatabaseSync } from 'node:sqlite';
import { asIdentifier, type AuditEventInput, type CircuitBreakerPolicy, type Failure, type Goal,
  type Task, type TaskGraphRevision } from '../src/architecture2/domain/index.js';
import { SqliteArchitecture2Persistence } from '../src/architecture2/persistence/index.js';
import { migrations } from '../src/architecture2/persistence/sqlite/migrations.js';
import { DeterministicProviderResolver } from '../src/architecture2/providers/index.js';
import { DeterministicResourceScheduler } from '../src/architecture2/resources/index.js';
import { acquireCircuitProbe, claimCircuitProbe, createFailureDiagnosis, inspectCircuits, recordCircuitFailure,
  recordCircuitProbeOutcome } from '../src/architecture2/workflow/index.js';

const T0 = '2026-08-14T20:00:00.000Z';
const T1 = '2026-08-14T20:00:01.000Z';
const T2 = '2026-08-14T20:00:02.000Z';
const policy: CircuitBreakerPolicy = { id: 'test.phase1o', version: 1, observationWindowMs: 10_000,
  failureThreshold: 2, cooldownMs: 1_000, qualifyingCategories: ['transient_infrastructure',
    'resource_unavailable', 'provider_or_capability_mismatch', 'execution_defect'] };

describe('Architecture 2 Phase 1O circuit breakers', () => {
  let directory: string;
  let persistence: SqliteArchitecture2Persistence;
  let sequence = 0;
  const event = (aggregateId: string, eventType: string, at = T0): AuditEventInput => ({
    id: asIdentifier<'Event'>(`phase1o-event-${++sequence}`), aggregateType: 'test', aggregateId,
    eventType, eventVersion: 1, actor: 'phase1o-test', occurredAt: at, payload: {},
  });

  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'graci-phase1o-'));
    persistence = new SqliteArchitecture2Persistence({ databasePath: join(directory, 'circuit.sqlite') });
    persistence.initialize();
    sequence = 0;
    seed();
  });
  afterEach(() => { persistence.close(); rmSync(directory, { recursive: true, force: true }); });

  function seed(): void {
    const goal: Goal = { id: asIdentifier<'Goal'>('circuit-goal'), objective: 'Circuit test', constraints: {},
      priority: 'normal', privacyClass: 'internal', status: 'active', version: 1, createdAt: T0, updatedAt: T0 };
    persistence.createGoal({ goal, criteria: [] }, event(goal.id, 'goal.created'));
    const graph: TaskGraphRevision = { id: asIdentifier<'TaskGraphRevision'>('circuit-graph'), goalId: goal.id,
      revision: 1, createdAt: T0 };
    persistence.createTaskGraphRevision(graph, event(graph.id, 'graph.created'));
    const task: Task = { id: asIdentifier<'Task'>('circuit-task'), goalId: goal.id, graphRevisionId: graph.id,
      title: 'Circuit', objective: 'Exercise circuit', inputs: {}, requiredCapabilities: ['text.generate'],
      privacyClass: 'internal', priority: 'normal', status: 'planned', required: true, retryPolicy: { maxAttempts: 5 },
      verificationPlan: {}, version: 1, createdAt: T0, updatedAt: T0 };
    persistence.createTask(task, event(task.id, 'task.created'));
    persistence.registerProvider({ provider: { id: asIdentifier<'Provider'>('circuit-provider'), adapterType: 'test',
      adapterVersion: '1', configurationReference: 'test', createdAt: T0 }, capabilities: [{
      id: asIdentifier<'Capability'>('text.generate'), contractVersion: 1, description: 'text',
      inputSchemaReference: 'in', outputSchemaReference: 'out', createdAt: T0 }], offerings: [{
      id: asIdentifier<'ProviderOffering'>('circuit-offering'), providerId: asIdentifier<'Provider'>('circuit-provider'),
      capabilityId: asIdentifier<'Capability'>('text.generate'), contractVersion: 1, privacyDestinations: ['internal'],
      permissions: [], features: [], supportedFormats: [], inputSchemaReference: 'in', outputSchemaReference: 'out',
      qualificationFingerprint: 'q1', qualityLevel: 1, expectedLatencyMs: 1, maximumCost: 0,
      sideEffectClass: 'none', createdAt: T0 }] }, [event('circuit-provider', 'provider.registered')]);
    persistence.recordQualification({ id: asIdentifier<'Qualification'>('circuit-qualification'),
      offeringId: asIdentifier<'ProviderOffering'>('circuit-offering'), status: 'qualified', level: 1, evidence: {},
      qualifiedAt: T0, triggerFingerprint: 'q1' }, event('circuit-offering', 'offering.qualified'));
    persistence.recordProviderHealth({ id: asIdentifier<'HealthObservation'>('circuit-provider-health'),
      offeringId: asIdentifier<'ProviderOffering'>('circuit-offering'), status: 'healthy', evidence: {}, observedAt: T0 },
    event('circuit-offering', 'offering.health'));
    persistence.registerNode({ id: asIdentifier<'Node'>('circuit-node'), name: 'Node', administrativeState: 'active',
      configurationReference: 'node', createdAt: T0 }, [{ id: asIdentifier<'OfferingLocation'>('circuit-location'),
      nodeId: asIdentifier<'Node'>('circuit-node'), offeringId: asIdentifier<'ProviderOffering'>('circuit-offering'),
      enabled: true, capacity: 1, privacyClasses: ['internal'], createdAt: T0 }],
    [event('circuit-node', 'node.registered')]);
    persistence.recordNodeHealth({ id: asIdentifier<'NodeHealthObservation'>('circuit-node-health'),
      nodeId: asIdentifier<'Node'>('circuit-node'), status: 'healthy', observedAt: T0 }, event('circuit-node', 'node.health'));
  }

  function diagnosis(number: number, category: Failure['category'] = 'execution_defect',
    at = number === 1 ? T0 : T1) {
    const task = persistence.getTask(asIdentifier<'Task'>('circuit-task'))!;
    const attempt = { id: asIdentifier<'Attempt'>(`circuit-attempt-${number}`), taskId: task.id, attemptNumber: number,
      status: 'failed' as const, providerOfferingId: 'circuit-offering', computeNodeId: 'circuit-node', inputSnapshot: {},
      result: {}, completedAt: at, createdAt: at };
    persistence.createAttempt(attempt, event(task.id, 'attempt.created'));
    const failure: Failure = { id: asIdentifier<'Failure'>(`circuit-failure-${number}`), taskId: task.id,
      attemptId: attempt.id, category, classification: 'permanent', code: 'FAILED', summary: 'failed', details: {},
      retryable: false, createdAt: attempt.createdAt };
    persistence.createFailure(failure, event(task.id, 'failure.recorded'));
    const diagnosisEvent = event(task.id, 'failure.diagnosed', attempt.createdAt);
    const value = createFailureDiagnosis({ evidence: { task, failure, attempts: persistence.getAttempts(task.id), attempt,
      offeringLocationId: asIdentifier<'OfferingLocation'>('circuit-location') }, eventId: diagnosisEvent.id,
      diagnosedAt: attempt.createdAt, diagnosedBy: 'phase1o-test' });
    return persistence.recordFailureDiagnosis(value, diagnosisEvent);
  }

  function observe(diagnosisId: ReturnType<typeof diagnosis>['id'], n: number, at: string) {
    return recordCircuitFailure(persistence, { targetType: 'provider_offering', targetId: 'circuit-offering', diagnosisId,
      evidenceId: asIdentifier<'CircuitEvidence'>(`circuit-evidence-${n}`),
      transitionId: asIdentifier<'CircuitTransition'>(`circuit-transition-${n}`),
      eventId: event('unused', 'circuit.evidence', at).id, observedAt: at, actor: 'phase1o-test', policy });
  }

  function claimProviderProbe(probeId: ReturnType<typeof acquireCircuitProbe>['id'], attemptId: string,
    attemptNumber: number, id: string) {
    const resolver = new DeterministicProviderResolver(persistence, { nextEvent: (decision) =>
      event(decision.request.id, 'provider-resolution.recorded', decision.decidedAt) });
    const decision = resolver.resolve({ id: asIdentifier<'ResolutionDecision'>(`probe-resolution-${id}`),
      capabilityId: asIdentifier<'Capability'>('text.generate'), contractVersion: 1, privacyClass: 'internal',
      requiredPermissions: [], requiredFeatures: [], minimumQualificationLevel: 1, maximumHealthAgeMs: 10_000,
      requestedAt: T2, circuitProbeId: probeId });
    expect(decision.selectedOfferingId).toBe('circuit-offering');
    return claimCircuitProbe(persistence, { probeId, taskId: asIdentifier<'Task'>('circuit-task'),
      attemptId: asIdentifier<'Attempt'>(attemptId), attemptNumber,
      providerOfferingId: asIdentifier<'ProviderOffering'>('circuit-offering'), providerResolutionId: decision.request.id,
      claimedAt: T2, eventId: event('unused', 'probe.claimed', T2).id, actor: 'phase1o-test' });
  }

  function openScopedCircuit(targetType: 'node' | 'offering_location', id: string) {
    for (const [number, value] of [[1, diagnosis(1)], [2, diagnosis(2)]] as const) recordCircuitFailure(persistence, {
      targetType, targetId: targetType === 'node' ? 'circuit-node' : 'circuit-location', diagnosisId: value.id,
      evidenceId: asIdentifier<'CircuitEvidence'>(`${id}-evidence-${number}`),
      transitionId: asIdentifier<'CircuitTransition'>(`${id}-open-${number}`),
      eventId: event('unused', 'circuit.evidence', number === 1 ? T0 : T1).id,
      observedAt: number === 1 ? T0 : T1, actor: 'phase1o-test', policy });
    return persistence.getCircuits().find((value) => value.targetType === targetType)!;
  }

  function resourceDecision(probeId: ReturnType<typeof acquireCircuitProbe>['id'], id: string) {
    const request = { id: asIdentifier<'ResourceSchedulingDecision'>(`probe-resource-${id}`),
      offeringId: asIdentifier<'ProviderOffering'>('circuit-offering'), privacyClass: 'internal' as const,
      requiredCapacity: 1, maximumHealthAgeMs: 10_000, requestedAt: T2, circuitProbeId: probeId };
    return new DeterministicResourceScheduler().schedule(request, { nodes: persistence.getNodes(),
      locations: persistence.getOfferingLocations(), healthObservations: persistence.getNodeHealth(asIdentifier<'Node'>('circuit-node')),
      leases: persistence.getResourceLeases(), circuits: persistence.getCircuits(),
      circuitProbes: persistence.getCircuits().flatMap((circuit) => persistence.getCircuitProbes(circuit.id)) });
  }

  it('opens only at the bounded qualifying threshold and keeps scopes isolated', () => {
    const first = diagnosis(1);
    expect(observe(first.id, 1, T0).state).toBe('closed');
    const nonqualifying = diagnosis(2, 'verification_failure');
    expect(() => observe(nonqualifying.id, 2, T1)).toThrow(/not qualifying/);
    const second = diagnosis(3);
    const opened = observe(second.id, 3, T1);
    expect(opened).toMatchObject({ state: 'open', targetType: 'provider_offering', targetId: 'circuit-offering' });
    expect(inspectCircuits(persistence)[0]).toMatchObject({ evidence: [{ diagnosisId: first.id }, { diagnosisId: second.id }] });
    expect(persistence.getCircuits().some((value) => value.targetType === 'node')).toBe(false);
  });

  it('does not combine qualifying failures outside the observation window', () => {
    const narrow = { ...policy, id: 'test.phase1o.narrow', observationWindowMs: 500 };
    const first = diagnosis(1);
    const second = diagnosis(2);
    const command = (value: ReturnType<typeof diagnosis>, n: number, at: string) => recordCircuitFailure(persistence, {
      targetType: 'provider_offering', targetId: 'circuit-offering', diagnosisId: value.id,
      evidenceId: asIdentifier<'CircuitEvidence'>(`window-evidence-${n}`),
      transitionId: asIdentifier<'CircuitTransition'>(`window-transition-${n}`),
      eventId: event('unused', 'circuit.evidence', at).id, observedAt: at, actor: 'phase1o-test', policy: narrow });
    expect(command(first, 1, T0).state).toBe('closed');
    expect(command(second, 2, T1).state).toBe('closed');
  });

  it('filters provider, node, and location routing with distinct open and probe reasons', () => {
    observe(diagnosis(1).id, 1, T0); observe(diagnosis(2).id, 2, T1);
    const resolver = new DeterministicProviderResolver(persistence, { nextEvent: (decision) =>
      event(decision.request.id, 'provider-resolution.recorded', decision.decidedAt) });
    const request = { id: asIdentifier<'ResolutionDecision'>('circuit-resolution'),
      capabilityId: asIdentifier<'Capability'>('text.generate'), contractVersion: 1, privacyClass: 'internal' as const,
      requiredPermissions: [], requiredFeatures: [], minimumQualificationLevel: 1, maximumHealthAgeMs: 10_000,
      requestedAt: T1 };
    expect(resolver.resolve(request).candidates[0]?.rejectionReasons).toContain('circuit_open');
    expect(resolver.resolve({ ...request, id: asIdentifier<'ResolutionDecision'>('circuit-resolution-cool'), requestedAt: T2 })
      .candidates[0]?.rejectionReasons).toContain('circuit_probe_required');

    const scopedDiagnoses = [[10, diagnosis(3)], [11, diagnosis(4)]] as const;
    for (const targetType of ['node', 'offering_location'] as const) {
      for (const [n, d] of scopedDiagnoses) recordCircuitFailure(persistence, {
        targetType, targetId: targetType === 'node' ? 'circuit-node' : 'circuit-location', diagnosisId: d.id,
        evidenceId: asIdentifier<'CircuitEvidence'>(`${targetType}-evidence-${n}`),
        transitionId: asIdentifier<'CircuitTransition'>(`${targetType}-transition-${n}`),
        eventId: event('unused', 'circuit.evidence', T1).id, observedAt: T1,
        actor: 'phase1o-test', policy });
    }
    const decision = new DeterministicResourceScheduler().schedule({ id: asIdentifier<'ResourceSchedulingDecision'>('circuit-resource'),
      offeringId: asIdentifier<'ProviderOffering'>('circuit-offering'), privacyClass: 'internal', requiredCapacity: 1,
      maximumHealthAgeMs: 10_000, requestedAt: T1 }, { nodes: persistence.getNodes(),
      locations: persistence.getOfferingLocations(), healthObservations: persistence.getNodeHealth(asIdentifier<'Node'>('circuit-node')),
      leases: [], circuits: persistence.getCircuits() });
    expect(decision.candidates[0]?.rejectionReasons).toEqual(expect.arrayContaining(['node_circuit_open', 'location_circuit_open']));
  });

  it('grants one durable probe, requires passing Verification to close, and prevents reuse', () => {
    observe(diagnosis(1).id, 1, T0); const opened = observe(diagnosis(2).id, 2, T1);
    const probe = acquireCircuitProbe(persistence, { circuitId: opened.id, probeId: asIdentifier<'CircuitProbe'>('probe-1'),
      transitionId: asIdentifier<'CircuitTransition'>('probe-half-open'), probeEventId: event(opened.id, 'probe', T2).id,
      transitionEventId: event(opened.id, 'half-open', T2).id, requestedAt: T2, actor: 'phase1o-test' });
    claimProviderProbe(probe.id, 'probe-attempt', 3, 'close');
    expect(() => acquireCircuitProbe(persistence, { circuitId: opened.id, probeId: asIdentifier<'CircuitProbe'>('probe-2'),
      transitionId: asIdentifier<'CircuitTransition'>('probe-half-open-2'), probeEventId: event(opened.id, 'probe', T2).id,
      transitionEventId: event(opened.id, 'half-open', T2).id, requestedAt: T2, actor: 'phase1o-test' })).toThrow();
    const task = persistence.getTask(asIdentifier<'Task'>('circuit-task'))!;
    const successful = { id: asIdentifier<'Attempt'>('probe-attempt'), taskId: task.id, attemptNumber: 3,
      status: 'succeeded' as const, providerOfferingId: 'circuit-offering', inputSnapshot: {}, result: {},
      completedAt: T2, createdAt: T2 };
    persistence.createAttempt(successful, event(task.id, 'attempt.created', T2));
    const verification = { id: asIdentifier<'Verification'>('probe-verification'), taskId: task.id, attemptId: successful.id,
      verdict: 'passed' as const, planVersion: 1, verifier: 'normal-verifier', criterionResults: {}, evidence: {}, createdAt: T2 };
    persistence.createVerification(verification, event(task.id, 'verification.recorded', T2));
    expect(() => recordCircuitProbeOutcome(persistence, { probeId: probe.id,
      transitionId: asIdentifier<'CircuitTransition'>('probe-no-verification'),
      eventId: event(opened.id, 'close-without-verification', T2).id, recordedAt: T2,
      actor: 'phase1o-test' })).toThrow(/exactly one Verification/);
    expect(recordCircuitProbeOutcome(persistence, { probeId: probe.id,
      transitionId: asIdentifier<'CircuitTransition'>('probe-close'), eventId: event(opened.id, 'close', T2).id,
      recordedAt: T2, actor: 'phase1o-test', verification }).state).toBe('closed');
    expect(() => recordCircuitProbeOutcome(persistence, { probeId: probe.id,
      transitionId: asIdentifier<'CircuitTransition'>('probe-reuse'), eventId: event(opened.id, 'reuse', T2).id,
      recordedAt: T2, actor: 'phase1o-test', verification })).toThrow(/not claimed/);
  });

  it('permits exact probe routing only until the authority is claimed once', () => {
    observe(diagnosis(1).id, 1, T0); const opened = observe(diagnosis(2).id, 2, T1);
    const probe = acquireCircuitProbe(persistence, { circuitId: opened.id, probeId: asIdentifier<'CircuitProbe'>('route-probe'),
      transitionId: asIdentifier<'CircuitTransition'>('route-half'), probeEventId: event(opened.id, 'probe', T2).id,
      transitionEventId: event(opened.id, 'half', T2).id, requestedAt: T2, actor: 'phase1o-test' });
    const resolver = new DeterministicProviderResolver(persistence, { nextEvent: (decision) =>
      event(decision.request.id, 'provider-resolution.recorded', decision.decidedAt) });
    const base = { capabilityId: asIdentifier<'Capability'>('text.generate'), contractVersion: 1,
      privacyClass: 'internal' as const, requiredPermissions: [] as string[], requiredFeatures: [] as string[],
      minimumQualificationLevel: 1, maximumHealthAgeMs: 10_000, requestedAt: T2 };
    expect(resolver.resolve({ ...base, id: asIdentifier<'ResolutionDecision'>('route-without') })
      .candidates[0]?.rejectionReasons).toContain('circuit_probe_required');
    const routed = resolver.resolve({ ...base, id: asIdentifier<'ResolutionDecision'>('route-with'), circuitProbeId: probe.id });
    expect(routed.selectedOfferingId).toBe('circuit-offering');
    const claim = { probeId: probe.id, taskId: asIdentifier<'Task'>('circuit-task'),
      attemptId: asIdentifier<'Attempt'>('route-attempt'), attemptNumber: 3,
      providerOfferingId: asIdentifier<'ProviderOffering'>('circuit-offering'), providerResolutionId: routed.request.id,
      claimedAt: T2, eventId: event('unused', 'probe.claimed', T2).id, actor: 'phase1o-test' };
    claimCircuitProbe(persistence, claim);
    expect(() => claimCircuitProbe(persistence, { ...claim,
      eventId: event('unused', 'probe.claimed-again', T2).id })).toThrow(/already claimed/);
    expect(resolver.resolve({ ...base, id: asIdentifier<'ResolutionDecision'>('route-reuse'), circuitProbeId: probe.id })
      .candidates[0]?.rejectionReasons).toContain('circuit_probe_required');
    const task = persistence.getTask(asIdentifier<'Task'>('circuit-task'))!;
    const running = { ...task, status: 'running' as const, version: task.version + 1, updatedAt: T2 };
    const wrongAttempt = { id: asIdentifier<'Attempt'>('wrong-route-attempt'), taskId: task.id, attemptNumber: 3,
      status: 'running' as const, providerOfferingId: 'circuit-offering', inputSnapshot: {}, startedAt: T2, createdAt: T2 };
    expect(() => persistence.startAttempt(running, task.version, wrongAttempt,
      [event(task.id, 'attempt.started', T2)], undefined, undefined, probe.id)).toThrow(/does not match claimed/);
    const exactAttempt = { ...wrongAttempt, id: claim.attemptId };
    persistence.startAttempt(running, task.version, exactAttempt,
      [event(task.id, 'attempt.started', T2)], undefined, undefined, probe.id);
    expect(persistence.getAttempts(task.id).at(-1)?.id).toBe(claim.attemptId);
  });

  it('keeps circuit state separate from provider health, Node administration, and location enablement', () => {
    observe(diagnosis(1).id, 1, T0); observe(diagnosis(2).id, 2, T1);
    expect(persistence.getProviderHealth(asIdentifier<'ProviderOffering'>('circuit-offering')).at(-1)?.status).toBe('healthy');
    expect(persistence.getNodes()[0]?.administrativeState).toBe('active');
    expect(persistence.getOfferingLocations()[0]?.enabled).toBe(true);
  });

  it('permits exact Node probe routing while unrelated resource routes remain blocked', () => {
    const opened = openScopedCircuit('node', 'node-probe');
    const probe = acquireCircuitProbe(persistence, { circuitId: opened.id, probeId: asIdentifier<'CircuitProbe'>('node-probe'),
      transitionId: asIdentifier<'CircuitTransition'>('node-half'), probeEventId: event(opened.id, 'probe', T2).id,
      transitionEventId: event(opened.id, 'half', T2).id, requestedAt: T2, actor: 'phase1o-test' });
    expect(resourceDecision(asIdentifier<'CircuitProbe'>('wrong-node-probe'), 'node-wrong').candidates[0]?.rejectionReasons)
      .toContain('node_circuit_probe_required');
    expect(resourceDecision(probe.id, 'node-exact').selectedNodeId).toBe('circuit-node');
  });

  it('claims an exact location probe route once and rejects scheduler reuse', () => {
    const opened = openScopedCircuit('offering_location', 'location-probe');
    const probe = acquireCircuitProbe(persistence, { circuitId: opened.id,
      probeId: asIdentifier<'CircuitProbe'>('location-probe'), transitionId: asIdentifier<'CircuitTransition'>('location-half'),
      probeEventId: event(opened.id, 'probe', T2).id, transitionEventId: event(opened.id, 'half', T2).id,
      requestedAt: T2, actor: 'phase1o-test' });
    const decision = resourceDecision(probe.id, 'location-exact');
    const lease = { id: asIdentifier<'ResourceLease'>('location-probe-lease'), decisionId: decision.request.id,
      offeringId: decision.request.offeringId, locationId: decision.selectedLocationId!, nodeId: decision.selectedNodeId!,
      capacity: 1, status: 'active' as const, acquiredAt: T2, expiresAt: '2026-08-14T20:01:02.000Z' };
    persistence.recordResourceSchedulingDecision(decision, lease, [event(opened.id, 'resource.scheduled', T2)]);
    claimCircuitProbe(persistence, { probeId: probe.id, taskId: asIdentifier<'Task'>('circuit-task'),
      attemptId: asIdentifier<'Attempt'>('location-probe-attempt'), attemptNumber: 3,
      providerOfferingId: asIdentifier<'ProviderOffering'>('circuit-offering'), nodeId: decision.selectedNodeId,
      locationId: decision.selectedLocationId, resourceSchedulingDecisionId: decision.request.id,
      claimedAt: T2, eventId: event(opened.id, 'probe.claimed', T2).id, actor: 'phase1o-test' });
    expect(resourceDecision(probe.id, 'location-reuse').candidates[0]?.rejectionReasons)
      .toContain('location_circuit_probe_required');
  });

  it('rejects a passing Verification from an Attempt unrelated to the claimed probe', () => {
    observe(diagnosis(1).id, 1, T0); const opened = observe(diagnosis(2).id, 2, T1);
    const probe = acquireCircuitProbe(persistence, { circuitId: opened.id, probeId: asIdentifier<'CircuitProbe'>('unrelated-probe'),
      transitionId: asIdentifier<'CircuitTransition'>('unrelated-half'), probeEventId: event(opened.id, 'probe', T2).id,
      transitionEventId: event(opened.id, 'half', T2).id, requestedAt: T2, actor: 'phase1o-test' });
    claimProviderProbe(probe.id, 'bound-attempt', 3, 'unrelated');
    const task = persistence.getTask(asIdentifier<'Task'>('circuit-task'))!;
    const unrelated = { id: asIdentifier<'Attempt'>('unrelated-attempt'), taskId: task.id, attemptNumber: 4,
      status: 'succeeded' as const, providerOfferingId: 'circuit-offering', inputSnapshot: {}, result: {},
      completedAt: T2, createdAt: T2 };
    persistence.createAttempt(unrelated, event(task.id, 'attempt.created', T2));
    const verification = { id: asIdentifier<'Verification'>('unrelated-verification'), taskId: task.id,
      attemptId: unrelated.id, verdict: 'passed' as const, planVersion: 1, verifier: 'normal',
      criterionResults: {}, evidence: {}, createdAt: T2 };
    persistence.createVerification(verification, event(task.id, 'verification.recorded', T2));
    expect(() => recordCircuitProbeOutcome(persistence, { probeId: probe.id,
      transitionId: asIdentifier<'CircuitTransition'>('unrelated-close'), eventId: event(opened.id, 'close', T2).id,
      recordedAt: T2, actor: 'phase1o-test', verification })).toThrow(/bound circuit probe Attempt/);
    expect(persistence.getCircuits().find((value) => value.id === opened.id)?.state).toBe('half_open');
  });

  it('reopens on a qualifying probe failure and reconstructs schema 12 state after restart', () => {
    observe(diagnosis(1).id, 1, T0); const opened = observe(diagnosis(2).id, 2, T1);
    const probe = acquireCircuitProbe(persistence, { circuitId: opened.id, probeId: asIdentifier<'CircuitProbe'>('probe-fail'),
      transitionId: asIdentifier<'CircuitTransition'>('probe-fail-half'), probeEventId: event(opened.id, 'probe', T2).id,
      transitionEventId: event(opened.id, 'half-open', T2).id, requestedAt: T2, actor: 'phase1o-test' });
    claimProviderProbe(probe.id, 'circuit-attempt-3', 3, 'failure');
    const failed = diagnosis(3);
    expect(recordCircuitProbeOutcome(persistence, { probeId: probe.id,
      transitionId: asIdentifier<'CircuitTransition'>('probe-reopen'), eventId: event(opened.id, 'reopen', T2).id,
      recordedAt: T2, actor: 'phase1o-test', failureDiagnosisId: failed.id }).state).toBe('open');
    const before = inspectCircuits(persistence);
    const path = join(directory, 'circuit.sqlite'); persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    expect(persistence.getSchemaVersion()).toBe(15);
    expect(inspectCircuits(persistence)).toEqual(before);
  });

  it('migrates a populated schema 11 database to schema 12 without fabricating circuits', () => {
    persistence.close();
    const path = join(directory, 'schema11.sqlite');
    const prior = new DatabaseSync(path);
    prior.exec(`CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
      applied_at TEXT NOT NULL) STRICT;`);
    for (const migration of migrations.slice(0, 11)) {
      migration.up(prior);
      prior.prepare('INSERT INTO schema_migrations VALUES (?, ?, ?)').run(migration.version, migration.name, T0);
    }
    prior.prepare(`INSERT INTO events(id,aggregate_type,aggregate_id,event_type,event_version,actor,occurred_at,
      payload_json,previous_hash,event_hash) VALUES (?,?,?,?,?,?,?,?,?,?)`)
      .run('schema11-event', 'test', 'schema11', 'schema11.populated', 1, 'test', T0, '{}', null, 'a'.repeat(64));
    prior.exec('PRAGMA user_version = 11'); prior.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    expect(persistence.getSchemaVersion()).toBe(15);
    expect(persistence.getEvents()).toHaveLength(1);
    expect(persistence.getCircuits()).toEqual([]);
  });
});

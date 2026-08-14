import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { asIdentifier, type AuditEventInput, type Failure, type Goal, type Task,
  type TaskGraphRevision, type ResourceLease, type ResourceSchedulingDecision } from '../src/architecture2/domain/index.js';
import { DeterministicTestProvider, type TaskExecutionProvider } from '../src/architecture2/execution/index.js';
import { SqliteArchitecture2Persistence } from '../src/architecture2/persistence/index.js';
import { DeterministicVerifier } from '../src/architecture2/verification/index.js';
import { DeterministicResourceScheduler } from '../src/architecture2/resources/index.js';
import { createFailureDiagnosis, diagnosePersistedFailure, MinimalOrchestrator, recoverWithAlternative } from '../src/architecture2/workflow/index.js';

const NOW = '2026-08-14T20:00:00.000Z';

describe('Architecture 2 Phase 1M bounded alternative recovery', () => {
  let directory: string;
  let persistence: SqliteArchitecture2Persistence;
  let sequence: number;

  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'graci-phase1m-'));
    persistence = new SqliteArchitecture2Persistence({ databasePath: join(directory, 'recovery.sqlite') });
    persistence.initialize();
    sequence = 0;
  });
  afterEach(() => { persistence.close(); rmSync(directory, { recursive: true, force: true }); });

  const event = (aggregateId: string, eventType: string): AuditEventInput => ({
    id: asIdentifier<'Event'>(`phase1m-event-${++sequence}`), aggregateType: 'test', aggregateId,
    eventType, eventVersion: 1, actor: 'phase1m-test', occurredAt: NOW, payload: {},
  });

  function seed(retryPolicy: Task['retryPolicy'] = { maxAttempts: 2 }): Task {
    const goal: Goal = { id: asIdentifier<'Goal'>('phase1m-goal'), objective: 'Recover', constraints: {},
      priority: 'normal', privacyClass: 'internal', status: 'active', version: 1, createdAt: NOW, updatedAt: NOW };
    persistence.createGoal({ goal, criteria: [] }, event(goal.id, 'goal.created'));
    const revision: TaskGraphRevision = { id: asIdentifier<'TaskGraphRevision'>('phase1m-graph'), goalId: goal.id,
      revision: 1, createdAt: NOW };
    persistence.createTaskGraphRevision(revision, event(revision.id, 'graph.created'));
    const task: Task = { id: asIdentifier<'Task'>('phase1m-task'), goalId: goal.id, graphRevisionId: revision.id,
      title: 'Recover', objective: 'Use an alternative offering', inputs: {}, requiredCapabilities: ['text.generate'],
      privacyClass: 'internal', priority: 'normal', status: 'planned', required: true, retryPolicy,
      verificationPlan: {}, version: 1, createdAt: NOW, updatedAt: NOW };
    persistence.createTask(task, event(task.id, 'task.created'));
    return task;
  }

  function registerOffering(id: 'offering-old' | 'offering-new', includeCapability: boolean): void {
    const capabilityId = asIdentifier<'Capability'>('text.generate');
    const offeringId = asIdentifier<'ProviderOffering'>(id);
    persistence.registerProvider({ provider: { id: asIdentifier<'Provider'>(`provider-${id}`), adapterType: 'test',
      adapterVersion: '1', configurationReference: `config:${id}`, createdAt: NOW },
    capabilities: includeCapability ? [{ id: capabilityId, contractVersion: 1, description: 'text',
      inputSchemaReference: 'input:1', outputSchemaReference: 'output:1', createdAt: NOW }] : [],
    offerings: [{ id: offeringId, providerId: asIdentifier<'Provider'>(`provider-${id}`), capabilityId,
      contractVersion: 1, privacyDestinations: ['internal'], permissions: [], features: ['text'],
      supportedFormats: ['text/plain'], inputSchemaReference: 'input:1', outputSchemaReference: 'output:1',
      qualificationFingerprint: 'qualified:1', qualityLevel: 1, expectedLatencyMs: 10, maximumCost: 0,
      sideEffectClass: 'none', createdAt: NOW }] }, [event(id, 'provider.registered')]);
    persistence.recordQualification({ id: asIdentifier<'Qualification'>(`qualification-${id}`), offeringId,
      status: 'qualified', level: 1, evidence: {}, qualifiedAt: NOW, triggerFingerprint: 'qualified:1' },
    event(id, 'offering.qualified'));
    persistence.recordProviderHealth({ id: asIdentifier<'HealthObservation'>(`health-${id}`), offeringId,
      status: 'healthy', evidence: {}, observedAt: NOW }, event(id, 'offering.health'));
  }

  function registerRecoveryNodes(): void {
    const offeringId = asIdentifier<'ProviderOffering'>('offering-old');
    for (const suffix of ['a', 'b', 'c'] as const) {
      const nodeId = asIdentifier<'Node'>(`node-${suffix}`);
      persistence.registerNode({ id: nodeId, name: `Node ${suffix}`, administrativeState: 'active',
        configurationReference: `node:${suffix}`, createdAt: NOW }, [{
        id: asIdentifier<'OfferingLocation'>(`location-${suffix}`), nodeId, offeringId, enabled: true,
        capacity: suffix === 'c' ? 2 : 1, privacyClasses: ['internal'], createdAt: NOW,
      }], [event(nodeId, 'node.registered')]);
      persistence.recordNodeHealth({ id: asIdentifier<'NodeHealthObservation'>(`node-health-${suffix}`), nodeId,
        status: 'healthy', observedAt: NOW }, event(nodeId, 'node.health'));
    }
  }

  function resourceBinding(task: Task, offeringId: 'offering-old', suffix: 'a' | 'b' | 'c', id: string) {
    const request = { id: asIdentifier<'ResourceSchedulingDecision'>(`resource-${id}`),
      offeringId: asIdentifier<'ProviderOffering'>(offeringId), privacyClass: task.privacyClass,
      requiredCapacity: 1, maximumHealthAgeMs: 60_000, requestedAt: NOW };
    const decision = new DeterministicResourceScheduler().schedule(request, {
      nodes: persistence.getNodes(), locations: persistence.getOfferingLocations(request.offeringId),
      healthObservations: persistence.getNodes().flatMap((node) => persistence.getNodeHealth(node.id)),
      leases: persistence.getResourceLeases(),
    });
    const locationId = asIdentifier<'OfferingLocation'>(`location-${suffix}`);
    const nodeId = asIdentifier<'Node'>(`node-${suffix}`);
    const forced: ResourceSchedulingDecision = { ...decision, selectedLocationId: locationId, selectedNodeId: nodeId };
    const lease: ResourceLease = { id: asIdentifier<'ResourceLease'>(`lease-${id}`), decisionId: request.id,
      offeringId: request.offeringId, locationId, nodeId, capacity: 1, status: 'active', acquiredAt: NOW,
      expiresAt: '2026-08-14T20:01:00.000Z' };
    return { decision: forced, lease };
  }

  async function prepareNodeDiagnosis(retryPolicy: Task['retryPolicy'] = { maxAttempts: 3 }) {
    const task = seed(retryPolicy);
    registerOffering('offering-old', true);
    registerRecoveryNodes();
    const failedProvider = new DeterministicTestProvider(new Map([[task.id,
      { outcome: 'failure', classification: 'permanent' }]]));
    Object.defineProperty(failedProvider, 'providerId', { value: 'offering-old' });
    let id = 0;
    await new MinimalOrchestrator(persistence, failedProvider, new DeterministicVerifier(), {
      now: () => NOW, nextId: (kind) => `${kind}-node-initial-${++id}`,
      resolveOffering: () => asIdentifier<'ProviderOffering'>('offering-old'),
      acquireResource: (value) => resourceBinding(value, 'offering-old', 'a', 'initial-a'),
    }).run(task.graphRevisionId);
    const currentTask = persistence.getTask(task.id)!;
    const attempt = persistence.getAttempts(task.id)[0]!;
    const failure: Failure = { id: asIdentifier<'Failure'>('failure-resource-unavailable'), taskId: task.id,
      attemptId: attempt.id, category: 'resource_unavailable', classification: 'permanent', code: 'NODE_FAILED',
      summary: 'The failed Node cannot execute this work', details: {}, retryable: false, createdAt: NOW };
    persistence.createFailure(failure, event(task.id, 'failure.recorded'));
    const diagnosisEvent = event(task.id, 'failure.diagnosed');
    const diagnosis = createFailureDiagnosis({ evidence: { task: currentTask, failure,
      attempts: [attempt], attempt, offeringLocationId: asIdentifier<'OfferingLocation'>('location-a') },
    eventId: diagnosisEvent.id, diagnosedAt: NOW, diagnosedBy: 'phase1m-test' });
    persistence.recordFailureDiagnosis(diagnosis, diagnosisEvent);
    return { task, attempt, failure, diagnosis };
  }

  function nodeRecoveryCommand(diagnosisId: ReturnType<typeof createFailureDiagnosis>['id'], taskId: Task['id'], id: string) {
    return { id: asIdentifier<'AlternativeRecoveryDecision'>(`recovery-${id}`), diagnosisId,
      requestedDisposition: 'alternative_node_recommended' as const, actor: 'phase1m-test', decidedAt: NOW,
      eventId: event(taskId, 'alternative-recovery.decided').id,
      evidenceId: asIdentifier<'ChangedConditionEvidence'>(`evidence-${id}`),
      evidenceEventId: event(taskId, 'failure.changed-condition-recorded').id,
      resourceRequest: { id: asIdentifier<'ResourceSchedulingDecision'>(`recovery-resource-${id}`),
        offeringId: asIdentifier<'ProviderOffering'>('offering-old'), privacyClass: 'internal' as const,
        requiredCapacity: 1, maximumHealthAgeMs: 60_000, requestedAt: NOW },
    };
  }

  async function prepareAlternativeDiagnosis() {
    const task = seed();
    registerOffering('offering-old', true);
    registerOffering('offering-new', false);
    const failedProvider = new DeterministicTestProvider(new Map([[task.id, { outcome: 'failure', classification: 'permanent' }]]));
    Object.defineProperty(failedProvider, 'providerId', { value: 'offering-old' });
    let id = 0;
    await new MinimalOrchestrator(persistence, failedProvider, new DeterministicVerifier(), {
      now: () => NOW, nextId: (kind) => `${kind}-phase1m-${++id}`,
      resolveOffering: () => asIdentifier<'ProviderOffering'>('offering-old'),
    }).run(task.graphRevisionId);
    const attempt = persistence.getAttempts(task.id)[0]!;
    const failure: Failure = { id: asIdentifier<'Failure'>('failure-provider-mismatch'), taskId: task.id,
      attemptId: attempt.id, category: 'provider_or_capability_mismatch', classification: 'permanent',
      code: 'PROVIDER_MISMATCH', summary: 'Failed offering is unsuitable', details: {}, retryable: false, createdAt: NOW };
    persistence.createFailure(failure, event(task.id, 'failure.recorded'));
    const diagnosis = diagnosePersistedFailure(persistence, { failureId: failure.id,
      eventId: event(task.id, 'failure.diagnosed').id, diagnosedAt: NOW, diagnosedBy: 'phase1m-test' });
    return { task, attempt, diagnosis };
  }

  it('authorizes a different offering with immutable evidence before the exact next Attempt', async () => {
    const { task, attempt, diagnosis } = await prepareAlternativeDiagnosis();
    const decision = recoverWithAlternative(persistence, {
      id: asIdentifier<'AlternativeRecoveryDecision'>('recovery-1'), diagnosisId: diagnosis.id,
      requestedDisposition: 'alternative_offering_recommended', actor: 'phase1m-test', decidedAt: NOW,
      eventId: event(task.id, 'alternative-recovery.decided').id,
      evidenceId: asIdentifier<'ChangedConditionEvidence'>('recovery-evidence-1'),
      evidenceEventId: event(task.id, 'failure.changed-condition-recorded').id,
      providerRequest: { id: asIdentifier<'ResolutionDecision'>('recovery-resolution-1'),
        capabilityId: asIdentifier<'Capability'>('text.generate'), contractVersion: 1, privacyClass: 'internal',
        requiredPermissions: [], requiredFeatures: ['text'], requiredFormats: ['text/plain'],
        inputSchemaReference: 'input:1', outputSchemaReference: 'output:1', maximumSideEffectClass: 'none',
        minimumQualificationLevel: 1, minimumQualityLevel: 1, maximumLatencyMs: 100, maximumCost: 0,
        maximumHealthAgeMs: 60_000, requestedAt: NOW },
    });
    expect(decision).toMatchObject({ disposition: 'authorized', failedOfferingId: 'offering-old',
      selectedOfferingId: 'offering-new', nextAttemptNumber: 2 });
    expect(persistence.getTask(task.id)?.status).toBe('ready');
    expect(persistence.getChangedConditionEvidence(diagnosis.id)).toHaveLength(1);
    expect(persistence.getAttempts(task.id)).toHaveLength(1);

    const successful = new DeterministicTestProvider();
    Object.defineProperty(successful, 'providerId', { value: 'offering-new' });
    await new MinimalOrchestrator(persistence, successful, new DeterministicVerifier(), {
      now: () => NOW, nextId: (kind) => `${kind}-recovered-${++sequence}`,
      resolveOffering: () => asIdentifier<'ProviderOffering'>('offering-old'),
      resolveExecutionProvider: (offeringId) => {
        expect(offeringId).toBe('offering-new');
        return successful;
      },
    }).run(task.graphRevisionId);
    expect(persistence.getAttempts(task.id).map(({ attemptNumber, providerOfferingId }) =>
      ({ attemptNumber, providerOfferingId }))).toEqual([
      { attemptNumber: 1, providerOfferingId: 'offering-old' },
      { attemptNumber: 2, providerOfferingId: 'offering-new' },
    ]);
    expect(persistence.getTask(task.id)?.status).toBe('succeeded');
    expect(persistence.getVerifications(task.id).at(-1)?.verdict).toBe('passed');
    expect(attempt.status).toBe('failed');
  });

  it('records no-candidate decisions idempotently without changing Task or Attempt history', async () => {
    const { task, diagnosis } = await prepareAlternativeDiagnosis();
    const command = { id: asIdentifier<'AlternativeRecoveryDecision'>('recovery-none'), diagnosisId: diagnosis.id,
      requestedDisposition: 'alternative_offering_recommended' as const, actor: 'phase1m-test', decidedAt: NOW,
      eventId: event(task.id, 'alternative-recovery.decided').id,
      evidenceId: asIdentifier<'ChangedConditionEvidence'>('unused-evidence'),
      evidenceEventId: event(task.id, 'unused-evidence-event').id,
      providerRequest: { id: asIdentifier<'ResolutionDecision'>('resolution-none'),
        capabilityId: asIdentifier<'Capability'>('text.generate'), contractVersion: 1, privacyClass: 'internal' as const,
        requiredPermissions: [], requiredFeatures: ['missing-feature'], minimumQualificationLevel: 1,
        maximumHealthAgeMs: 60_000, requestedAt: NOW } };
    const first = recoverWithAlternative(persistence, command);
    expect(first.disposition).toBe('no_candidate');
    expect(recoverWithAlternative(persistence, { ...command,
      eventId: asIdentifier<'Event'>('ignored-repeat-event') })).toEqual(first);
    expect(persistence.getTask(task.id)?.status).toBe('failed');
    expect(persistence.getAttempts(task.id)).toHaveLength(1);
  });

  it('reconstructs schema-10 recovery history and rejects direct mutation', async () => {
    const { task, diagnosis } = await prepareAlternativeDiagnosis();
    const decision = recoverWithAlternative(persistence, { id: asIdentifier<'AlternativeRecoveryDecision'>('recovery-reopen'),
      diagnosisId: diagnosis.id, requestedDisposition: 'alternative_offering_recommended', actor: 'phase1m-test', decidedAt: NOW,
      eventId: event(task.id, 'alternative-recovery.decided').id,
      evidenceId: asIdentifier<'ChangedConditionEvidence'>('reopen-evidence'),
      evidenceEventId: event(task.id, 'failure.changed-condition-recorded').id,
      providerRequest: { id: asIdentifier<'ResolutionDecision'>('reopen-resolution'),
        capabilityId: asIdentifier<'Capability'>('text.generate'), contractVersion: 1, privacyClass: 'internal',
        requiredPermissions: [], requiredFeatures: ['text'], minimumQualificationLevel: 1,
        maximumHealthAgeMs: 60_000, requestedAt: NOW } });
    const path = join(directory, 'recovery.sqlite');
    persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath: path });
    persistence.initialize();
    expect(persistence.getSchemaVersion()).toBe(16);
    expect(persistence.getAlternativeRecoveryDecision(diagnosis.id)).toEqual(decision);
  });

  it('persists a genuinely different deterministic Node binding and uses a normal atomic lease and Attempt', async () => {
    const { task, diagnosis } = await prepareNodeDiagnosis();
    const decision = recoverWithAlternative(persistence, nodeRecoveryCommand(diagnosis.id, task.id, 'node-success'));
    expect(decision).toMatchObject({ disposition: 'authorized', failedNodeId: 'node-a', failedLocationId: 'location-a',
      selectedNodeId: 'node-c', selectedLocationId: 'location-c', selectedOfferingId: 'offering-old' });
    expect(persistence.getResourceLeases()).toHaveLength(1);
    const provider = new DeterministicTestProvider();
    Object.defineProperty(provider, 'providerId', { value: 'offering-old' });
    await new MinimalOrchestrator(persistence, provider, new DeterministicVerifier(), {
      now: () => NOW, nextId: (kind) => `${kind}-node-recovery-${++sequence}`,
      resolveOffering: () => asIdentifier<'ProviderOffering'>('offering-old'),
      acquireResource: (value, _offering, recovery) => {
        expect(recovery).toEqual(decision);
        return resourceBinding(value, 'offering-old', 'c', 'recovered-c');
      },
      resolveExecutionProvider: () => provider,
    }).run(task.graphRevisionId);
    const attempts = persistence.getAttempts(task.id);
    expect(attempts[1]).toMatchObject({ attemptNumber: 2, providerOfferingId: 'offering-old', computeNodeId: 'node-c' });
    const recoveredLease = persistence.getResourceLeases().find((lease) => lease.nodeId === 'node-c');
    expect(recoveredLease).toMatchObject({ status: 'released', locationId: 'location-c' });
    const scheduling = persistence.getResourceSchedulingDecision(recoveredLease!.decisionId);
    expect(scheduling).toMatchObject({ selectedNodeId: 'node-c', selectedLocationId: 'location-c' });
    expect(persistence.getTask(task.id)?.status).toBe('succeeded');
  });

  it('records no Node candidate without Task transition, lease, or Attempt', async () => {
    const { task, diagnosis } = await prepareNodeDiagnosis();
    for (const node of persistence.getNodes().filter((value) => value.id !== 'node-a')) {
      persistence.transitionNodeAdministrativeState(node.id, node.version, 'active', 'disabled', 'phase1m-test',
        'remove alternatives', NOW, event(node.id, 'node.administration.changed'));
    }
    const beforeLeases = persistence.getResourceLeases().length;
    const decision = recoverWithAlternative(persistence, nodeRecoveryCommand(diagnosis.id, task.id, 'node-none'));
    expect(decision).toMatchObject({ disposition: 'no_candidate', reason: 'no_eligible_alternative' });
    expect(persistence.getTask(task.id)?.status).toBe('failed');
    expect(persistence.getAttempts(task.id)).toHaveLength(1);
    expect(persistence.getResourceLeases()).toHaveLength(beforeLeases);
  });

  it('rejects stale or superseded diagnosis authority without unsafe partial recovery state', async () => {
    const { task, diagnosis, attempt } = await prepareAlternativeDiagnosis();
    const newerFailure: Failure = { id: asIdentifier<'Failure'>('newer-authoritative-failure'), taskId: task.id,
      attemptId: attempt.id, category: 'execution_defect', classification: 'permanent', code: 'NEWER_FAILURE',
      summary: 'A newer durable failure supersedes the diagnosis', details: {}, retryable: false, createdAt: NOW };
    persistence.createFailure(newerFailure, event(task.id, 'failure.recorded'));
    diagnosePersistedFailure(persistence, { failureId: newerFailure.id, eventId: event(task.id, 'failure.diagnosed').id,
      diagnosedAt: NOW, diagnosedBy: 'phase1m-test' });
    const beforeEvents = persistence.getEvents().length;
    const command = { id: asIdentifier<'AlternativeRecoveryDecision'>('recovery-stale'), diagnosisId: diagnosis.id,
      requestedDisposition: 'alternative_offering_recommended' as const, actor: 'phase1m-test', decidedAt: NOW,
      eventId: event(task.id, 'alternative-recovery.decided').id,
      evidenceId: asIdentifier<'ChangedConditionEvidence'>('stale-evidence'),
      evidenceEventId: event(task.id, 'failure.changed-condition-recorded').id,
      providerRequest: { id: asIdentifier<'ResolutionDecision'>('stale-resolution'),
        capabilityId: asIdentifier<'Capability'>('text.generate'), contractVersion: 1, privacyClass: 'internal' as const,
        requiredPermissions: [], requiredFeatures: ['text'], minimumQualificationLevel: 1,
        maximumHealthAgeMs: 60_000, requestedAt: NOW } };
    const decision = recoverWithAlternative(persistence, command);
    expect(decision).toMatchObject({ disposition: 'rejected', reason: 'latest_failure_or_attempt_mismatch' });
    expect(persistence.getTask(task.id)?.status).toBe('failed');
    expect(persistence.getChangedConditionEvidence(diagnosis.id)).toEqual([]);
    expect(persistence.getEvents().length).toBe(beforeEvents + 1);
  });

  it('prohibits indeterminate outcomes and non-authorized dispositions', async () => {
    const { task, attempt } = await prepareAlternativeDiagnosis();
    const failure: Failure = { id: asIdentifier<'Failure'>('indeterminate-recovery-failure'), taskId: task.id,
      attemptId: attempt.id, category: 'external_outcome_indeterminate', classification: 'external_outcome_indeterminate',
      code: 'OUTCOME_UNKNOWN', summary: 'External outcome is unknown', details: {}, retryable: false, createdAt: NOW };
    persistence.createFailure(failure, event(task.id, 'failure.recorded'));
    const diagnosisEvent = event(task.id, 'failure.diagnosed');
    const diagnosis = createFailureDiagnosis({ evidence: { task: persistence.getTask(task.id)!, failure,
      attempts: [attempt], attempt: { ...attempt, status: 'indeterminate' } }, eventId: diagnosisEvent.id,
      diagnosedAt: NOW, diagnosedBy: 'phase1m-test' });
    persistence.recordFailureDiagnosis(diagnosis, diagnosisEvent);
    const command = nodeRecoveryCommand(diagnosis.id, task.id, 'indeterminate');
    const decision = recoverWithAlternative(persistence, command);
    expect(diagnosis).toMatchObject({ outcomeCertainty: 'indeterminate_external_outcome',
      disposition: 'reconciliation_required' });
    expect(decision).toMatchObject({ disposition: 'rejected', reason: 'diagnosis_not_authoritative' });
    expect(persistence.getAttempts(task.id)).toHaveLength(1);
  });

  it('enforces pending approval and exhausted total Attempt limits', async () => {
    const approvalCase = await prepareAlternativeDiagnosis();
    persistence.createApproval({ id: asIdentifier<'Approval'>('pending-recovery-approval'), goalId: approvalCase.task.goalId,
      taskId: approvalCase.task.id, attemptId: approvalCase.attempt.id, action: 'alternative_recovery', scope: {},
      actionDigest: 'a'.repeat(64), decision: 'requested', requestedAt: NOW }, event(approvalCase.task.id, 'approval.requested'));
    const approvalDecision = recoverWithAlternative(persistence, {
      ...nodeRecoveryCommand(approvalCase.diagnosis.id, approvalCase.task.id, 'approval'),
      requestedDisposition: 'alternative_offering_recommended', resourceRequest: undefined,
      providerRequest: { id: asIdentifier<'ResolutionDecision'>('approval-resolution'),
        capabilityId: asIdentifier<'Capability'>('text.generate'), contractVersion: 1, privacyClass: 'internal',
        requiredPermissions: [], requiredFeatures: ['text'], minimumQualificationLevel: 1,
        maximumHealthAgeMs: 60_000, requestedAt: NOW },
    });
    expect(approvalDecision).toMatchObject({ disposition: 'rejected', reason: 'approval_required' });
    expect(persistence.getTask(approvalCase.task.id)?.status).toBe('failed');

    persistence.close(); rmSync(directory, { recursive: true, force: true });
    directory = mkdtempSync(join(tmpdir(), 'graci-phase1m-limit-'));
    persistence = new SqliteArchitecture2Persistence({ databasePath: join(directory, 'recovery.sqlite') });
    persistence.initialize(); sequence = 0;
    const limitCase = await prepareNodeDiagnosis({ maxAttempts: 1 });
    const limitDecision = recoverWithAlternative(persistence,
      nodeRecoveryCommand(limitCase.diagnosis.id, limitCase.task.id, 'limit'));
    expect(limitDecision).toMatchObject({ disposition: 'rejected', reason: 'attempt_limit_exhausted' });
    expect(persistence.getAttempts(limitCase.task.id)).toHaveLength(1);
  });

  it('orders changed-condition evidence before attempt.started in the durable Event sequence', async () => {
    const { task, diagnosis } = await prepareAlternativeDiagnosis();
    const decision = recoverWithAlternative(persistence, { id: asIdentifier<'AlternativeRecoveryDecision'>('recovery-order'),
      diagnosisId: diagnosis.id, requestedDisposition: 'alternative_offering_recommended', actor: 'phase1m-test', decidedAt: NOW,
      eventId: event(task.id, 'alternative-recovery.decided').id,
      evidenceId: asIdentifier<'ChangedConditionEvidence'>('order-evidence'),
      evidenceEventId: event(task.id, 'failure.changed-condition-recorded').id,
      providerRequest: { id: asIdentifier<'ResolutionDecision'>('order-resolution'),
        capabilityId: asIdentifier<'Capability'>('text.generate'), contractVersion: 1, privacyClass: 'internal',
        requiredPermissions: [], requiredFeatures: ['text'], minimumQualificationLevel: 1,
        maximumHealthAgeMs: 60_000, requestedAt: NOW } });
    const provider = new DeterministicTestProvider();
    Object.defineProperty(provider, 'providerId', { value: 'offering-new' });
    await new MinimalOrchestrator(persistence, provider, new DeterministicVerifier(), {
      now: () => NOW, nextId: (kind) => `${kind}-order-${++sequence}`,
      resolveOffering: () => asIdentifier<'ProviderOffering'>('offering-old'), resolveExecutionProvider: () => provider,
    }).run(task.graphRevisionId);
    const events = persistence.getEvents();
    const evidenceEvent = events.find((value) => value.eventType === 'failure.changed-condition-recorded' &&
      value.payload.evidenceId === decision.changedConditionEvidenceId)!;
    const secondAttemptEvent = events.find((value) => value.eventType === 'attempt.started' && value.payload.attemptNumber === 2)!;
    expect(evidenceEvent.sequence).toBeLessThan(secondAttemptEvent.sequence);
  });

  it('routes a failed recovery Attempt through normal Failure and latest Phase 1L diagnosis', async () => {
    const { task, diagnosis } = await prepareAlternativeDiagnosis();
    recoverWithAlternative(persistence, { id: asIdentifier<'AlternativeRecoveryDecision'>('recovery-fails'),
      diagnosisId: diagnosis.id, requestedDisposition: 'alternative_offering_recommended', actor: 'phase1m-test', decidedAt: NOW,
      eventId: event(task.id, 'alternative-recovery.decided').id,
      evidenceId: asIdentifier<'ChangedConditionEvidence'>('failed-recovery-evidence'),
      evidenceEventId: event(task.id, 'failure.changed-condition-recorded').id,
      providerRequest: { id: asIdentifier<'ResolutionDecision'>('failed-recovery-resolution'),
        capabilityId: asIdentifier<'Capability'>('text.generate'), contractVersion: 1, privacyClass: 'internal',
        requiredPermissions: [], requiredFeatures: ['text'], minimumQualificationLevel: 1,
        maximumHealthAgeMs: 60_000, requestedAt: NOW } });
    const provider = new DeterministicTestProvider(new Map([[task.id,
      { outcome: 'failure', classification: 'permanent', code: 'RECOVERY_FAILED' }]]));
    Object.defineProperty(provider, 'providerId', { value: 'offering-new' });
    await new MinimalOrchestrator(persistence, provider, new DeterministicVerifier(), {
      now: () => NOW, nextId: (kind) => `${kind}-failed-recovery-${++sequence}`,
      resolveOffering: () => asIdentifier<'ProviderOffering'>('offering-old'), resolveExecutionProvider: () => provider,
    }).run(task.graphRevisionId);
    const failures = persistence.getFailures(task.id);
    const diagnoses = persistence.getFailureDiagnoses(task.id);
    const recoveryFailure = failures.find((value) => value.attemptId === persistence.getAttempts(task.id)[1]!.id)!;
    const recoveryDiagnosis = diagnoses.find((value) => value.failureId === recoveryFailure.id)!;
    expect(recoveryFailure).toMatchObject({ code: 'RECOVERY_FAILED' });
    expect(recoveryDiagnosis).toMatchObject({ outcomeCertainty: 'proven_unsuccessful' });
  });

  it('isolates recovered failure from concurrently admitted unrelated work', async () => {
    const { task, diagnosis } = await prepareAlternativeDiagnosis();
    const unrelated: Task = { ...task, id: asIdentifier<'Task'>('phase1m-unrelated-task'), title: 'Unrelated',
      objective: 'Complete independently', status: 'planned', version: 1 };
    persistence.createTask(unrelated, event(unrelated.id, 'task.created'));
    recoverWithAlternative(persistence, { id: asIdentifier<'AlternativeRecoveryDecision'>('recovery-isolation'),
      diagnosisId: diagnosis.id, requestedDisposition: 'alternative_offering_recommended', actor: 'phase1m-test', decidedAt: NOW,
      eventId: event(task.id, 'alternative-recovery.decided').id,
      evidenceId: asIdentifier<'ChangedConditionEvidence'>('isolation-evidence'),
      evidenceEventId: event(task.id, 'failure.changed-condition-recorded').id,
      providerRequest: { id: asIdentifier<'ResolutionDecision'>('isolation-resolution'),
        capabilityId: asIdentifier<'Capability'>('text.generate'), contractVersion: 1, privacyClass: 'internal',
        requiredPermissions: [], requiredFeatures: ['text'], minimumQualificationLevel: 1,
        maximumHealthAgeMs: 60_000, requestedAt: NOW } });
    const recoveredProvider = new DeterministicTestProvider(new Map([[task.id,
      { outcome: 'failure', classification: 'permanent', code: 'ISOLATED_FAILURE' }]]));
    Object.defineProperty(recoveredProvider, 'providerId', { value: 'offering-new' });
    const unrelatedProvider = new DeterministicTestProvider();
    Object.defineProperty(unrelatedProvider, 'providerId', { value: 'offering-old' });
    await new MinimalOrchestrator(persistence, unrelatedProvider, new DeterministicVerifier(), {
      now: () => NOW, nextId: (kind) => `${kind}-isolation-${++sequence}`, maxConcurrentTasks: 2,
      resolveOffering: (value) => asIdentifier<'ProviderOffering'>(value.id === task.id ? 'offering-new' : 'offering-old'),
      resolveExecutionProvider: (offering) => offering === 'offering-new' ? recoveredProvider : unrelatedProvider,
    }).run(task.graphRevisionId);
    expect(persistence.getTask(task.id)?.status).toBe('failed');
    expect(persistence.getTask(unrelated.id)?.status).toBe('succeeded');
    expect(unrelatedProvider.getExecutionCount(unrelated.id)).toBe(1);
  });

  it('rolls back authorized recovery, evidence, and Task transition when the atomic decision write fails', async () => {
    const { task, diagnosis } = await prepareAlternativeDiagnosis();
    const duplicate = event(task.id, 'preexisting.event');
    persistence.appendEvent(duplicate);
    expect(() => recoverWithAlternative(persistence, {
      id: asIdentifier<'AlternativeRecoveryDecision'>('recovery-rollback'), diagnosisId: diagnosis.id,
      requestedDisposition: 'alternative_offering_recommended', actor: 'phase1m-test', decidedAt: NOW,
      eventId: duplicate.id, evidenceId: asIdentifier<'ChangedConditionEvidence'>('rollback-evidence'),
      evidenceEventId: event(task.id, 'failure.changed-condition-recorded').id,
      providerRequest: { id: asIdentifier<'ResolutionDecision'>('rollback-resolution'),
        capabilityId: asIdentifier<'Capability'>('text.generate'), contractVersion: 1, privacyClass: 'internal',
        requiredPermissions: [], requiredFeatures: ['text'], minimumQualificationLevel: 1,
        maximumHealthAgeMs: 60_000, requestedAt: NOW },
    })).toThrow();
    expect(persistence.getTask(task.id)?.status).toBe('failed');
    expect(persistence.getAlternativeRecoveryDecision(diagnosis.id)).toBeUndefined();
    expect(persistence.getChangedConditionEvidence(diagnosis.id)).toEqual([]);
    expect(persistence.getAttempts(task.id)).toHaveLength(1);
  });
});

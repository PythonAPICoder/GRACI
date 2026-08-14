import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { DatabaseSync } from 'node:sqlite';
import { asIdentifier, type Attempt, type AuditEventInput, type Failure, type Goal, type Task,
  type TaskGraphRevision } from '../src/architecture2/domain/index.js';
import { SqliteArchitecture2Persistence } from '../src/architecture2/persistence/index.js';
import { RESEARCH_PROVIDER_CONTRACT_VERSION, type ResearchProvider } from '../src/architecture2/providers/index.js';
import { createFailureDiagnosis, createResearchRequest, executeResearchRequest, TaskStateMachine }
  from '../src/architecture2/workflow/index.js';

const NOW = '2026-08-14T23:55:00.000Z';
const LATER = '2026-08-14T23:55:01.000Z';
const capabilityId = asIdentifier<'Capability'>('research.execute');
const providerId = asIdentifier<'Provider'>('research-provider');
const offeringId = asIdentifier<'ProviderOffering'>('research-offering');

describe('Architecture 2 Phase 1T governed research provider execution', () => {
  let directory: string;
  let path: string;
  let persistence: SqliteArchitecture2Persistence;
  let sequence: number;

  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'graci-phase1t-'));
    path = join(directory, 'research-provider.sqlite');
    persistence = new SqliteArchitecture2Persistence({ databasePath: path });
    persistence.initialize();
    sequence = 0;
  });
  afterEach(() => { persistence.close(); rmSync(directory, { recursive: true, force: true }); });

  const eventId = () => asIdentifier<'Event'>(`phase1t-event-${++sequence}`);
  const event = (aggregateId: string, eventType: string): AuditEventInput => ({ id: eventId(), aggregateType: 'test',
    aggregateId, eventType, eventVersion: 1, actor: 'phase1t-test', occurredAt: NOW, payload: {} });

  function seedRequest() {
    const goal: Goal = { id: asIdentifier<'Goal'>('phase1t-goal'), objective: 'Research a defect', constraints: {},
      priority: 'normal', privacyClass: 'internal', status: 'active', version: 1, createdAt: NOW, updatedAt: NOW };
    persistence.createGoal({ goal, criteria: [] }, event(goal.id, 'goal.created'));
    const graph: TaskGraphRevision = { id: asIdentifier<'TaskGraphRevision'>('phase1t-graph'), goalId: goal.id,
      revision: 1, createdAt: NOW };
    persistence.createTaskGraphRevision(graph, event(graph.id, 'graph.created'));
    const task: Task = { id: asIdentifier<'Task'>('phase1t-task'), goalId: goal.id, graphRevisionId: graph.id,
      title: 'Research', objective: 'Resolve failure', inputs: {}, requiredCapabilities: ['test.execute'],
      privacyClass: 'internal', priority: 'normal', status: 'planned', required: true, retryPolicy: { maxAttempts: 3 },
      verificationPlan: {}, version: 1, createdAt: NOW, updatedAt: NOW };
    persistence.createTask(task, event(task.id, 'task.created'));
    persistence.updateGoal({ ...goal, activeGraphRevisionId: graph.id, version: 2 }, 1, event(goal.id, 'goal.active'));
    const machine = new TaskStateMachine();
    const ready = machine.prepare(task, 'ready', NOW, { dependenciesSatisfied: true });
    persistence.updateTask(ready, 1, event(task.id, 'task.ready'));
    const scheduled = machine.prepare(ready, 'scheduled', NOW);
    persistence.updateTask(scheduled, 2, event(task.id, 'task.scheduled'));
    const attempt: Attempt = { id: asIdentifier<'Attempt'>('phase1t-attempt'), taskId: task.id, attemptNumber: 1,
      status: 'running', inputSnapshot: { objective: task.objective, inputs: {}, requiredCapabilities: task.requiredCapabilities },
      createdAt: NOW, startedAt: NOW };
    const running = machine.prepare(scheduled, 'running', NOW, { attempt });
    persistence.startAttempt(running, 3, attempt, [event(task.id, 'attempt.started')]);
    const terminalAttempt: Attempt = { ...attempt, status: 'failed', completedAt: NOW };
    const failure: Failure = { id: asIdentifier<'Failure'>('phase1t-failure'), taskId: task.id, attemptId: attempt.id,
      category: 'unknown', classification: 'permanent', code: 'UNEXPLAINED_FAILURE', summary: 'Research required',
      details: {}, retryable: false, createdAt: NOW };
    const failed = machine.prepare(running, 'failed', NOW, { attempt: terminalAttempt, terminalReason: failure.code });
    const diagnosisEvent = event(task.id, 'failure.diagnosed');
    const diagnosis = createFailureDiagnosis({ evidence: { task: failed, failure, attempts: [terminalAttempt],
      attempt: terminalAttempt }, eventId: diagnosisEvent.id, diagnosedAt: NOW, diagnosedBy: 'phase1t-test' });
    persistence.recordAttemptOutcome(failed, 4, terminalAttempt, failure,
      [event(task.id, 'failure.recorded'), diagnosisEvent, event(task.id, 'task.failed')], diagnosis);
    return createResearchRequest(persistence, { id: asIdentifier<'ResearchRequest'>('phase1t-request'),
      diagnosisId: diagnosis.id, question: 'What fact resolves this failure?', purpose: 'Bounded technical research',
      requestedBy: 'phase1t-test', requestedAt: NOW, eventId: eventId() });
  }

  function registerProvider(qualified = true) {
    persistence.registerProvider({ provider: { id: providerId, adapterType: 'test-research', adapterVersion: '1',
      configurationReference: 'test:research', createdAt: NOW }, capabilities: [{ id: capabilityId, contractVersion: 1,
      description: 'Bounded research', inputSchemaReference: 'research:request:1',
      outputSchemaReference: 'research:evidence:1', createdAt: NOW }], offerings: [{ id: offeringId, providerId,
      capabilityId, contractVersion: 1, privacyDestinations: ['internal'], permissions: [], features: ['research'],
      supportedFormats: ['application/json'], inputSchemaReference: 'research:request:1',
      outputSchemaReference: 'research:evidence:1', qualificationFingerprint: 'research-v1', qualityLevel: 2,
      expectedLatencyMs: 100, maximumCost: 0, sideEffectClass: 'none', createdAt: NOW }] },
    [event(providerId, 'provider.registered')]);
    if (qualified) persistence.recordQualification({ id: asIdentifier<'Qualification'>('research-qualification'),
      offeringId, status: 'qualified', level: 2, evidence: {}, qualifiedAt: NOW,
      triggerFingerprint: 'research-v1' }, event(offeringId, 'offering.qualified'));
    persistence.recordProviderHealth({ id: asIdentifier<'HealthObservation'>('research-health'), offeringId,
      status: 'healthy', evidence: {}, observedAt: NOW }, event(offeringId, 'offering.health-observed'));
  }

  function provider(result: Awaited<ReturnType<ResearchProvider['research']>>): ResearchProvider {
    return { contractVersion: RESEARCH_PROVIDER_CONTRACT_VERSION, providerId, offeringId, research: async () => result };
  }

  function command(requestId: ReturnType<typeof seedRequest>['id']) {
    return { executionId: asIdentifier<'ResearchProviderExecution'>('phase1t-execution'), requestId,
      resolutionRequest: { id: asIdentifier<'ResolutionDecision'>('phase1t-resolution'), capabilityId,
        contractVersion: 1, privacyClass: 'internal' as const, requiredPermissions: [], requiredFeatures: ['research'],
        requiredFormats: ['application/json'], inputSchemaReference: 'research:request:1',
        outputSchemaReference: 'research:evidence:1', maximumSideEffectClass: 'none' as const,
        minimumQualificationLevel: 1, maximumHealthAgeMs: 60_000, requestedAt: NOW },
      evidenceId: asIdentifier<'ResearchEvidence'>('phase1t-evidence'), startedAt: NOW,
      deadline: '2026-08-14T23:56:00.000Z', completedAt: LATER, actor: 'phase1t-test',
      resolutionEventId: eventId(), startEventId: eventId(), evidenceEventId: eventId(), completionEventId: eventId() };
  }

  it('executes through an eligible exact offering and records unaccepted provenance across restart', async () => {
    const request = seedRequest(); registerProvider(); const before = persistence.getTask(request.taskId);
    await executeResearchRequest(persistence, command(request.id), { resolveProvider: () => provider({ status: 'success',
      value: { suppliedAt: LATER, source: 'provider-research', reference: 'result-1', content: { finding: 'fact' },
        integrity: { digest: 'abc' } } }) });
    const inspection = persistence.inspectResearchRequest(request.id);
    expect(inspection).toMatchObject({ lifecycle: 'evidence_recorded', evidence: [{ evidence: {
      supplierId: providerId, supplierType: 'research_provider', source: 'provider-research', reference: 'result-1' } }] });
    expect(persistence.getAcceptedResearchEvidence(request.id)).toEqual([]);
    expect(persistence.getTask(request.taskId)).toEqual(before);
    persistence.close(); persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    expect(persistence.getResearchProviderExecutions(request.id)).toMatchObject([{ status: 'succeeded', providerId,
      offeringId, resolutionDecisionId: 'phase1t-resolution', evidenceId: 'phase1t-evidence' }]);
  });

  it('rejects an unqualified offering before provider invocation', async () => {
    const request = seedRequest(); registerProvider(false); let calls = 0;
    await expect(executeResearchRequest(persistence, command(request.id), { resolveProvider: () => ({ ...provider({
      status: 'non_retryable_failure', failure: { code: 'NO', summary: 'not called' } }), research: async () => {
        calls += 1; return { status: 'non_retryable_failure' as const, failure: { code: 'NO', summary: 'not called' } };
      } }) })).rejects.toThrow(/No eligible/);
    expect(calls).toBe(0);
    expect(persistence.getResearchProviderExecutions(request.id)).toEqual([]);
  });

  it('respects an open offering circuit before provider invocation', async () => {
    const request = seedRequest(); registerProvider();
    persistence.close();
    const database = new DatabaseSync(path);
    database.prepare(`INSERT INTO circuits (id,target_type,target_id,state,policy_id,policy_version,
      observation_window_ms,failure_threshold,cooldown_ms,qualifying_categories_json,opened_at,cooldown_until,version,updated_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)`).run('phase1t-circuit', 'provider_offering', offeringId, 'open',
      'phase1o.default', 1, 300000, 3, 60000, '["execution_defect"]', NOW, '2026-08-15T00:00:00.000Z', 1, NOW);
    database.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    let calls = 0;
    await expect(executeResearchRequest(persistence, command(request.id), { resolveProvider: () => ({ ...provider({
      status: 'non_retryable_failure', failure: { code: 'NO', summary: 'not called' } }), research: async () => {
        calls += 1; return { status: 'non_retryable_failure' as const, failure: { code: 'NO', summary: 'not called' } };
      } }) })).rejects.toThrow(/No eligible/);
    expect(calls).toBe(0);
    expect(persistence.getProviderResolution(asIdentifier<'ResolutionDecision'>('phase1t-resolution'))
      ?.candidates[0]?.rejectionReasons).toContain('circuit_open');
  });

  it('durably records known provider failure without recovery or evidence', async () => {
    const request = seedRequest(); registerProvider(); const before = persistence.getTask(request.taskId);
    const result = await executeResearchRequest(persistence, command(request.id), { resolveProvider: () => provider({
      status: 'retryable_failure', failure: { code: 'TEMPORARY', summary: 'Unavailable' } }) });
    expect(result).toMatchObject({ status: 'failed', failureCategory: 'transient_infrastructure',
      failureClassification: 'transient', failureCode: 'TEMPORARY' });
    expect(persistence.inspectResearchRequest(request.id)?.lifecycle).toBe('requested');
    expect(persistence.getTask(request.taskId)).toEqual(before);
  });

  it('stops safely on indeterminate outcome and permits no duplicate execution', async () => {
    const request = seedRequest(); registerProvider(); const first = command(request.id);
    const result = await executeResearchRequest(persistence, first, { resolveProvider: () => provider({
      status: 'indeterminate_outcome', failure: { code: 'UNKNOWN', summary: 'Outcome uncertain' } }) });
    expect(result).toMatchObject({ status: 'indeterminate', failureCategory: 'external_outcome_indeterminate' });
    expect(persistence.inspectResearchRequest(request.id)?.evidence).toEqual([]);
    await expect(executeResearchRequest(persistence, { ...command(request.id), resolutionRequest: {
      ...first.resolutionRequest, id: asIdentifier<'ResolutionDecision'>('phase1t-resolution-duplicate') },
      executionId: asIdentifier<'ResearchProviderExecution'>('phase1t-execution-duplicate') },
    { resolveProvider: () => provider({ status: 'success', value: { suppliedAt: LATER, source: 'x', reference: 'y', content: {} } }) }))
      .rejects.toThrow(/already has provider execution authority/);
    expect(persistence.getResearchProviderExecutions(request.id)).toHaveLength(1);
  });

  it('fails closed when the Research Request authority is stale', async () => {
    const request = seedRequest(); registerProvider();
    persistence.close();
    const database = new DatabaseSync(path);
    database.prepare(`UPDATE tasks SET status='ready',terminal_reason=NULL,completed_at=NULL,version=version+1 WHERE id=?`)
      .run(request.taskId);
    database.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    await expect(executeResearchRequest(persistence, command(request.id), { resolveProvider: () => provider({ status: 'success',
      value: { suppliedAt: LATER, source: 'x', reference: 'y', content: {} } }) })).rejects.toThrow(/stale, invalid/);
    expect(persistence.getResearchProviderExecutions(request.id)).toEqual([]);
  });

  it('migrates populated schema 16 without fabricating execution history', () => {
    const request = seedRequest(); registerProvider();
    persistence.close();
    const database = new DatabaseSync(path);
    database.exec(`DROP TRIGGER research_provider_executions_no_delete;
      DROP TRIGGER research_provider_executions_terminal_no_update;
      DROP TABLE research_provider_executions;
      DELETE FROM schema_migrations WHERE version=17;
      PRAGMA user_version=16;`);
    database.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    expect(persistence.getSchemaVersion()).toBe(17);
    expect(persistence.getResearchRequest(request.id)).toEqual(request);
    expect(persistence.getResearchProviderExecutions(request.id)).toEqual([]);
  });
});

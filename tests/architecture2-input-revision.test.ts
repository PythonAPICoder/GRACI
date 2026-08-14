import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { DatabaseSync } from 'node:sqlite';
import { createHash } from 'node:crypto';
import { asIdentifier, type Attempt, type AuditEventInput, type Failure, type Goal, type Task,
  type TaskGraphRevision } from '../src/architecture2/domain/index.js';
import { DeterministicTestProvider } from '../src/architecture2/execution/index.js';
import { SqliteArchitecture2Persistence } from '../src/architecture2/persistence/index.js';
import { DeterministicVerifier } from '../src/architecture2/verification/index.js';
import { authorizeInputRevision, createFailureDiagnosis, MinimalOrchestrator,
  TaskStateMachine } from '../src/architecture2/workflow/index.js';

const NOW = '2026-08-14T23:00:00.000Z';

describe('Architecture 2 Phase 1P governed input revision', () => {
  let directory: string;
  let path: string;
  let persistence: SqliteArchitecture2Persistence;
  let sequence: number;

  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'graci-phase1p-'));
    path = join(directory, 'input-revision.sqlite');
    persistence = new SqliteArchitecture2Persistence({ databasePath: path });
    persistence.initialize();
    sequence = 0;
  });
  afterEach(() => { persistence.close(); rmSync(directory, { recursive: true, force: true }); });

  function event(taskId: string, type: string): AuditEventInput {
    return { id: asIdentifier<'Event'>(`phase1p-event-${++sequence}`), aggregateType: 'task', aggregateId: taskId,
      eventType: type, eventVersion: 1, actor: 'phase1p-test', occurredAt: NOW, payload: {} };
  }

  function seed(maxAttempts = 3, category: Failure['category'] = 'invalid_input_or_precondition',
    classification: Failure['classification'] = 'permanent', terminalStatus: Attempt['status'] = 'failed') {
    const goal: Goal = { id: asIdentifier<'Goal'>('phase1p-goal'), objective: 'Revise input', constraints: {},
      priority: 'normal', privacyClass: 'internal', status: 'active', version: 1, createdAt: NOW, updatedAt: NOW };
    persistence.createGoal({ goal, criteria: [] }, event(goal.id, 'goal.created'));
    const graph: TaskGraphRevision = { id: asIdentifier<'TaskGraphRevision'>('phase1p-graph'), goalId: goal.id,
      revision: 1, createdAt: NOW };
    persistence.createTaskGraphRevision(graph, event(graph.id, 'graph.created'));
    const task: Task = { id: asIdentifier<'Task'>('phase1p-task'), goalId: goal.id, graphRevisionId: graph.id,
      title: 'Use input', objective: 'Execute with corrected input', inputs: { query: 'bad', nested: { order: 1 } },
      requiredCapabilities: ['test.execute'], privacyClass: 'internal', priority: 'normal', status: 'planned',
      required: true, retryPolicy: { maxAttempts }, verificationPlan: {}, version: 1, createdAt: NOW, updatedAt: NOW };
    persistence.createTask(task, event(task.id, 'task.created'));
    const machine = new TaskStateMachine();
    const ready = machine.prepare(task, 'ready', NOW, { dependenciesSatisfied: true });
    persistence.updateTask(ready, task.version, event(task.id, 'task.ready'));
    const scheduled = machine.prepare(ready, 'scheduled', NOW);
    persistence.updateTask(scheduled, ready.version, event(task.id, 'task.scheduled'));
    const attempt: Attempt = { id: asIdentifier<'Attempt'>('phase1p-attempt-1'), taskId: task.id, attemptNumber: 1,
      status: 'running', providerOfferingId: 'deterministic-test-provider',
      inputSnapshot: { objective: task.objective, inputs: task.inputs, requiredCapabilities: task.requiredCapabilities },
      idempotencyKey: `${task.id}:1`, startedAt: NOW, createdAt: NOW };
    const running = machine.prepare(scheduled, 'running', NOW, { attempt });
    persistence.startAttempt(running, scheduled.version, attempt, [event(task.id, 'attempt.started')]);
    const failedAttempt: Attempt = { ...attempt, status: terminalStatus, result: { rejected: true }, completedAt: NOW };
    const failure: Failure = { id: asIdentifier<'Failure'>('phase1p-failure-1'), taskId: task.id, attemptId: attempt.id,
      category, classification, code: 'INVALID_QUERY',
      summary: 'Query is invalid', details: {}, retryable: false, createdAt: NOW };
    const failed = machine.prepare(running, 'failed', NOW, { attempt: failedAttempt, terminalReason: failure.code });
    const diagnosisEvent = event(task.id, 'failure.diagnosed');
    const diagnosis = createFailureDiagnosis({ evidence: { task: failed, failure, attempts: [failedAttempt],
      attempt: failedAttempt }, eventId: diagnosisEvent.id, diagnosedAt: NOW, diagnosedBy: 'phase1p-test' });
    persistence.recordAttemptOutcome(failed, running.version, failedAttempt, failure,
      [event(task.id, 'failure.recorded'), diagnosisEvent, event(task.id, 'task.failed')], diagnosis);
    return { task, graph, attempt: failedAttempt, failure, diagnosis };
  }

  function scheduleAuthorized(source: ReturnType<typeof seed>) {
    const current = persistence.getTask(source.task.id)!;
    const machine = new TaskStateMachine();
    const scheduled = machine.prepare(current, 'scheduled', NOW);
    persistence.updateTask(scheduled, current.version, event(current.id, 'task.scheduled'));
    return { machine, scheduled };
  }

  function authorize(diagnosisId: ReturnType<typeof seed>['diagnosis']['id'], revisedInputs = { query: 'good' }) {
    return authorizeInputRevision(persistence, { id: asIdentifier<'InputRevision'>('phase1p-revision-1'), diagnosisId,
      revisedInputs, actor: 'phase1p-test', authorizedAt: NOW,
      eventId: asIdentifier<'Event'>(`phase1p-revision-event-${++sequence}`) });
  }

  it('authorizes and consumes the exact next Attempt using revised inputs while preserving history', async () => {
    const { task, graph, attempt, diagnosis } = seed();
    const revision = authorize(diagnosis.id);
    expect(revision).toMatchObject({ taskId: task.id, failedAttemptId: attempt.id, nextAttemptNumber: 2,
      priorInputs: { query: 'bad', nested: { order: 1 } }, revisedInputs: { query: 'good' } });
    expect(persistence.getTask(task.id)).toMatchObject({ status: 'ready', inputs: { query: 'good' } });
    const provider = new DeterministicTestProvider();
    await new MinimalOrchestrator(persistence, provider, new DeterministicVerifier(), {
      now: () => NOW, nextId: (kind) => `${kind}-phase1p-${++sequence}` }).run(graph.id);
    const attempts = persistence.getAttempts(task.id);
    expect(attempts[0]?.inputSnapshot).toEqual(attempt.inputSnapshot);
    expect(attempts[1]).toMatchObject({ attemptNumber: 2, inputSnapshot: { inputs: { query: 'good' } } });
    expect(persistence.getPendingInputRevision(task.id)).toBeUndefined();
    expect(persistence.getTask(task.id)?.status).toBe('succeeded');
    persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    expect(persistence.getInputRevision(revision.id)).toEqual(revision);
    expect(persistence.getPendingInputRevision(task.id)).toBeUndefined();
    expect(persistence.getAttempts(task.id)).toHaveLength(2);
  });

  it('rejects canonical-identical and malformed revised JSON', () => {
    const source = seed();
    expect(() => authorize(source.diagnosis.id, { nested: { order: 1 }, query: 'bad' })).toThrow(/must change/);
    expect(() => authorize(source.diagnosis.id, { invalid: Number.NaN })).toThrow(/plain JSON/);
    expect(() => authorize(source.diagnosis.id, { invalid: new Date() } as never)).toThrow(/plain JSON/);
    const cyclic: Record<string, unknown> = {}; cyclic.self = cyclic;
    expect(() => authorize(source.diagnosis.id, cyclic)).toThrow(/cyclic/);
  });

  it('rejects other and indeterminate diagnoses and enforces Attempt and approval gates', () => {
    const other = seed(3, 'execution_defect');
    expect(other.diagnosis.disposition).toBe('terminal_failure');
    expect(() => authorize(other.diagnosis.id)).toThrow(/stale|ineligible/);

    persistence.close();
    path = join(directory, 'indeterminate.sqlite');
    persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize(); sequence = 100;
    const indeterminate = seed(3, 'external_outcome_indeterminate', 'external_outcome_indeterminate', 'indeterminate');
    expect(indeterminate.diagnosis.disposition).toBe('reconciliation_required');
    expect(() => authorize(indeterminate.diagnosis.id)).toThrow(/ineligible/);

    persistence.close();
    path = join(directory, 'limit.sqlite');
    persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize(); sequence = 200;
    const exhausted = seed(1);
    expect(() => authorize(exhausted.diagnosis.id)).toThrow(/limit/);

    persistence.close();
    path = join(directory, 'approval.sqlite');
    persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize(); sequence = 300;
    const source = seed();
    persistence.createApproval({ id: asIdentifier<'Approval'>('phase1p-approval'), goalId: source.task.goalId,
      taskId: source.task.id, attemptId: source.attempt.id, action: 'revise_input', scope: {}, actionDigest: 'a'.repeat(64),
      decision: 'requested', requestedAt: NOW }, event(source.task.id, 'approval.requested'));
    expect(() => authorize(source.diagnosis.id)).toThrow(/approval/);
    const current = persistence.getTask(source.task.id)!;
    const priorInputsDigest = createHash('sha256').update('{"nested":{"order":1},"query":"bad"}').digest('hex');
    const revisedInputsDigest = createHash('sha256').update('{"query":"good"}').digest('hex');
    expect(() => persistence.authorizeInputRevision({ id: asIdentifier<'InputRevision'>('direct-race-revision'),
      taskId: current.id, failedAttemptId: source.attempt.id, failureId: source.failure.id,
      diagnosisId: source.diagnosis.id, priorInputs: current.inputs, priorInputsDigest,
      revisedInputs: { query: 'good' }, revisedInputsDigest, nextAttemptNumber: 2, actor: 'phase1p-test',
      authorizedAt: NOW, eventId: asIdentifier<'Event'>('direct-race-event') },
    { ...current, inputs: { query: 'good' }, status: 'ready', terminalReason: undefined, completedAt: undefined,
      version: current.version + 1 }, current.version,
    { id: asIdentifier<'Event'>('direct-race-event'), aggregateType: 'task', aggregateId: current.id,
      eventType: 'input-revision.authorized', eventVersion: 1, actor: 'phase1p-test', occurredAt: NOW,
      payload: {} })).toThrow(/no longer current/);
    expect(persistence.getInputRevisionByDiagnosis(source.diagnosis.id)).toBeUndefined();
  });

  it('changes only inputs and lifecycle metadata and is idempotent while rejecting conflicting identity', () => {
    const source = seed();
    const before = persistence.getTask(source.task.id)!;
    const revision = authorize(source.diagnosis.id);
    const after = persistence.getTask(source.task.id)!;
    expect({ ...after, inputs: before.inputs, status: before.status, terminalReason: before.terminalReason,
      completedAt: before.completedAt, version: before.version, updatedAt: before.updatedAt }).toEqual(before);
    const repeated = authorizeInputRevision(persistence, { id: revision.id, diagnosisId: source.diagnosis.id,
      revisedInputs: { query: 'good' }, actor: 'different-replay-actor', authorizedAt: '2026-08-14T23:00:01.000Z',
      eventId: asIdentifier<'Event'>('unused-replay-event') });
    expect(repeated).toEqual(revision);
    expect(() => authorizeInputRevision(persistence, { id: asIdentifier<'InputRevision'>('conflicting-revision'),
      diagnosisId: source.diagnosis.id, revisedInputs: { query: 'other' }, actor: 'phase1p-test', authorizedAt: NOW,
      eventId: asIdentifier<'Event'>('conflicting-event') })).toThrow(/conflict/);
    const second = new SqliteArchitecture2Persistence({ databasePath: path }); second.initialize();
    expect(authorizeInputRevision(second, { id: revision.id, diagnosisId: source.diagnosis.id,
      revisedInputs: { query: 'good' }, actor: 'second-connection', authorizedAt: NOW,
      eventId: asIdentifier<'Event'>('second-connection-event') })).toEqual(revision);
    second.close();
  });

  it('fails closed when the diagnosed Task is stale or superseded', () => {
    const source = seed();
    const current = persistence.getTask(source.task.id)!;
    persistence.updateTask({ ...current, status: 'superseded', terminalReason: 'new-plan',
      version: current.version + 1, updatedAt: NOW }, current.version, event(current.id, 'task.superseded'));
    expect(() => authorize(source.diagnosis.id)).toThrow(/stale|ineligible/);
    expect(persistence.getInputRevisionByDiagnosis(source.diagnosis.id)).toBeUndefined();
  });

  it('requires exact pending authority, next number, and full immutable Attempt snapshot atomically', () => {
    const source = seed();
    const revision = authorize(source.diagnosis.id);
    const { machine, scheduled } = scheduleAuthorized(source);
    const baseAttempt: Attempt = { id: asIdentifier<'Attempt'>('phase1p-attempt-2'), taskId: source.task.id,
      attemptNumber: 2, status: 'running', providerOfferingId: 'deterministic-test-provider',
      inputSnapshot: { objective: source.task.objective, inputs: { query: 'good' },
        requiredCapabilities: source.task.requiredCapabilities }, startedAt: NOW, createdAt: NOW };
    const running = machine.prepare(scheduled, 'running', NOW, { attempt: baseAttempt });
    expect(() => persistence.startAttempt(running, scheduled.version, { ...baseAttempt, attemptNumber: 3 },
      [event(source.task.id, 'attempt.started')], undefined, undefined, undefined, revision.id)).toThrow(/exactly match/);
    expect(() => persistence.startAttempt(running, scheduled.version, { ...baseAttempt,
      inputSnapshot: { ...baseAttempt.inputSnapshot, objective: 'tampered' } },
      [event(source.task.id, 'attempt.started')], undefined, undefined, undefined, revision.id)).toThrow(/exactly match/);
    expect(() => persistence.startAttempt(running, scheduled.version, baseAttempt,
      [event(source.task.id, 'attempt.started')])).toThrow(/must be consumed/);
    expect(persistence.getAttempts(source.task.id)).toHaveLength(1);
    expect(persistence.getTask(source.task.id)?.status).toBe('scheduled');
    persistence.startAttempt(running, scheduled.version, baseAttempt, [event(source.task.id, 'attempt.started')],
      undefined, undefined, undefined, revision.id);
    expect(persistence.getPendingInputRevision(source.task.id)).toBeUndefined();
    expect(() => persistence.startAttempt(running, scheduled.version, { ...baseAttempt,
      id: asIdentifier<'Attempt'>('phase1p-attempt-reuse') }, [event(source.task.id, 'attempt.started')],
      undefined, undefined, undefined, revision.id)).toThrow(/not pending/);
    expect(persistence.getAttempts(source.task.id)).toHaveLength(2);
  });

  it('does not bypass provider resolution or resource admission controls', async () => {
    const source = seed(); authorize(source.diagnosis.id);
    let resolutions = 0; let resourceChecks = 0;
    const result = await new MinimalOrchestrator(persistence, new DeterministicTestProvider(), new DeterministicVerifier(), {
      now: () => NOW, resolveOffering: () => { resolutions += 1; return asIdentifier<'ProviderOffering'>('controlled-offering'); },
      acquireResource: () => { resourceChecks += 1; return undefined; } }).run(source.graph.id);
    expect({ resolutions, resourceChecks, status: result.status }).toEqual({ resolutions: 1, resourceChecks: 1, status: 'incomplete' });
    expect(persistence.getPendingInputRevision(source.task.id)?.id).toBe('phase1p-revision-1');
    expect(persistence.getAttempts(source.task.id)).toHaveLength(1);
  });

  it('keeps normal Verification authoritative after revised execution', async () => {
    const source = seed(); authorize(source.diagnosis.id);
    const provider = new DeterministicTestProvider(new Map([[source.task.id,
      { outcome: 'success', verificationPasses: false }]]));
    await new MinimalOrchestrator(persistence, provider, new DeterministicVerifier(), {
      now: () => NOW, nextId: (kind) => `${kind}-reject-${++sequence}` }).run(source.graph.id);
    expect(persistence.getTask(source.task.id)?.status).toBe('failed');
    expect(persistence.getVerifications(source.task.id).at(-1)?.verdict).toBe('failed');
    expect(persistence.getAttempts(source.task.id)).toHaveLength(2);
  });

  it('reconstructs immutable authority and migrates populated schema 12 without fabricating revisions', () => {
    const source = seed();
    const revision = authorize(source.diagnosis.id);
    persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath: path });
    persistence.initialize();
    expect(persistence.getSchemaVersion()).toBe(13);
    expect(persistence.getInputRevision(revision.id)).toEqual(revision);

    const oldPath = join(directory, 'schema12.sqlite');
    persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath: oldPath }); persistence.initialize(); sequence = 500;
    const populated = seed();
    persistence.close();
    const database = new DatabaseSync(oldPath);
    database.exec(`DROP TABLE input_revision_consumptions; DROP TABLE input_revisions;
      DROP INDEX idx_failures_input_revision_authority; DROP INDEX idx_diagnoses_input_revision_authority;
      DELETE FROM schema_migrations WHERE version=13; PRAGMA user_version=12;`);
    database.close();
    const migrated = new SqliteArchitecture2Persistence({ databasePath: oldPath });
    migrated.initialize();
    expect(migrated.getSchemaVersion()).toBe(13);
    expect(migrated.getTask(populated.task.id)?.status).toBe('failed');
    expect(migrated.getAttempts(populated.task.id)).toHaveLength(1);
    expect(migrated.getFailure(populated.failure.id)).toEqual(populated.failure);
    expect(migrated.getFailureDiagnosisById(populated.diagnosis.id)).toEqual(populated.diagnosis);
    expect(migrated.getPendingInputRevision(populated.task.id)).toBeUndefined();
    migrated.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
  });
});

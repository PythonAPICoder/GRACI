import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { DatabaseSync } from 'node:sqlite';
import { asIdentifier, type Attempt, type AuditEventInput, type Failure, type Goal, type Task,
  type TaskGraphRevision } from '../src/architecture2/domain/index.js';
import { DeterministicTestProvider } from '../src/architecture2/execution/index.js';
import { SqliteArchitecture2Persistence } from '../src/architecture2/persistence/index.js';
import { migrations } from '../src/architecture2/persistence/sqlite/migrations.js';
import { reconcileExternalOutcome, type ReconciliationCommand,
  type ReconciliationProvider } from '../src/architecture2/reconciliation/index.js';
import { DeterministicVerifier } from '../src/architecture2/verification/index.js';
import { diagnosePersistedFailure, MinimalOrchestrator, recoverWithAlternative,
  TaskStateMachine } from '../src/architecture2/workflow/index.js';

const NOW = '2026-08-14T22:00:00.000Z';

describe('Architecture 2 Phase 1N external outcome reconciliation', () => {
  let directory: string;
  let path: string;
  let persistence: SqliteArchitecture2Persistence;
  let sequence: number;

  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'graci-phase1n-'));
    path = join(directory, 'reconciliation.sqlite');
    persistence = new SqliteArchitecture2Persistence({ databasePath: path });
    persistence.initialize();
    sequence = 0;
  });
  afterEach(() => { persistence.close(); rmSync(directory, { recursive: true, force: true }); });

  function event(taskId: string, type: string): AuditEventInput {
    return { id: asIdentifier<'Event'>(`phase1n-event-${++sequence}`), aggregateType: 'task', aggregateId: taskId,
      eventType: type, eventVersion: 1, actor: 'phase1n-test', occurredAt: NOW, payload: {} };
  }

  function command(diagnosisId: ReconciliationCommand['diagnosisId'], suffix: string): ReconciliationCommand {
    return { id: asIdentifier<'ReconciliationDecision'>(`reconciliation-${suffix}`), diagnosisId,
      actor: 'phase1n-test', decidedAt: NOW, eventId: event('phase1n-task', 'reconciliation.decided').id,
      verificationId: asIdentifier<'Verification'>(`verification-${suffix}`),
      verificationEventId: event('phase1n-task', 'verification.recorded').id,
      transitionEventId: event('phase1n-task', 'task.transitioned').id,
      failureId: asIdentifier<'Failure'>(`failure-${suffix}`),
      failureEventId: event('phase1n-task', 'failure.recorded').id,
      diagnosisEventId: event('phase1n-task', 'failure.diagnosed').id };
  }

  function provider(result: unknown): ReconciliationProvider {
    return { providerId: 'test-reconciler', providerVersion: 1, reconcile: async () => result as never };
  }

  function seedIndeterminate(maxAttempts = 2) {
    const goal: Goal = { id: asIdentifier<'Goal'>('phase1n-goal'), objective: 'Reconcile', constraints: {},
      priority: 'normal', privacyClass: 'internal', status: 'active', version: 1, createdAt: NOW, updatedAt: NOW };
    persistence.createGoal({ goal, criteria: [] }, event(goal.id, 'goal.created'));
    const graph: TaskGraphRevision = { id: asIdentifier<'TaskGraphRevision'>('phase1n-graph'), goalId: goal.id,
      revision: 1, createdAt: NOW };
    persistence.createTaskGraphRevision(graph, event(graph.id, 'graph.created'));
    const task: Task = { id: asIdentifier<'Task'>('phase1n-task'), goalId: goal.id, graphRevisionId: graph.id,
      title: 'External effect', objective: 'Perform one external effect', inputs: {}, requiredCapabilities: ['external.effect'],
      privacyClass: 'internal', priority: 'normal', status: 'planned', required: true, retryPolicy: { maxAttempts },
      verificationPlan: {}, version: 1, createdAt: NOW, updatedAt: NOW };
    persistence.createTask(task, event(task.id, 'task.created'));
    const machine = new TaskStateMachine();
    const ready = machine.prepare(task, 'ready', NOW, { dependenciesSatisfied: true });
    persistence.updateTask(ready, task.version, event(task.id, 'task.ready'));
    const scheduled = machine.prepare(ready, 'scheduled', NOW);
    persistence.updateTask(scheduled, ready.version, event(task.id, 'task.scheduled'));
    const attempt: Attempt = { id: asIdentifier<'Attempt'>('phase1n-attempt-1'), taskId: task.id, attemptNumber: 1,
      status: 'running', providerOfferingId: 'offering-original', inputSnapshot: {}, idempotencyKey: 'external-operation-1',
      startedAt: NOW, createdAt: NOW };
    const running = machine.prepare(scheduled, 'running', NOW, { attempt });
    persistence.startAttempt(running, scheduled.version, attempt, [event(task.id, 'attempt.started')]);
    return { task, graph };
  }

  async function recoverSource(maxAttempts = 2) {
    const seeded = seedIndeterminate(maxAttempts);
    await new MinimalOrchestrator(persistence, new DeterministicTestProvider(), new DeterministicVerifier(),
      { now: () => NOW, nextId: (kind) => `${kind}-recover-${++sequence}` }).run(seeded.graph.id);
    const failure = persistence.getFailures(seeded.task.id).at(-1)!;
    const diagnosis = persistence.getFailureDiagnoses(seeded.task.id).at(-1)!;
    return { ...seeded, failure, diagnosis };
  }

  it('proves completion through the normal verifier without creating another Attempt and reconstructs it after reopen', async () => {
    const { task, diagnosis } = await recoverSource();
    const decision = await reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider({
      conclusion: 'proven_completed', operationId: 'external-operation-1', output: { receipt: 'one' },
      evidence: { verificationPasses: true, receipt: 'one' }, reason: 'authoritative receipt matched',
    }), command(diagnosis.id, 'completed'));
    expect(decision).toMatchObject({ conclusion: 'proven_completed', verificationId: 'verification-completed' });
    expect(persistence.getAttempts(task.id)).toHaveLength(1);
    expect(persistence.getTask(task.id)?.status).toBe('succeeded');
    persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath: path });
    persistence.initialize();
    expect(persistence.getSchemaVersion()).toBe(19);
    expect(persistence.getReconciliationDecision(decision.id)).toEqual(decision);
    expect(persistence.getAttempts(task.id)).toHaveLength(1);
  });

  it('authorizes exactly one next Attempt with the same offering and normal execution/verification', async () => {
    const { task, graph, diagnosis } = await recoverSource();
    const decision = await reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider({
      conclusion: 'proven_not_completed', operationId: 'external-operation-1', evidence: { absent: true },
      reason: 'provider proves no effect occurred',
    }), command(diagnosis.id, 'not-completed'));
    expect(decision.nextAttemptNumber).toBe(2);
    expect(persistence.getTask(task.id)?.status).toBe('ready');
    const execution = new DeterministicTestProvider();
    Object.defineProperty(execution, 'providerId', { value: 'offering-original' });
    await new MinimalOrchestrator(persistence, execution, new DeterministicVerifier(), {
      now: () => NOW, nextId: (kind) => `${kind}-fresh-${++sequence}`,
      resolveOffering: () => asIdentifier<'ProviderOffering'>('offering-other'),
      resolveExecutionProvider: (offering) => { expect(offering).toBe('offering-original'); return execution; },
    }).run(graph.id);
    expect(persistence.getAttempts(task.id).map((value) => [value.attemptNumber, value.providerOfferingId]))
      .toEqual([[1, 'offering-original'], [2, 'offering-original']]);
    expect(persistence.getTask(task.id)?.status).toBe('succeeded');
    await expect(reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider({
      conclusion: 'proven_not_completed', operationId: 'external-operation-1', evidence: { absent: false }, reason: 'conflict',
    }), command(diagnosis.id, 'conflict'))).rejects.toThrow(/already concluded|stale/);
  });

  it('persists proven-not-completed with explicit withheld authority when the Attempt budget is exhausted', async () => {
    const { task, diagnosis } = await recoverSource(1);
    const decision = await reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider({
      conclusion: 'proven_not_completed', operationId: 'external-operation-1', evidence: { absent: true },
      reason: 'effect absent',
    }), command(diagnosis.id, 'budget'));
    expect(decision).toMatchObject({ conclusion: 'proven_not_completed', nextAttemptNumber: undefined,
      reason: 'proven_not_completed; retry_authority_withheld:attempt_limit_exhausted' });
    expect(persistence.getTask(task.id)?.status).toBe('failed');
    expect(persistence.getPendingReconciliation(task.id)).toBeUndefined();
  });

  it('persists proven-not-completed with explicit withheld authority while approval is pending', async () => {
    const { task, diagnosis } = await recoverSource();
    persistence.createApproval({ id: asIdentifier<'Approval'>('phase1n-pending-approval'), goalId: task.goalId,
      taskId: task.id, attemptId: diagnosis.attemptId, action: 'external_effect', scope: {}, actionDigest: 'a'.repeat(64),
      decision: 'requested', requestedAt: NOW }, event(task.id, 'approval.requested'));
    const decision = await reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider({
      conclusion: 'proven_not_completed', operationId: 'external-operation-1', evidence: { absent: true },
      reason: 'effect absent',
    }), command(diagnosis.id, 'approval'));
    expect(decision).toMatchObject({ conclusion: 'proven_not_completed', nextAttemptNumber: undefined,
      reason: 'proven_not_completed; retry_authority_withheld:approval_required' });
    expect(persistence.getTask(task.id)?.status).toBe('failed');
  });

  it('records normal rejecting Verification and trusted terminal diagnosis without retrying the external effect', async () => {
    const { task, diagnosis } = await recoverSource();
    const before = persistence.getAttempts(task.id);
    const decision = await reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider({
      conclusion: 'proven_completed', operationId: 'external-operation-1', output: { receipt: 'bad' },
      evidence: { verificationPasses: false }, reason: 'effect exists',
    }), command(diagnosis.id, 'rejected'));
    const verification = persistence.getVerifications(task.id).at(-1)!;
    const failure = persistence.getFailures(task.id).at(-1)!;
    const rejectionDiagnosis = persistence.getFailureDiagnoses(task.id).at(-1)!;
    expect(decision.verificationId).toBe(verification.id);
    expect(verification).toMatchObject({ verdict: 'failed', attemptId: diagnosis.attemptId,
      evidence: { reconciliationProvenCompleted: true } });
    expect(failure).toMatchObject({ classification: 'verification_failed', retryable: false });
    expect(rejectionDiagnosis).toMatchObject({ failureId: failure.id, outcomeCertainty: 'proven_completed',
      disposition: 'terminal_failure', retryable: false });
    expect(persistence.getAttempts(task.id)).toEqual(before);
    expect(persistence.getTask(task.id)?.status).toBe('failed');
  });

  it('rejects oversized, deeply malformed, cyclic, non-finite, and non-JSON nested evidence', async () => {
    const cases: unknown[] = [
      { huge: 'x'.repeat(70 * 1024) },
      { nested: { invalid: Number.NaN } },
      { nested: { invalid: undefined } },
      { nested: { invalid: 1n } },
      { nested: new Date() },
    ];
    for (const [index, evidence] of cases.entries()) {
      persistence.close(); rmSync(directory, { recursive: true, force: true });
      directory = mkdtempSync(join(tmpdir(), `graci-phase1n-malformed-${index}-`));
      path = join(directory, 'reconciliation.sqlite');
      persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize(); sequence = 0;
      const { diagnosis } = await recoverSource();
      await expect(reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider({
        conclusion: 'remains_indeterminate', operationId: 'external-operation-1', evidence,
        reason: 'invalid evidence',
      }), command(diagnosis.id, `invalid-${index}`))).rejects.toThrow(/bounded|JSON|plain|finite|serializable|limit/);
      expect(persistence.getReconciliationDecisions(diagnosis.id)).toEqual([]);
    }
    const cycle: Record<string, unknown> = {}; cycle.self = cycle;
    persistence.close(); rmSync(directory, { recursive: true, force: true });
    directory = mkdtempSync(join(tmpdir(), 'graci-phase1n-cycle-')); path = join(directory, 'reconciliation.sqlite');
    persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize(); sequence = 0;
    const { diagnosis } = await recoverSource();
    await expect(reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider({
      conclusion: 'remains_indeterminate', operationId: 'external-operation-1', evidence: cycle, reason: 'cycle',
    }), command(diagnosis.id, 'cycle'))).rejects.toThrow(/cycle/);
  });

  it('keeps indeterminate work stopped, permits idempotent observations, and fails closed on provider errors or malformed evidence', async () => {
    const { task, diagnosis } = await recoverSource();
    const result = { conclusion: 'remains_indeterminate' as const, operationId: 'external-operation-1',
      evidence: { status: 'unknown' }, reason: 'provider cannot prove either outcome' };
    const firstCommand = command(diagnosis.id, 'unknown');
    const first = await reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider(result), firstCommand);
    expect(await reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider(result), firstCommand)).toEqual(first);
    expect(persistence.getTask(task.id)?.status).toBe('failed');
    expect(persistence.getAttempts(task.id)).toHaveLength(1);
    await expect(reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider({
      conclusion: 'proven_completed', operationId: 'wrong-operation', output: {}, evidence: {}, reason: 'wrong',
    }), command(diagnosis.id, 'malformed'))).rejects.toThrow(/Malformed or contradictory/);
    await expect(reconcileExternalOutcome(persistence, new DeterministicVerifier(), {
      providerId: 'throwing', providerVersion: 1, reconcile: async () => { throw new Error('offline'); },
    }, command(diagnosis.id, 'exception'))).rejects.toThrow(/failed closed/);
    expect(persistence.getReconciliationDecisions(diagnosis.id)).toHaveLength(1);
  });

  it('rejects a stale diagnosis after a newer Failure and trusted diagnosis become authoritative', async () => {
    const { task, diagnosis } = await recoverSource();
    const newer: Failure = { id: asIdentifier<'Failure'>('phase1n-newer-failure'), taskId: task.id,
      attemptId: diagnosis.attemptId, category: 'external_outcome_indeterminate',
      classification: 'external_outcome_indeterminate', code: 'NEWER_UNKNOWN', summary: 'Newer uncertainty evidence',
      details: {}, retryable: false, createdAt: '2026-08-14T22:00:01.000Z' };
    persistence.createFailure(newer, event(task.id, 'failure.recorded'));
    diagnosePersistedFailure(persistence, { failureId: newer.id, diagnosedBy: 'phase1n-test',
      diagnosedAt: '2026-08-14T22:00:01.000Z', eventId: event(task.id, 'failure.diagnosed').id });
    await expect(reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider({
      conclusion: 'remains_indeterminate', operationId: 'external-operation-1', evidence: { unknown: true }, reason: 'unknown',
    }), command(diagnosis.id, 'stale-failure'))).rejects.toThrow(/stale|contradictory/);
    expect(persistence.getReconciliationDecisions(diagnosis.id)).toEqual([]);
  });

  it('rejects a superseded source Attempt and creates no replay authority', async () => {
    const { task, diagnosis } = await recoverSource();
    persistence.createAttempt({ id: asIdentifier<'Attempt'>('phase1n-attempt-2'), taskId: task.id, attemptNumber: 2,
      status: 'failed', providerOfferingId: 'offering-original', inputSnapshot: {}, result: { failed: true },
      idempotencyKey: 'external-operation-2', completedAt: '2026-08-14T22:00:01.000Z',
      createdAt: '2026-08-14T22:00:01.000Z' }, event(task.id, 'attempt.failed'));
    await expect(reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider({
      conclusion: 'proven_not_completed', operationId: 'external-operation-1', evidence: { absent: true }, reason: 'absent',
    }), command(diagnosis.id, 'superseded-attempt'))).rejects.toThrow(/stale|contradictory/);
    expect(persistence.getAttempts(task.id)).toHaveLength(2);
    expect(persistence.getPendingReconciliation(task.id)).toBeUndefined();
  });

  it('rejects a source diagnosis after any alternative-recovery action', async () => {
    const { task, diagnosis } = await recoverSource();
    recoverWithAlternative(persistence, { id: asIdentifier<'AlternativeRecoveryDecision'>('phase1n-prior-recovery'),
      diagnosisId: diagnosis.id, requestedDisposition: 'alternative_offering_recommended', actor: 'phase1n-test',
      decidedAt: NOW, eventId: event(task.id, 'alternative-recovery.decided').id,
      evidenceId: asIdentifier<'ChangedConditionEvidence'>('phase1n-unused-evidence'),
      evidenceEventId: event(task.id, 'failure.changed-condition-recorded').id });
    await expect(reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider({
      conclusion: 'remains_indeterminate', operationId: 'external-operation-1', evidence: { unknown: true }, reason: 'unknown',
    }), command(diagnosis.id, 'prior-recovery'))).rejects.toThrow(/recovery action/);
    expect(persistence.getReconciliationDecisions(diagnosis.id)).toEqual([]);
  });

  it('rejects non-indeterminate latest diagnosis authority', async () => {
    const { task, diagnosis } = await recoverSource();
    const failure: Failure = { id: asIdentifier<'Failure'>('phase1n-non-indeterminate'), taskId: task.id,
      attemptId: diagnosis.attemptId, category: 'execution_defect', classification: 'permanent', code: 'KNOWN_FAILURE',
      summary: 'Known unsuccessful result', details: {}, retryable: false, createdAt: '2026-08-14T22:00:01.000Z' };
    persistence.createFailure(failure, event(task.id, 'failure.recorded'));
    const nonIndeterminate = diagnosePersistedFailure(persistence, { failureId: failure.id, diagnosedBy: 'phase1n-test',
      diagnosedAt: '2026-08-14T22:00:01.000Z', eventId: event(task.id, 'failure.diagnosed').id });
    await expect(reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider({
      conclusion: 'remains_indeterminate', operationId: 'external-operation-1', evidence: { unknown: true }, reason: 'unknown',
    }), command(nonIndeterminate.id, 'non-indeterminate'))).rejects.toThrow(/non-indeterminate|stale|contradictory/);
  });

  it('rejects command/evidence and conclusive authority conflicts while exact replay is idempotent', async () => {
    const { diagnosis } = await recoverSource();
    const result = { conclusion: 'remains_indeterminate' as const, operationId: 'external-operation-1',
      evidence: { observation: 1 }, reason: 'unknown' };
    const original = command(diagnosis.id, 'idempotent');
    const decision = await reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider(result), original);
    expect(await reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider(result), original)).toEqual(decision);
    await expect(reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider({ ...result,
      evidence: { observation: 2 } }), original)).rejects.toThrow(/identity conflict/);
    const conclusive = command(diagnosis.id, 'conclusive');
    await reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider({ conclusion: 'proven_not_completed',
      operationId: 'external-operation-1', evidence: { absent: true }, reason: 'absent' }), conclusive);
    await expect(reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider({ conclusion: 'proven_completed',
      operationId: 'external-operation-1', output: {}, evidence: { verificationPasses: true }, reason: 'conflict' }),
    command(diagnosis.id, 'conclusive-conflict'))).rejects.toThrow(/already concluded/);
  });

  it('does not mutate an unrelated Task while reconciling the source Task', async () => {
    const { task, diagnosis } = await recoverSource();
    const unrelated: Task = { ...task, id: asIdentifier<'Task'>('phase1n-unrelated'), title: 'Unrelated',
      status: 'planned', terminalReason: undefined, completedAt: undefined, version: 1 };
    persistence.createTask(unrelated, event(unrelated.id, 'task.created'));
    await reconcileExternalOutcome(persistence, new DeterministicVerifier(), provider({
      conclusion: 'remains_indeterminate', operationId: 'external-operation-1', evidence: { unknown: true }, reason: 'unknown',
    }), command(diagnosis.id, 'isolation'));
    expect(persistence.getTask(unrelated.id)).toEqual(unrelated);
    expect(persistence.getAttempts(unrelated.id)).toEqual([]);
  });

  it('migrates a populated schema-10 database to immutable schema 11 without fabricating history', () => {
    persistence.close();
    path = join(directory, 'schema10.sqlite');
    const database = new DatabaseSync(path);
    database.exec(`CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, applied_at TEXT NOT NULL) STRICT;`);
    for (const migration of migrations.filter((value) => value.version <= 10)) {
      migration.up(database);
      database.prepare('INSERT INTO schema_migrations VALUES (?, ?, ?)').run(migration.version, migration.name, NOW);
    }
    database.exec('PRAGMA user_version = 10');
    database.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath: path });
    persistence.initialize();
    expect(persistence.getSchemaVersion()).toBe(19);
    expect(persistence.getReconciliationDecisions(asIdentifier<'FailureDiagnosis'>('absent'))).toEqual([]);
  });
});

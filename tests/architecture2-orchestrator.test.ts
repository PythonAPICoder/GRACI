import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import {
  asIdentifier,
  type Attempt,
  type AuditEventInput,
  type Goal,
  type Task,
  type TaskDependency,
  type TaskGraphRevision,
  type TaskId,
  type Verification,
} from '../src/architecture2/domain/index.js';
import { DeterministicTestProvider, type DeterministicBehavior } from '../src/architecture2/execution/index.js';
import { SqliteArchitecture2Persistence } from '../src/architecture2/persistence/index.js';
import { DeterministicVerifier } from '../src/architecture2/verification/index.js';
import { InvalidTaskTransitionError, MinimalOrchestrator, TaskStateMachine } from '../src/architecture2/workflow/index.js';

const NOW = '2026-08-12T21:00:00.000Z';

describe('Architecture 2 Phase 1B workflow kernel', () => {
  let directory: string;
  let databasePath: string;
  let persistence: SqliteArchitecture2Persistence;
  let sequence: number;

  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'graci-phase1b-'));
    databasePath = join(directory, 'workflow.sqlite');
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    sequence = 0;
  });

  afterEach(() => {
    persistence.close();
    rmSync(directory, { recursive: true, force: true });
  });

  const taskId = (id: string) => asIdentifier<'Task'>(id);
  const graphId = (id = 'graph-1') => asIdentifier<'TaskGraphRevision'>(id);

  function nextId(kind: 'attempt' | 'verification' | 'failure' | 'approval' | 'event'): string {
    sequence += 1;
    return `${kind}-${sequence}`;
  }

  function event(aggregateId: string, eventType: string, id?: string): AuditEventInput {
    return {
      id: asIdentifier<'Event'>(id ?? nextId('event')),
      aggregateType: 'test',
      aggregateId,
      eventType,
      eventVersion: 1,
      actor: 'phase1b-test',
      occurredAt: NOW,
      payload: {},
    };
  }

  function task(id: string, status: Task['status'] = 'planned', createdAt = NOW): Task {
    return {
      id: taskId(id),
      goalId: asIdentifier<'Goal'>('goal-1'),
      graphRevisionId: graphId(),
      title: id,
      objective: `Execute ${id}`,
      inputs: {},
      requiredCapabilities: ['test.execute'],
      privacyClass: 'internal',
      priority: 'normal',
      status,
      required: true,
      retryPolicy: {},
      verificationPlan: { type: 'deterministic' },
      version: 1,
      createdAt,
      updatedAt: createdAt,
    };
  }

  function seedGraph(taskValues: Task[], dependencies: Array<[string, string]> = []): void {
    const goal: Goal = {
      id: asIdentifier<'Goal'>('goal-1'),
      objective: 'Execute a deterministic DAG',
      constraints: {},
      priority: 'normal',
      privacyClass: 'internal',
      status: 'active',
      version: 1,
      createdAt: NOW,
      updatedAt: NOW,
    };
    persistence.createGoal({ goal, criteria: [] }, event(goal.id, 'goal.created'));
    const revision: TaskGraphRevision = {
      id: graphId(), goalId: goal.id, revision: 1, rationale: 'Phase 1B test graph', createdAt: NOW,
    };
    persistence.createTaskGraphRevision(revision, event(revision.id, 'task_graph.created'));
    for (const value of taskValues) persistence.createTask(value, event(value.id, 'task.created'));
    for (const [predecessor, successor] of dependencies) {
      const dependency: TaskDependency = {
        graphRevisionId: revision.id,
        predecessorTaskId: taskId(predecessor),
        successorTaskId: taskId(successor),
        condition: 'success',
        createdAt: NOW,
      };
      persistence.createTaskDependency(dependency, event(revision.id, 'task_dependency.created'));
    }
  }

  function orchestrator(behaviors: ReadonlyMap<TaskId, DeterministicBehavior | readonly DeterministicBehavior[]> = new Map()) {
    const provider = new DeterministicTestProvider(behaviors);
    const value = new MinimalOrchestrator(persistence, provider, new DeterministicVerifier(), {
      actor: 'phase1b-test-orchestrator', now: () => NOW, nextId,
    });
    return { value, provider };
  }

  it('accepts valid transitions and rejects invalid or unguarded transitions', () => {
    const machine = new TaskStateMachine();
    const planned = task('task-1');
    const ready = machine.prepare(planned, 'ready', NOW, { dependenciesSatisfied: true });
    expect(ready.status).toBe('ready');
    expect(ready.version).toBe(2);
    expect(() => machine.prepare(planned, 'ready', NOW)).toThrow(InvalidTaskTransitionError);
    expect(() => machine.prepare({ ...planned, status: 'running' }, 'planned', NOW)).toThrow(InvalidTaskTransitionError);
    expect(() => machine.prepare({ ...planned, status: 'verifying' }, 'succeeded', NOW)).toThrow(/passing Verification/);
    expect(() => machine.prepare({ ...planned, status: 'succeeded', completedAt: NOW }, 'failed', NOW,
      { terminalReason: 'rewrite' })).toThrow(InvalidTaskTransitionError);
    expect(() => machine.prepare({ ...planned, status: 'running' }, 'retry_pending', NOW)).toThrow(/retry authorization/);
    expect(() => machine.prepare({ ...planned, status: 'verifying' }, 'retry_pending', NOW)).toThrow(/retry authorization/);
    expect(() => machine.prepare({ ...planned, status: 'running' }, 'waiting_for_approval', NOW))
      .toThrow(/approval-pause authorization/);
    expect(() => machine.prepare({ ...planned, status: 'waiting_for_approval' }, 'ready', NOW,
      { dependenciesSatisfied: true })).toThrow(/approval authorization/);
  });

  it('rejects stale optimistic transitions and leaves state and events unchanged', () => {
    seedGraph([task('task-1')]);
    const machine = new TaskStateMachine();
    const original = persistence.getTask(taskId('task-1'))!;
    machine.transition(persistence, original, 'ready', NOW, event(original.id, 'task.transitioned'),
      { dependenciesSatisfied: true });
    const eventCount = persistence.getEvents().length;
    expect(() => machine.transition(persistence, original, 'ready', NOW, event(original.id, 'task.transitioned.stale'),
      { dependenciesSatisfied: true })).toThrow(/concurrency conflict/);
    expect(persistence.getTask(original.id)?.version).toBe(2);
    expect(persistence.getEvents()).toHaveLength(eventCount);
  });

  it('does not run a task until its required dependency succeeds', async () => {
    seedGraph([task('task-a'), task('task-b')], [['task-a', 'task-b']]);
    const { value, provider } = orchestrator();
    const result = await value.run(graphId());
    expect(result.executedTaskIds).toEqual([taskId('task-a'), taskId('task-b')]);
    expect(provider.getExecutionCount(taskId('task-b'))).toBe(1);
    expect(result.status).toBe('succeeded');
  });

  it('executes a multi-level DAG in dependency order', async () => {
    seedGraph([task('task-c'), task('task-a'), task('task-b')], [['task-a', 'task-b'], ['task-b', 'task-c']]);
    const { value } = orchestrator();
    expect((await value.run(graphId())).executedTaskIds).toEqual([
      taskId('task-a'), taskId('task-b'), taskId('task-c'),
    ]);
  });

  it('uses created-at then identifier order for independent runnable tasks', async () => {
    seedGraph([
      task('task-z', 'planned', '2026-08-12T21:00:01.000Z'),
      task('task-b'),
      task('task-a'),
    ]);
    const { value } = orchestrator();
    expect((await value.run(graphId())).executedTaskIds).toEqual([
      taskId('task-a'), taskId('task-b'), taskId('task-z'),
    ]);
  });

  it('records provider failure, skips verification, and blocks required downstream work', async () => {
    seedGraph([task('task-a'), task('task-b')], [['task-a', 'task-b']]);
    const behaviors = new Map<TaskId, DeterministicBehavior>([[taskId('task-a'), { outcome: 'failure' }]]);
    const { value, provider } = orchestrator(behaviors);
    const result = await value.run(graphId());
    expect(result.status).toBe('failed');
    expect(result.terminal).toBe(true);
    expect(persistence.getTask(taskId('task-a'))?.status).toBe('failed');
    expect(persistence.getTask(taskId('task-b'))).toMatchObject({ status: 'blocked', terminalReason: 'required_dependency_failed' });
    expect(provider.getExecutionCount(taskId('task-b'))).toBe(0);
    expect(persistence.getAttempts(taskId('task-a'))).toHaveLength(1);
    expect(persistence.getFailures(taskId('task-a'))).toHaveLength(1);
    expect(persistence.getVerifications(taskId('task-a'))).toEqual([]);
  });

  it('requires deterministic verification before task success', async () => {
    seedGraph([task('task-a')]);
    const behaviors = new Map<TaskId, DeterministicBehavior>([[taskId('task-a'), {
      outcome: 'success', verificationPasses: false,
    }]]);
    const { value } = orchestrator(behaviors);
    const result = await value.run(graphId());
    expect(result.status).toBe('failed');
    expect(persistence.getAttempts(taskId('task-a'))[0]).toMatchObject({ status: 'succeeded' });
    expect(persistence.getVerifications(taskId('task-a'))[0]).toMatchObject({ verdict: 'failed' });
    expect(persistence.getTask(taskId('task-a'))?.status).toBe('failed');
    expect(persistence.getFailures(taskId('task-a'))[0]).toMatchObject({
      category: 'verification_failure', classification: 'verification_failed', retryable: false,
    });
  });

  it('persists passing verification and completes a successful DAG', async () => {
    seedGraph([task('task-a')]);
    const { value } = orchestrator();
    const result = await value.run(graphId());
    expect(result).toMatchObject({ status: 'succeeded', terminal: true, executedTaskIds: [taskId('task-a')] });
    expect(persistence.getAttempts(taskId('task-a'))[0]).toMatchObject({ attemptNumber: 1, status: 'succeeded' });
    expect(persistence.getVerifications(taskId('task-a'))[0]).toMatchObject({ verdict: 'passed' });
    expect(persistence.getTask(taskId('task-a'))?.status).toBe('succeeded');
  });

  it('creates distinct immutable attempts with deterministic per-task numbering', () => {
    seedGraph([task('task-a')]);
    const first: Attempt = {
      id: asIdentifier<'Attempt'>('attempt-1'), taskId: taskId('task-a'), attemptNumber: 1, status: 'failed',
      inputSnapshot: {}, result: { error: 1 }, completedAt: NOW, createdAt: NOW,
    };
    const second: Attempt = {
      ...first, id: asIdentifier<'Attempt'>('attempt-2'), attemptNumber: 2,
    };
    persistence.createAttempt(first, event(first.id, 'attempt.failed'));
    persistence.createAttempt(second, event(second.id, 'attempt.failed'));
    expect(persistence.getAttempts(taskId('task-a'))).toEqual([first, second]);
  });

  it('does not execute succeeded or failed terminal tasks again after restart', async () => {
    seedGraph([task('task-a'), task('task-b')]);
    const behaviors = new Map<TaskId, DeterministicBehavior>([[taskId('task-b'), { outcome: 'failure' }]]);
    const first = orchestrator(behaviors);
    await first.value.run(graphId());
    expect(first.provider.getExecutionCount(taskId('task-a'))).toBe(1);
    expect(first.provider.getExecutionCount(taskId('task-b'))).toBe(1);
    persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    const restarted = orchestrator(behaviors);
    const result = await restarted.value.run(graphId());
    expect(result.executedTaskIds).toEqual([]);
    expect(restarted.provider.getExecutionCount(taskId('task-a'))).toBe(0);
    expect(restarted.provider.getExecutionCount(taskId('task-b'))).toBe(0);
    expect(persistence.getAttempts(taskId('task-a'))).toHaveLength(1);
    expect(persistence.getAttempts(taskId('task-b'))).toHaveLength(1);
  });

  it('continues planned dependent work from durable state after reopen', async () => {
    seedGraph([task('task-a'), task('task-b')], [['task-a', 'task-b']]);
    const machine = new TaskStateMachine();
    let root = persistence.getTask(taskId('task-a'))!;
    root = machine.transition(persistence, root, 'ready', NOW, event(root.id, 'task.transitioned'), { dependenciesSatisfied: true });
    root = machine.transition(persistence, root, 'scheduled', NOW, event(root.id, 'task.transitioned'));
    const attempt: Attempt = { id: asIdentifier<'Attempt'>('attempt-root'), taskId: root.id, attemptNumber: 1,
      status: 'running', inputSnapshot: {}, startedAt: NOW, createdAt: NOW };
    const running = machine.prepare(root, 'running', NOW, { attempt });
    persistence.startAttempt(running, root.version, attempt, [event(root.id, 'attempt.started')]);
    const completedAttempt: Attempt = { ...attempt, status: 'succeeded', result: {}, completedAt: NOW };
    const verifying = machine.prepare(running, 'verifying', NOW, { attempt: completedAttempt });
    persistence.recordAttemptOutcome(verifying, running.version, completedAttempt, undefined, [event(root.id, 'attempt.succeeded')]);
    const verification: Verification = { id: asIdentifier<'Verification'>('verification-root'), taskId: root.id,
      attemptId: attempt.id, verdict: 'passed', planVersion: 1, verifier: 'test', criterionResults: {}, evidence: {}, createdAt: NOW };
    const succeeded = machine.prepare(verifying, 'succeeded', NOW, { verification });
    persistence.recordVerificationOutcome(succeeded, verifying.version, verification, undefined, [event(root.id, 'verification.passed')]);
    persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    const restarted = orchestrator();
    const result = await restarted.value.run(graphId());
    expect(result.executedTaskIds).toEqual([taskId('task-b')]);
    expect(persistence.getAttempts(taskId('task-a'))).toHaveLength(1);
    expect(persistence.getAttempts(taskId('task-b'))).toHaveLength(1);
  });

  it('recovers interrupted running work as indeterminate failure without replay', async () => {
    seedGraph([task('task-a')]);
    const machine = new TaskStateMachine();
    let value = persistence.getTask(taskId('task-a'))!;
    value = machine.transition(persistence, value, 'ready', NOW, event(value.id, 'task.transitioned'), { dependenciesSatisfied: true });
    value = machine.transition(persistence, value, 'scheduled', NOW, event(value.id, 'task.transitioned'));
    const attempt: Attempt = { id: asIdentifier<'Attempt'>('attempt-interrupted'), taskId: value.id, attemptNumber: 1,
      status: 'running', inputSnapshot: {}, startedAt: NOW, createdAt: NOW };
    const running = machine.prepare(value, 'running', NOW, { attempt });
    persistence.startAttempt(running, value.version, attempt, [event(value.id, 'attempt.started')]);
    persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    const restarted = orchestrator();
    const result = await restarted.value.run(graphId());
    expect(result.executedTaskIds).toEqual([]);
    expect(restarted.provider.getExecutionCount(taskId('task-a'))).toBe(0);
    expect(persistence.getTask(taskId('task-a'))).toMatchObject({ status: 'failed', terminalReason: 'INTERRUPTED_RUNNING_ATTEMPT' });
    expect(persistence.getAttempts(taskId('task-a'))[0]).toMatchObject({ status: 'indeterminate' });
    expect(persistence.getFailures(taskId('task-a'))[0]).toMatchObject({
      category: 'external_outcome_indeterminate', classification: 'external_outcome_indeterminate', retryable: false,
    });
  });

  it('rolls back a transition when its event fails', () => {
    seedGraph([task('task-a')]);
    const duplicate = 'event-duplicate';
    persistence.appendEvent(event('seed', 'seed', duplicate));
    const original = persistence.getTask(taskId('task-a'))!;
    const machine = new TaskStateMachine();
    expect(() => machine.transition(persistence, original, 'ready', NOW,
      event(original.id, 'task.transitioned', duplicate), { dependenciesSatisfied: true })).toThrow();
    expect(persistence.getTask(original.id)).toEqual(original);
  });

  it('rolls back task and Attempt creation when an Attempt transaction event fails', () => {
    seedGraph([task('task-a')]);
    const duplicate = 'event-attempt-duplicate';
    persistence.appendEvent(event('seed', 'seed', duplicate));
    const machine = new TaskStateMachine();
    let value = persistence.getTask(taskId('task-a'))!;
    value = machine.transition(persistence, value, 'ready', NOW, event(value.id, 'task.transitioned'), { dependenciesSatisfied: true });
    value = machine.transition(persistence, value, 'scheduled', NOW, event(value.id, 'task.transitioned'));
    const attempt: Attempt = { id: asIdentifier<'Attempt'>('attempt-atomic'), taskId: value.id, attemptNumber: 1,
      status: 'running', inputSnapshot: {}, startedAt: NOW, createdAt: NOW };
    const running = machine.prepare(value, 'running', NOW, { attempt });
    expect(() => persistence.startAttempt(running, value.version, attempt,
      [event(value.id, 'attempt.started', duplicate)])).toThrow();
    expect(persistence.getTask(value.id)).toEqual(value);
    expect(persistence.getAttempts(value.id)).toEqual([]);
  });

  it('retries a transient failure and preserves both attempts before success', async () => {
    seedGraph([{ ...task('task-a'), retryPolicy: { maxAttempts: 3 } }]);
    const behaviors = new Map<TaskId, readonly DeterministicBehavior[]>([[taskId('task-a'), [
      { outcome: 'failure', classification: 'transient' },
      { outcome: 'success', verificationPasses: true },
    ]]]);
    const { value } = orchestrator(behaviors);
    expect((await value.run(graphId())).status).toBe('succeeded');
    expect(persistence.getAttempts(taskId('task-a')).map(({ attemptNumber, status }) => ({ attemptNumber, status })))
      .toEqual([{ attemptNumber: 1, status: 'failed' }, { attemptNumber: 2, status: 'succeeded' }]);
    expect(persistence.getFailures(taskId('task-a'))[0]).toMatchObject({ classification: 'transient', retryable: true });
  });

  it('stops transient retries at the durable maximum and remains exhausted after restart', async () => {
    seedGraph([{ ...task('task-a'), retryPolicy: { maxAttempts: 3 } }]);
    const behaviors = new Map<TaskId, DeterministicBehavior>([[taskId('task-a'),
      { outcome: 'failure', classification: 'transient' }]]);
    await orchestrator(behaviors).value.run(graphId());
    expect(persistence.getAttempts(taskId('task-a'))).toHaveLength(3);
    expect(persistence.getTask(taskId('task-a'))?.status).toBe('failed');
    persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    const restarted = orchestrator(behaviors);
    expect((await restarted.value.run(graphId())).executedTaskIds).toEqual([]);
    expect(restarted.provider.getExecutionCount(taskId('task-a'))).toBe(0);
    expect(persistence.getAttempts(taskId('task-a'))).toHaveLength(3);
  });

  it('does not retry permanent or verification failures by default', async () => {
    seedGraph([task('task-a')]);
    await orchestrator(new Map([[taskId('task-a'), { outcome: 'failure', classification: 'permanent' }]])).value.run(graphId());
    expect(persistence.getAttempts(taskId('task-a'))).toHaveLength(1);
    expect(persistence.getFailures(taskId('task-a'))[0]).toMatchObject({ classification: 'permanent', retryable: false });

    persistence.close();
    rmSync(directory, { recursive: true, force: true });
    directory = mkdtempSync(join(tmpdir(), 'graci-phase1c-verification-'));
    databasePath = join(directory, 'workflow.sqlite');
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    seedGraph([task('task-a')]);
    await orchestrator(new Map([[taskId('task-a'), { outcome: 'success', verificationPasses: false }]])).value.run(graphId());
    expect(persistence.getAttempts(taskId('task-a'))).toHaveLength(1);
    expect(persistence.getFailures(taskId('task-a'))[0]).toMatchObject({ classification: 'verification_failed', retryable: false });
  });

  it('durably pauses for approval, survives restart, and resumes the same task after explicit approval', async () => {
    seedGraph([task('task-a')]);
    const pause = new Map<TaskId, DeterministicBehavior>([[taskId('task-a'),
      { outcome: 'failure', classification: 'approval_required', summary: 'Authorize continuation' }]]);
    await orchestrator(pause).value.run(graphId());
    expect(persistence.getTask(taskId('task-a'))?.status).toBe('waiting_for_approval');
    expect(persistence.getAttempts(taskId('task-a'))).toHaveLength(1);
    expect(persistence.getApprovals(taskId('task-a'))[0]).toMatchObject({ decision: 'requested' });
    expect(persistence.getFailures(taskId('task-a'))[0]).toMatchObject({
      classification: 'approval_required', retryable: false,
    });

    persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    const restarted = orchestrator();
    expect((await restarted.value.run(graphId())).executedTaskIds).toEqual([]);
    expect(restarted.provider.getExecutionCount(taskId('task-a'))).toBe(0);
    restarted.value.approveTask(taskId('task-a'));
    expect((await restarted.value.run(graphId())).status).toBe('succeeded');
    expect(persistence.getAttempts(taskId('task-a')).map((attempt) => attempt.attemptNumber)).toEqual([1, 2]);
    expect(persistence.getApprovals(taskId('task-a'))[0]).toMatchObject({ decision: 'approved' });
  });

  it('rejects approval for a task that is not awaiting approval', () => {
    seedGraph([task('task-a')]);
    expect(() => orchestrator().value.approveTask(taskId('task-a'))).toThrow(/not awaiting approval/);
  });

  it('permits an explicitly authorized bounded verification retry and preserves history', async () => {
    seedGraph([{ ...task('task-a'), retryPolicy: { maxAttempts: 2, retryVerificationFailures: true } }]);
    const behaviors = new Map<TaskId, readonly DeterministicBehavior[]>([[taskId('task-a'), [
      { outcome: 'success', verificationPasses: false },
      { outcome: 'success', verificationPasses: true },
    ]]]);
    const { value } = orchestrator(behaviors);
    expect((await value.run(graphId())).status).toBe('succeeded');
    expect(persistence.getAttempts(taskId('task-a')).map((attempt) => attempt.attemptNumber)).toEqual([1, 2]);
    expect(persistence.getVerifications(taskId('task-a')).map((verification) => verification.verdict))
      .toEqual(['failed', 'passed']);
    expect(persistence.getFailures(taskId('task-a'))[0]).toMatchObject({
      classification: 'verification_failed', retryable: true,
    });
  });

  it('bounds explicitly authorized verification retries by maxAttempts', async () => {
    seedGraph([{ ...task('task-a'), retryPolicy: { maxAttempts: 2, retryVerificationFailures: true } }]);
    const behaviors = new Map<TaskId, DeterministicBehavior>([[taskId('task-a'),
      { outcome: 'success', verificationPasses: false }]]);
    await orchestrator(behaviors).value.run(graphId());
    expect(persistence.getTask(taskId('task-a'))?.status).toBe('failed');
    expect(persistence.getAttempts(taskId('task-a'))).toHaveLength(2);
    expect(persistence.getVerifications(taskId('task-a'))).toHaveLength(2);
    expect(persistence.getFailures(taskId('task-a')).at(-1)).toMatchObject({ retryable: false });
  });

  it('fails closed when durable retry_pending history does not prove retry safety', async () => {
    seedGraph([task('task-a', 'retry_pending')]);
    const restarted = orchestrator();
    expect((await restarted.value.run(graphId())).executedTaskIds).toEqual([]);
    expect(restarted.provider.getExecutionCount(taskId('task-a'))).toBe(0);
    expect(persistence.getTask(taskId('task-a'))).toMatchObject({
      status: 'failed', terminalReason: 'UNSAFE_RETRY_PENDING_STATE',
    });
    expect(persistence.getFailures(taskId('task-a')).at(-1)).toMatchObject({
      classification: 'permanent', retryable: false, code: 'UNSAFE_RETRY_PENDING_STATE',
    });
  });

  it('durably denies a paused task and never resumes it after restart', async () => {
    seedGraph([task('task-a')]);
    const pause = new Map<TaskId, DeterministicBehavior>([[taskId('task-a'),
      { outcome: 'failure', classification: 'approval_required' }]]);
    const first = orchestrator(pause);
    await first.value.run(graphId());
    first.value.denyTask(taskId('task-a'), 'Risk not accepted');
    expect(persistence.getTask(taskId('task-a'))).toMatchObject({
      status: 'failed', terminalReason: 'APPROVAL_DENIED: Risk not accepted',
    });
    expect(persistence.getApprovals(taskId('task-a'))[0]).toMatchObject({
      decision: 'denied', scope: { denialReason: 'Risk not accepted' },
    });
    expect(persistence.getEvents().some((value) => value.eventType === 'approval.denied' &&
      value.payload.reason === 'Risk not accepted')).toBe(true);

    persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    const restarted = orchestrator();
    expect((await restarted.value.run(graphId())).executedTaskIds).toEqual([]);
    expect(restarted.provider.getExecutionCount(taskId('task-a'))).toBe(0);
  });

  it('rejects denial for a task that is not awaiting approval', () => {
    seedGraph([task('task-a')]);
    expect(() => orchestrator().value.denyTask(taskId('task-a'), 'Not applicable')).toThrow(/not awaiting approval/);
  });
});

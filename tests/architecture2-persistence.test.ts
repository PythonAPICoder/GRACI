import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { DatabaseSync } from 'node:sqlite';
import {
  asIdentifier,
  type Attempt,
  type AuditEventInput,
  type Goal,
  type GoalSuccessCriterion,
  type Task,
  type TaskDependency,
  type TaskGraphRevision,
} from '../src/architecture2/domain/index.js';
import { SqliteArchitecture2Persistence } from '../src/architecture2/persistence/index.js';
import { migrations } from '../src/architecture2/persistence/sqlite/migrations.js';

const NOW = '2026-08-12T20:00:00.000Z';

describe('Architecture 2 SQLite persistence', () => {
  let directory: string;
  let databasePath: string;
  let persistence: SqliteArchitecture2Persistence;
  let eventCounter: number;

  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'graci-phase1a-'));
    databasePath = join(directory, 'kernel.sqlite');
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    eventCounter = 0;
  });

  afterEach(() => {
    persistence.close();
    rmSync(directory, { recursive: true, force: true });
  });

  function event(aggregateId: string, eventType: string, id?: string): AuditEventInput {
    eventCounter += 1;
    return {
      id: asIdentifier<'Event'>(id ?? `event-${eventCounter}`),
      aggregateType: 'test',
      aggregateId,
      eventType,
      eventVersion: 1,
      actor: 'phase1a-test',
      occurredAt: NOW,
      payload: { eventCounter },
    };
  }

  function goal(id = 'goal-1'): Goal {
    return {
      id: asIdentifier<'Goal'>(id),
      objective: 'Prove durable workflow persistence',
      constraints: {},
      priority: 'normal',
      privacyClass: 'internal',
      status: 'draft',
      version: 1,
      createdAt: NOW,
      updatedAt: NOW,
    };
  }

  function criterion(goalId = 'goal-1'): GoalSuccessCriterion {
    return {
      id: asIdentifier<'GoalCriterion'>(`criterion-${goalId}`),
      goalId: asIdentifier<'Goal'>(goalId),
      description: 'Persistence tests pass',
      required: true,
      verificationMethod: 'automated_test',
      position: 0,
      createdAt: NOW,
    };
  }

  function revision(goalId = 'goal-1', id = 'graph-1', number = 1): TaskGraphRevision {
    return {
      id: asIdentifier<'TaskGraphRevision'>(id),
      goalId: asIdentifier<'Goal'>(goalId),
      revision: number,
      rationale: 'Initial immutable task graph',
      createdAt: NOW,
    };
  }

  function task(id: string, graphRevisionId = 'graph-1', goalId = 'goal-1'): Task {
    return {
      id: asIdentifier<'Task'>(id),
      goalId: asIdentifier<'Goal'>(goalId),
      graphRevisionId: asIdentifier<'TaskGraphRevision'>(graphRevisionId),
      title: id,
      objective: `Execute ${id}`,
      inputs: {},
      requiredCapabilities: ['test.execute'],
      privacyClass: 'internal',
      priority: 'normal',
      status: 'planned',
      required: true,
      retryPolicy: { maxAttempts: 2 },
      verificationPlan: { method: 'test' },
      version: 1,
      createdAt: NOW,
      updatedAt: NOW,
    };
  }

  function createGraphWithTasks(): void {
    const value = goal();
    persistence.createGoal({ goal: value, criteria: [criterion()] }, event(value.id, 'goal.created'));
    const graph = revision();
    persistence.createTaskGraphRevision(graph, event(graph.id, 'task_graph.created'));
    persistence.createTask(task('task-1'), event('task-1', 'task.created'));
    persistence.createTask(task('task-2'), event('task-2', 'task.created'));
  }

  it('initializes a new database through the current schema version', () => {
    expect(persistence.getSchemaVersion()).toBe(2);
    expect(persistence.getEvents()).toEqual([]);
  });

  it('persists domain records across close and reopen', () => {
    const value = goal();
    persistence.createGoal({ goal: value, criteria: [criterion()] }, event(value.id, 'goal.created'));
    persistence.close();

    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();

    const stored = persistence.getGoal(value.id);
    expect(stored?.goal).toEqual(value);
    expect(stored?.criteria).toEqual([criterion()]);
    expect(persistence.getEvents()).toHaveLength(1);
  });

  it('rejects foreign-key violations and does not append an event', () => {
    const orphan = revision('missing-goal', 'orphan-graph');
    expect(() => persistence.createTaskGraphRevision(orphan, event(orphan.id, 'task_graph.created'))).toThrow();
    expect(persistence.getTaskGraphRevisions(asIdentifier<'Goal'>('missing-goal'))).toEqual([]);
    expect(persistence.getEvents()).toEqual([]);
  });

  it('rejects invalid and duplicate identifiers or graph revisions', () => {
    const invalid = { ...goal(), id: 'contains spaces' as Goal['id'] };
    expect(() => persistence.createGoal({ goal: invalid, criteria: [] }, event('invalid', 'goal.created'))).toThrow(/Invalid goal id/);

    const value = goal();
    persistence.createGoal({ goal: value, criteria: [criterion()] }, event(value.id, 'goal.created'));
    const first = revision();
    persistence.createTaskGraphRevision(first, event(first.id, 'task_graph.created'));
    const duplicateNumber = revision('goal-1', 'graph-2', 1);
    expect(() => persistence.createTaskGraphRevision(duplicateNumber, event(duplicateNumber.id, 'task_graph.created'))).toThrow();
    expect(persistence.getTaskGraphRevisions(value.id)).toHaveLength(1);
  });

  it('persists and deterministically queries a task dependency', () => {
    createGraphWithTasks();
    const dependency: TaskDependency = {
      graphRevisionId: asIdentifier<'TaskGraphRevision'>('graph-1'),
      predecessorTaskId: asIdentifier<'Task'>('task-1'),
      successorTaskId: asIdentifier<'Task'>('task-2'),
      condition: 'success',
      createdAt: NOW,
    };
    persistence.createTaskDependency(dependency, event('graph-1', 'task_dependency.created'));
    expect(persistence.getTaskDependencies(dependency.graphRevisionId)).toEqual([dependency]);
  });

  it('rejects self-dependencies', () => {
    createGraphWithTasks();
    const dependency: TaskDependency = {
      graphRevisionId: asIdentifier<'TaskGraphRevision'>('graph-1'),
      predecessorTaskId: asIdentifier<'Task'>('task-1'),
      successorTaskId: asIdentifier<'Task'>('task-1'),
      condition: 'success',
      createdAt: NOW,
    };
    expect(() => persistence.createTaskDependency(dependency, event('graph-1', 'task_dependency.created'))).toThrow();
    expect(persistence.getTaskDependencies(dependency.graphRevisionId)).toEqual([]);
  });

  it('preserves every retry-like attempt as a distinct record', () => {
    createGraphWithTasks();
    const base: Omit<Attempt, 'id' | 'attemptNumber'> = {
      taskId: asIdentifier<'Task'>('task-1'),
      status: 'failed',
      inputSnapshot: { input: 1 },
      result: { error: 'test failure' },
      completedAt: NOW,
      createdAt: NOW,
    };
    const first: Attempt = { ...base, id: asIdentifier<'Attempt'>('attempt-1'), attemptNumber: 1 };
    const second: Attempt = { ...base, id: asIdentifier<'Attempt'>('attempt-2'), attemptNumber: 2 };
    persistence.createAttempt(first, event(first.id, 'attempt.completed'));
    persistence.createAttempt(second, event(second.id, 'attempt.completed'));
    expect(persistence.getAttempts(base.taskId)).toEqual([first, second]);
  });

  it('exposes append-only event insertion with deterministic sequence and hash chaining', () => {
    const first = persistence.appendEvent(event('goal-1', 'test.first'));
    const second = persistence.appendEvent(event('goal-1', 'test.second'));
    expect(first.sequence).toBe(1);
    expect(first.previousHash).toBeUndefined();
    expect(first.eventHash).toMatch(/^[a-f0-9]{64}$/);
    expect(second.sequence).toBe(2);
    expect(second.previousHash).toBe(first.eventHash);
    expect(persistence.getEvents(1)).toEqual([second]);
    expect(() => persistence.appendEvent({ ...event('goal-1', 'duplicate'), id: first.id })).toThrow();
    expect(persistence.getEvents()).toHaveLength(2);
  });

  it('rolls back state when corresponding event insertion fails', () => {
    const duplicateEventId = 'event-rollback';
    const value = goal('goal-rollback');
    persistence.createGoal({ goal: value, criteria: [] }, event(value.id, 'goal.created'));
    persistence.appendEvent(event('seed', 'seed.created', duplicateEventId));
    const updated: Goal = { ...value, status: 'active', version: 2, updatedAt: '2026-08-12T20:01:00.000Z' };
    expect(() => persistence.updateGoal(updated, 1, event(value.id, 'goal.updated', duplicateEventId))).toThrow();
    expect(persistence.getGoal(value.id)?.goal).toEqual(value);
    expect(persistence.getEvents()).toHaveLength(2);
  });

  it('detects optimistic concurrency conflicts without changing state or events', () => {
    const value = goal();
    persistence.createGoal({ goal: value, criteria: [] }, event(value.id, 'goal.created'));
    const updated: Goal = { ...value, status: 'active', version: 2, updatedAt: '2026-08-12T20:01:00.000Z' };
    persistence.updateGoal(updated, 1, event(value.id, 'goal.updated'));
    const stale: Goal = { ...updated, status: 'blocked', version: 2, updatedAt: '2026-08-12T20:02:00.000Z' };
    expect(() => persistence.updateGoal(stale, 1, event(value.id, 'goal.updated.stale'))).toThrow(/concurrency conflict/);
    expect(persistence.getGoal(value.id)?.goal).toEqual(updated);
    expect(persistence.getEvents()).toHaveLength(2);
  });

  it('keeps test databases isolated and disposable', () => {
    const secondPath = join(directory, 'second.sqlite');
    const second = new SqliteArchitecture2Persistence({ databasePath: secondPath });
    second.initialize();
    try {
      persistence.appendEvent(event('first', 'first.created'));
      expect(second.getSchemaVersion()).toBe(2);
      expect(second.getEvents()).toEqual([]);
    } finally {
      second.close();
    }
  });

  it('conservatively migrates populated schema-1 failure history without making work runnable', () => {
    persistence.close();
    databasePath = join(directory, 'legacy.sqlite');
    const legacy = new DatabaseSync(databasePath);
    legacy.exec('PRAGMA foreign_keys = ON');
    legacy.exec(`CREATE TABLE schema_migrations (
      version INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, applied_at TEXT NOT NULL
    ) STRICT`);
    migrations[0].up(legacy);
    legacy.prepare('INSERT INTO schema_migrations(version, name, applied_at) VALUES (1, ?, ?)')
      .run(migrations[0].name, NOW);
    legacy.exec('PRAGMA user_version = 1');
    legacy.prepare(`INSERT INTO goals
      (id, objective, constraints_json, priority, privacy_class, status, version, created_at, updated_at)
      VALUES ('legacy-goal', 'Preserve legacy failures', '{}', 'normal', 'internal', 'active', 1, ?, ?)`)
      .run(NOW, NOW);
    legacy.prepare(`INSERT INTO task_graph_revisions(id, goal_id, revision, rationale, created_at)
      VALUES ('legacy-graph', 'legacy-goal', 1, 'Legacy graph', ?)`)
      .run(NOW);
    legacy.prepare(`INSERT INTO tasks
      (id, goal_id, graph_revision_id, title, objective, inputs_json, required_capabilities_json,
       privacy_class, priority, status, required, retry_policy_json, verification_plan_json,
       terminal_reason, version, created_at, updated_at, completed_at)
      VALUES ('legacy-task', 'legacy-goal', 'legacy-graph', 'Legacy task', 'Inspect migration', '{}', '[]',
       'internal', 'normal', 'failed', 1, '{}', '{}', 'LEGACY_FAILURE', 1, ?, ?, ?)`)
      .run(NOW, NOW, NOW);
    const insertFailure = legacy.prepare(`INSERT INTO failures
      (id, task_id, category, code, summary, details_json, retryable, created_at)
      VALUES (?, 'legacy-task', ?, ?, ?, ?, ?, ?)`);
    insertFailure.run('failure-transient', 'transient_infrastructure', 'TRANSIENT', 'Temporary outage',
      '{"source":"legacy"}', 1, '2026-08-12T20:00:01.000Z');
    insertFailure.run('failure-resource', 'resource_unavailable', 'RESOURCE', 'Missing resource',
      '{"source":"legacy"}', 1, '2026-08-12T20:00:02.000Z');
    insertFailure.run('failure-policy', 'policy_or_approval', 'POLICY', 'Policy rejected',
      '{"source":"legacy"}', 0, '2026-08-12T20:00:03.000Z');
    insertFailure.run('failure-verification', 'verification_failure', 'VERIFY', 'Verification rejected',
      '{"source":"legacy"}', 0, '2026-08-12T20:00:04.000Z');
    insertFailure.run('failure-indeterminate', 'external_outcome_indeterminate', 'UNKNOWN_OUTCOME', 'Outcome unknown',
      '{"source":"legacy"}', 0, '2026-08-12T20:00:05.000Z');
    legacy.close();

    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    expect(persistence.getSchemaVersion()).toBe(2);
    expect(persistence.getTask(asIdentifier<'Task'>('legacy-task'))?.status).toBe('failed');
    const failures = persistence.getFailures(asIdentifier<'Task'>('legacy-task'));
    expect(failures).toHaveLength(5);
    expect(failures.map(({ category, classification, code, summary, details, retryable, createdAt }) => ({
      category, classification, code, summary, details, retryable, createdAt,
    }))).toEqual([
      { category: 'transient_infrastructure', classification: 'transient', code: 'TRANSIENT',
        summary: 'Temporary outage', details: { source: 'legacy' }, retryable: true, createdAt: '2026-08-12T20:00:01.000Z' },
      { category: 'resource_unavailable', classification: 'permanent', code: 'RESOURCE',
        summary: 'Missing resource', details: { source: 'legacy' }, retryable: true, createdAt: '2026-08-12T20:00:02.000Z' },
      { category: 'policy_or_approval', classification: 'permanent', code: 'POLICY',
        summary: 'Policy rejected', details: { source: 'legacy' }, retryable: false, createdAt: '2026-08-12T20:00:03.000Z' },
      { category: 'verification_failure', classification: 'verification_failed', code: 'VERIFY',
        summary: 'Verification rejected', details: { source: 'legacy' }, retryable: false, createdAt: '2026-08-12T20:00:04.000Z' },
      { category: 'external_outcome_indeterminate', classification: 'external_outcome_indeterminate', code: 'UNKNOWN_OUTCOME',
        summary: 'Outcome unknown', details: { source: 'legacy' }, retryable: false, createdAt: '2026-08-12T20:00:05.000Z' },
    ]);
  });
});

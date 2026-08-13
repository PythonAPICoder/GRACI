import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { DatabaseSync } from 'node:sqlite';
import {
  asIdentifier,
  type AuditEventInput,
  type Goal,
  type Task,
  type TaskDependency,
  type TaskGraphRevision,
  type TaskId,
} from '../src/architecture2/domain/index.js';
import { SqliteArchitecture2Persistence } from '../src/architecture2/persistence/index.js';
import {
  getReadyTasksInScheduleOrder,
  inspectQueue,
  selectNextReadyTask,
  TaskGraphValidationError,
  validateTaskGraph,
} from '../src/architecture2/workflow/index.js';

const NOW = '2026-08-13T20:00:00.000Z';

describe('Architecture 2 Phase 1D durable queue', () => {
  let directory: string;
  let databasePath: string;
  let persistence: SqliteArchitecture2Persistence;
  let eventNumber: number;

  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'graci-phase1d-'));
    databasePath = join(directory, 'queue.sqlite');
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    eventNumber = 0;
  });

  afterEach(() => {
    persistence.close();
    rmSync(directory, { recursive: true, force: true });
  });

  const taskId = (id: string) => asIdentifier<'Task'>(id);
  const graphId = () => asIdentifier<'TaskGraphRevision'>('graph-1');

  function event(aggregateId: string, eventType: string, forcedId?: string): AuditEventInput {
    eventNumber += 1;
    return { id: asIdentifier<'Event'>(forcedId ?? `queue-event-${eventNumber}`), aggregateType: 'test', aggregateId,
      eventType, eventVersion: 1, actor: 'phase1d-test', occurredAt: NOW, payload: {} };
  }

  function goal(): Goal {
    return { id: asIdentifier<'Goal'>('goal-1'), objective: 'Exercise the durable queue', constraints: {}, priority: 'normal',
      privacyClass: 'internal', status: 'active', version: 1, createdAt: NOW, updatedAt: NOW };
  }

  function revision(): TaskGraphRevision {
    return { id: graphId(), goalId: goal().id, revision: 1, rationale: 'Phase 1D graph', createdAt: NOW };
  }

  function task(id: string, status: Task['status'] = 'planned', createdAt = NOW): Task {
    const terminal = ['succeeded', 'failed', 'cancelled', 'superseded'].includes(status);
    return { id: taskId(id), goalId: goal().id, graphRevisionId: graphId(), title: id, objective: `Execute ${id}`,
      inputs: {}, requiredCapabilities: ['test.execute'], privacyClass: 'internal', priority: 'normal', status,
      required: true, retryPolicy: {}, verificationPlan: {}, terminalReason: status === 'failed' ? 'TEST_FAILURE' : undefined,
      version: 1, createdAt, updatedAt: createdAt, completedAt: terminal ? createdAt : undefined };
  }

  function dependency(predecessor: string, successor: string, condition: TaskDependency['condition'] = 'success',
    predicate?: Record<string, unknown>): TaskDependency {
    return { graphRevisionId: graphId(), predecessorTaskId: taskId(predecessor), successorTaskId: taskId(successor),
      condition, predicate, createdAt: NOW };
  }

  function seedGoal(): void {
    const value = goal();
    persistence.createGoal({ goal: value, criteria: [] }, event(value.id, 'goal.created'));
  }

  function admit(tasks: Task[], dependencies: TaskDependency[] = []): void {
    seedGoal();
    const graph = revision();
    persistence.admitTaskGraph(graph, tasks, dependencies, [
      event(graph.id, 'task_graph.admitted'),
      ...tasks.map((value) => event(value.id, 'task.created')),
      ...dependencies.map(() => event(graph.id, 'task_dependency.created')),
    ]);
  }

  it('atomically admits, retrieves, and reconstructs a complete graph after reopen', () => {
    const tasks = [task('task-b'), task('task-a')];
    const edges = [dependency('task-a', 'task-b')];
    admit(tasks, edges);
    expect(persistence.getTasks(graphId()).map((value) => value.id)).toEqual([taskId('task-a'), taskId('task-b')]);
    expect(persistence.getTaskDependencies(graphId())).toEqual(edges);
    persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    expect(persistence.getTasks(graphId()).map((value) => value.id)).toEqual([taskId('task-a'), taskId('task-b')]);
    expect(persistence.getTaskDependencies(graphId())).toEqual(edges);
  });

  it('rolls back every graph record when an admission event fails', () => {
    seedGoal();
    persistence.appendEvent(event('seed', 'seed.created', 'duplicate-event'));
    const graph = revision();
    const tasks = [task('task-a'), task('task-b')];
    expect(() => persistence.admitTaskGraph(graph, tasks, [dependency('task-a', 'task-b')], [
      event(graph.id, 'task_graph.admitted'), event('task-a', 'task.created'),
      event('task-b', 'task.created'), event(graph.id, 'task_dependency.created', 'duplicate-event'),
    ])).toThrow();
    expect(persistence.getTaskGraphRevision(graph.id)).toBeUndefined();
    expect(persistence.getTasks(graph.id)).toEqual([]);
    expect(persistence.getTaskDependencies(graph.id)).toEqual([]);
  });

  it('selects ready Tasks only by createdAt then lexical Task ID independent of input order', () => {
    const values = [
      task('task-z', 'ready', '2026-08-13T20:00:01.000Z'), task('task-b', 'ready'),
      task('task-a', 'ready'), task('task-0', 'planned', '2026-08-13T19:00:00.000Z'),
    ];
    const expected = [taskId('task-a'), taskId('task-b'), taskId('task-z')];
    expect(getReadyTasksInScheduleOrder(values).map((value) => value.id)).toEqual(expected);
    expect(getReadyTasksInScheduleOrder([...values].reverse()).map((value) => value.id)).toEqual(expected);
    expect(selectNextReadyTask(values)?.id).toBe(taskId('task-a'));
    expect(selectNextReadyTask(values)?.id).toBe(taskId('task-a'));
  });

  it('produces the same scheduler selection after persistence reconstruction', () => {
    admit([task('task-z', 'ready', '2026-08-13T20:00:01.000Z'), task('task-b', 'ready'), task('task-a', 'ready')]);
    expect(selectNextReadyTask(persistence.getTasks(graphId()))?.id).toBe(taskId('task-a'));
    persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    expect(selectNextReadyTask(persistence.getTasks(graphId()))?.id).toBe(taskId('task-a'));
  });

  it('accepts deterministic diamond and multi-level DAGs', () => {
    const values = ['task-a', 'task-b', 'task-c', 'task-d'].map((id) => task(id));
    const diamond = [dependency('task-a', 'task-b'), dependency('task-a', 'task-c'),
      dependency('task-b', 'task-d'), dependency('task-c', 'task-d')];
    expect(validateTaskGraph(revision(), values.reverse(), diamond.reverse()).topologicalTaskIds)
      .toEqual(['task-a', 'task-b', 'task-c', 'task-d']);
    expect(validateTaskGraph(revision(), values, [dependency('task-a', 'task-b'), dependency('task-b', 'task-c')])
      .topologicalTaskIds).toEqual(['task-a', 'task-b', 'task-c', 'task-d']);
  });

  it.each([
    ['unknown predecessor', [task('task-a')], [dependency('missing', 'task-a')], 'UNKNOWN_PREDECESSOR_TASK'],
    ['unknown successor', [task('task-a')], [dependency('task-a', 'missing')], 'UNKNOWN_SUCCESSOR_TASK'],
    ['self dependency', [task('task-a')], [dependency('task-a', 'task-a')], 'SELF_DEPENDENCY'],
    ['duplicate dependency', [task('task-a'), task('task-b')],
      [dependency('task-a', 'task-b'), dependency('task-a', 'task-b')], 'DUPLICATE_DEPENDENCY'],
    ['conflicting dependency', [task('task-a'), task('task-b')],
      [dependency('task-a', 'task-b'), dependency('task-a', 'task-b', 'completion')], 'CONFLICTING_DEPENDENCY'],
    ['predicate missing data', [task('task-a'), task('task-b')],
      [dependency('task-a', 'task-b', 'predicate')], 'INVALID_PREDICATE_DEPENDENCY'],
    ['predicate on success', [task('task-a'), task('task-b')],
      [dependency('task-a', 'task-b', 'success', { equals: true })], 'INVALID_PREDICATE_DEPENDENCY'],
  ])('rejects %s before persistence', (_name, tasks, edges, code) => {
    expect(() => validateTaskGraph(revision(), tasks as Task[], edges as TaskDependency[]))
      .toThrow(expect.objectContaining({ code }));
  });

  it('rejects two-node and multi-node cycles', () => {
    const values = ['task-a', 'task-b', 'task-c'].map((id) => task(id));
    expect(() => validateTaskGraph(revision(), values, [dependency('task-a', 'task-b'), dependency('task-b', 'task-a')]))
      .toThrow(expect.objectContaining({ code: 'CYCLIC_TASK_GRAPH' }));
    expect(() => validateTaskGraph(revision(), values, [dependency('task-a', 'task-b'), dependency('task-b', 'task-c'),
      dependency('task-c', 'task-a')])).toThrow(expect.objectContaining({ code: 'CYCLIC_TASK_GRAPH' }));
  });

  it('reports deterministic unresolved IDs without claiming exact cycle membership', () => {
    const values = [task('task-c'), task('task-b'), task('task-a')];
    const edges = [dependency('task-b', 'task-c'), dependency('task-b', 'task-a'), dependency('task-a', 'task-b')];
    const unresolved = (tasks: Task[], dependencies: TaskDependency[]) => {
      try {
        validateTaskGraph(revision(), tasks, dependencies);
        throw new Error('Expected cyclic graph rejection');
      } catch (error) {
        expect(error).toBeInstanceOf(TaskGraphValidationError);
        return (error as TaskGraphValidationError).unresolvedTaskIds;
      }
    };
    expect(unresolved(values, edges)).toEqual([taskId('task-a'), taskId('task-b'), taskId('task-c')]);
    expect(unresolved([...values].reverse(), [...edges].reverse())).toEqual([taskId('task-a'), taskId('task-b'), taskId('task-c')]);
  });

  it('inspects ready, pending, predicate, completion, and blocked dependency semantics deterministically', () => {
    admit([
      task('root-success', 'succeeded'), task('root-failed', 'failed'), task('ready-task'), task('waiting-task'),
      task('predicate-task'), task('completion-task'), task('blocked-task'),
    ], [
      dependency('waiting-task', 'ready-task'), dependency('root-success', 'waiting-task'),
      dependency('root-success', 'predicate-task', 'predicate', { key: 'value' }),
      dependency('root-failed', 'completion-task', 'completion'), dependency('root-failed', 'blocked-task'),
    ]);
    const snapshot = inspectQueue(persistence, graphId());
    expect(snapshot.map((entry) => entry.taskId)).toEqual([
      taskId('blocked-task'), taskId('completion-task'), taskId('predicate-task'), taskId('ready-task'),
      taskId('root-failed'), taskId('root-success'), taskId('waiting-task'),
    ]);
    expect(snapshot.find((entry) => entry.taskId === taskId('completion-task'))).toMatchObject({ reason: 'ready', blockingTaskIds: [] });
    expect(snapshot.find((entry) => entry.taskId === taskId('predicate-task'))).toMatchObject({
      reason: 'predicate_not_supported', blockingTaskIds: [taskId('root-success')],
    });
    expect(snapshot.find((entry) => entry.taskId === taskId('blocked-task'))).toMatchObject({
      reason: 'required_dependency_failed', blockingTaskIds: [taskId('root-failed')],
    });
    expect(snapshot.find((entry) => entry.taskId === taskId('ready-task'))).toMatchObject({
      reason: 'dependencies_pending', blockingTaskIds: [taskId('waiting-task')],
    });
  });

  it('reports eligibility, dependency predecessor state, Attempt count, Failure, and terminal reason', () => {
    admit([task('task-a', 'ready'), task('task-b', 'failed')], [dependency('task-b', 'task-a', 'completion')]);
    persistence.createAttempt({ id: asIdentifier<'Attempt'>('attempt-b'), taskId: taskId('task-b'), attemptNumber: 1,
      status: 'failed', inputSnapshot: {}, result: {}, completedAt: NOW, createdAt: NOW }, event('task-b', 'attempt.failed'));
    persistence.createFailure({ id: asIdentifier<'Failure'>('failure-b'), taskId: taskId('task-b'), category: 'execution_defect',
      classification: 'permanent', code: 'FAILED', summary: 'Task failed', details: {}, retryable: false, createdAt: NOW },
      event('task-b', 'failure.recorded'));
    const snapshot = inspectQueue(persistence, graphId());
    expect(snapshot.find((entry) => entry.taskId === taskId('task-a'))).toMatchObject({
      schedulerEligible: true, dependencies: [{ predecessorTaskId: taskId('task-b'), predecessorStatus: 'failed', condition: 'completion' }],
    });
    expect(snapshot.find((entry) => entry.taskId === taskId('task-b'))).toMatchObject({
      attemptCount: 1, terminalReason: 'TEST_FAILURE', latestFailure: { classification: 'permanent', code: 'FAILED' },
    });
  });

  it.each([
    ['malformed JSON', "UPDATE tasks SET inputs_json = '{' WHERE id = 'task-a'", /Corrupt persisted JSON/],
    ['invalid enum', "UPDATE tasks SET status = 'unknown' WHERE id = 'task-a'", /Invalid Task status/],
    ['malformed timestamp', "UPDATE tasks SET created_at = 'not-a-date' WHERE id = 'task-a'", /Invalid task creation timestamp/],
  ])('fails explicitly on persisted %s without fallback', (_name, statement, expected) => {
    admit([task('task-a')]);
    persistence.close();
    const raw = new DatabaseSync(databasePath);
    raw.exec('PRAGMA ignore_check_constraints = ON');
    raw.exec(statement);
    raw.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    expect(() => persistence.getTasks(graphId())).toThrow(expected);
  });

  it('fails closed when persisted structure references a missing predecessor', () => {
    admit([task('task-a'), task('task-b')], [dependency('task-a', 'task-b')]);
    persistence.close();
    const raw = new DatabaseSync(databasePath);
    raw.exec('PRAGMA foreign_keys = OFF; DROP TRIGGER tasks_no_delete; DELETE FROM tasks WHERE id = \'task-a\'');
    raw.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    expect(() => inspectQueue(persistence, graphId())).toThrow(/Unknown predecessor Task: task-a/);
  });
});

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { asIdentifier, type Attempt, type AuditEventInput, type Failure, type Goal, type Task,
  type TaskGraphRevision } from '../src/architecture2/domain/index.js';
import { SqliteArchitecture2Persistence } from '../src/architecture2/persistence/index.js';
import { authorizeReplanning, createFailureDiagnosis, TaskStateMachine } from '../src/architecture2/workflow/index.js';

const NOW = '2026-08-14T23:30:00.000Z';

describe('Architecture 2 Phase 1Q governed replanning', () => {
  let directory: string;
  let path: string;
  let persistence: SqliteArchitecture2Persistence;
  let sequence: number;
  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'graci-phase1q-')); path = join(directory, 'replanning.sqlite');
    persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize(); sequence = 0;
  });
  afterEach(() => { persistence.close(); rmSync(directory, { recursive: true, force: true }); });

  function event(aggregateId: string, type: string): AuditEventInput {
    return { id: asIdentifier<'Event'>(`phase1q-event-${++sequence}`), aggregateType: 'task', aggregateId,
      eventType: type, eventVersion: 1, actor: 'phase1q-test', occurredAt: NOW, payload: {} };
  }

  function seed() {
    const goal: Goal = { id: asIdentifier<'Goal'>('phase1q-goal'), objective: 'Repair plan', constraints: {},
      priority: 'normal', privacyClass: 'internal', status: 'active', version: 1, createdAt: NOW, updatedAt: NOW };
    persistence.createGoal({ goal, criteria: [] }, event(goal.id, 'goal.created'));
    const graph: TaskGraphRevision = { id: asIdentifier<'TaskGraphRevision'>('phase1q-graph-1'), goalId: goal.id,
      revision: 1, createdAt: NOW };
    persistence.createTaskGraphRevision(graph, event(graph.id, 'graph.created'));
    const base = { goalId: goal.id, graphRevisionId: graph.id, inputs: {}, requiredCapabilities: ['test.execute'],
      privacyClass: 'internal' as const, priority: 'normal' as const, required: true, retryPolicy: { maxAttempts: 3 },
      verificationPlan: {}, version: 1, createdAt: NOW, updatedAt: NOW };
    const failedTask: Task = { ...base, id: asIdentifier<'Task'>('phase1q-failed'), title: 'Bad decomposition',
      objective: 'Impossible structural unit', status: 'planned' };
    const unfinished: Task = { ...base, id: asIdentifier<'Task'>('phase1q-unfinished'), title: 'Old unfinished work',
      objective: 'Old work', status: 'planned' };
    persistence.createTask(failedTask, event(failedTask.id, 'task.created'));
    persistence.createTask(unfinished, event(unfinished.id, 'task.created'));
    persistence.updateGoal({ ...goal, activeGraphRevisionId: graph.id, version: 2 }, 1, event(goal.id, 'goal.activated'));
    const machine = new TaskStateMachine();
    const ready = machine.prepare(failedTask, 'ready', NOW, { dependenciesSatisfied: true });
    persistence.updateTask(ready, 1, event(ready.id, 'task.ready'));
    const scheduled = machine.prepare(ready, 'scheduled', NOW); persistence.updateTask(scheduled, 2, event(ready.id, 'task.scheduled'));
    const attempt: Attempt = { id: asIdentifier<'Attempt'>('phase1q-attempt'), taskId: failedTask.id, attemptNumber: 1,
      status: 'running', inputSnapshot: { objective: failedTask.objective, inputs: {}, requiredCapabilities: ['test.execute'] },
      createdAt: NOW, startedAt: NOW };
    const running = machine.prepare(scheduled, 'running', NOW, { attempt });
    persistence.startAttempt(running, 3, attempt, [event(running.id, 'attempt.started')]);
    const terminalAttempt: Attempt = { ...attempt, status: 'failed', completedAt: NOW };
    const failure: Failure = { id: asIdentifier<'Failure'>('phase1q-failure'), taskId: failedTask.id,
      attemptId: attempt.id, category: 'execution_defect', classification: 'permanent',
      code: 'TASK_GRAPH_STRUCTURE_INVALID', summary: 'Task decomposition cannot execute safely', details: {},
      retryable: false, createdAt: NOW };
    const failed = machine.prepare(running, 'failed', NOW, { attempt: terminalAttempt, terminalReason: failure.code });
    const diagnosisEvent = event(failed.id, 'failure.diagnosed');
    const diagnosis = createFailureDiagnosis({ evidence: { task: failed, failure, attempts: [terminalAttempt],
      attempt: terminalAttempt }, eventId: diagnosisEvent.id, diagnosedAt: NOW, diagnosedBy: 'phase1q-test' });
    persistence.recordAttemptOutcome(failed, 4, terminalAttempt, failure,
      [event(failed.id, 'failure.recorded'), diagnosisEvent, event(failed.id, 'task.failed')], diagnosis);
    return { goal, graph, failedTask, unfinished, attempt: terminalAttempt, failure, diagnosis };
  }

  function replan(source: ReturnType<typeof seed>) {
    const revision: TaskGraphRevision = { id: asIdentifier<'TaskGraphRevision'>('phase1q-graph-2'),
      goalId: source.goal.id, revision: 2, rationale: 'Replace unsafe decomposition', createdAt: NOW };
    const replacement: Task = { ...source.unfinished, id: asIdentifier<'Task'>('phase1q-replacement'),
      graphRevisionId: revision.id, title: 'Safe replacement', objective: 'Replacement work', version: 1 };
    return authorizeReplanning(persistence, { id: asIdentifier<'ReplanningDecision'>('phase1q-decision'),
      diagnosisId: source.diagnosis.id, revision, tasks: [replacement], dependencies: [],
      replacements: [{ supersededTaskId: source.unfinished.id, replacementTaskIds: [replacement.id] }],
      reason: 'Trusted diagnosis requires a new decomposition', actor: 'phase1q-test', authorizedAt: NOW,
      eventIds: [event(source.goal.id, 'replan'), event(replacement.id, 'task.created'), event(source.unfinished.id, 'superseded')]
        .map((value) => value.id) });
  }

  it('atomically activates one revision, preserves history, supersedes unfinished work, and reconstructs lineage', () => {
    const source = seed(); expect(source.diagnosis.disposition).toBe('replanning_recommended');
    const decision = replan(source);
    expect(persistence.getGoal(source.goal.id)?.goal).toMatchObject({ activeGraphRevisionId: decision.replacementGraphRevisionId, version: 3 });
    expect(persistence.getTask(source.failedTask.id)?.status).toBe('failed');
    expect(persistence.getAttempts(source.failedTask.id)).toEqual([source.attempt]);
    expect(persistence.getTask(source.unfinished.id)?.status).toBe('superseded');
    expect(persistence.getTasks(decision.replacementGraphRevisionId)[0]?.status).toBe('planned');
    expect(persistence.getTaskGraphRevisions(source.goal.id)).toHaveLength(2);
    expect(() => replan(source)).not.toThrow();
    persistence.close(); persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    expect(persistence.getSchemaVersion()).toBe(15);
    expect(persistence.getReplanningDecision(decision.id)).toEqual(decision);
    expect(persistence.getTaskGraphRevisions(source.goal.id)).toHaveLength(2);
  });

  it('fails closed for stale authority and malformed replacement graphs', () => {
    const source = seed(); replan(source);
    expect(() => authorizeReplanning(persistence, { id: asIdentifier<'ReplanningDecision'>('conflict'),
      diagnosisId: source.diagnosis.id,
      revision: { id: asIdentifier<'TaskGraphRevision'>('other-graph'), goalId: source.goal.id, revision: 3, createdAt: NOW },
      tasks: [], dependencies: [], replacements: [], reason: 'conflict', actor: 'test', authorizedAt: NOW,
      eventIds: [event(source.goal.id, 'conflict')] .map((value) => value.id) })).toThrow(/conflict/);
  });
});

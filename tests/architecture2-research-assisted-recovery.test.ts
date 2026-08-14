import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { DatabaseSync } from 'node:sqlite';
import { asIdentifier, type Attempt, type AuditEventInput, type Failure, type Goal, type Task,
  type TaskGraphRevision } from '../src/architecture2/domain/index.js';
import { SqliteArchitecture2Persistence } from '../src/architecture2/persistence/index.js';
import { authorizeInputRevision, authorizeReplanning, createFailureDiagnosis, createResearchRequest,
  decideResearchEvidence, recordResearchEvidence, TaskStateMachine } from '../src/architecture2/workflow/index.js';

const NOW = '2026-08-14T23:59:00.000Z';

describe('Architecture 2 Phase 1S research-assisted recovery', () => {
  let directory: string;
  let path: string;
  let persistence: SqliteArchitecture2Persistence;
  let sequence = 0;

  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'graci-phase1s-'));
    path = join(directory, 'phase1s.sqlite');
    persistence = new SqliteArchitecture2Persistence({ databasePath: path });
    persistence.initialize(); sequence = 0;
  });
  afterEach(() => { persistence.close(); rmSync(directory, { recursive: true, force: true }); });

  function event(aggregateId: string, eventType: string): AuditEventInput {
    return { id: asIdentifier<'Event'>(`phase1s-event-${++sequence}`), aggregateType: 'task', aggregateId,
      eventType, eventVersion: 1, actor: 'phase1s-test', occurredAt: NOW, payload: {} };
  }

  function seed(kind: 'input' | 'replanning' = 'input', maxAttempts = 3) {
    const suffix = `${kind}-${sequence}`;
    const goal: Goal = { id: asIdentifier<'Goal'>(`phase1s-goal-${suffix}`), objective: 'Research-assisted recovery',
      constraints: {}, priority: 'normal', privacyClass: 'internal', status: 'active', version: 1,
      createdAt: NOW, updatedAt: NOW };
    persistence.createGoal({ goal, criteria: [] }, event(goal.id, 'goal.created'));
    const graph: TaskGraphRevision = { id: asIdentifier<'TaskGraphRevision'>(`phase1s-graph-${suffix}`),
      goalId: goal.id, revision: 1, createdAt: NOW };
    persistence.createTaskGraphRevision(graph, event(graph.id, 'graph.created'));
    const base = { goalId: goal.id, graphRevisionId: graph.id, inputs: { query: 'bad' },
      requiredCapabilities: ['test.execute'], privacyClass: 'internal' as const, priority: 'normal' as const,
      required: true, retryPolicy: { maxAttempts }, verificationPlan: {}, version: 1, createdAt: NOW, updatedAt: NOW };
    const task: Task = { ...base, id: asIdentifier<'Task'>(`phase1s-task-${suffix}`), title: 'Failed work',
      objective: 'Recover safely', status: 'planned' };
    const unfinished: Task = { ...base, id: asIdentifier<'Task'>(`phase1s-unfinished-${suffix}`), title: 'Unfinished',
      objective: 'Replace me', inputs: {}, status: 'planned' };
    persistence.createTask(task, event(task.id, 'task.created'));
    if (kind === 'replanning') persistence.createTask(unfinished, event(unfinished.id, 'task.created'));
    persistence.updateGoal({ ...goal, activeGraphRevisionId: graph.id, version: 2 }, 1, event(goal.id, 'goal.active'));
    const machine = new TaskStateMachine();
    const ready = machine.prepare(task, 'ready', NOW, { dependenciesSatisfied: true });
    persistence.updateTask(ready, 1, event(task.id, 'task.ready'));
    const scheduled = machine.prepare(ready, 'scheduled', NOW); persistence.updateTask(scheduled, 2, event(task.id, 'task.scheduled'));
    const attempt: Attempt = { id: asIdentifier<'Attempt'>(`phase1s-attempt-${suffix}`), taskId: task.id,
      attemptNumber: 1, status: 'running', inputSnapshot: { objective: task.objective, inputs: task.inputs,
        requiredCapabilities: task.requiredCapabilities }, createdAt: NOW, startedAt: NOW };
    const running = machine.prepare(scheduled, 'running', NOW, { attempt });
    persistence.startAttempt(running, 3, attempt, [event(task.id, 'attempt.started')]);
    const terminalAttempt: Attempt = { ...attempt, status: 'failed', completedAt: NOW };
    const failure: Failure = { id: asIdentifier<'Failure'>(`phase1s-failure-${suffix}`), taskId: task.id,
      attemptId: attempt.id, category: 'unknown', classification: 'permanent',
      code: kind === 'replanning' ? 'TASK_GRAPH_STRUCTURE_INVALID' : 'UNEXPLAINED_INPUT_FAILURE',
      summary: 'Trusted research is required', details: {}, retryable: false, createdAt: NOW };
    const failed = machine.prepare(running, 'failed', NOW, { attempt: terminalAttempt, terminalReason: failure.code });
    const diagnosisEvent = event(task.id, 'failure.diagnosed');
    const diagnosis = createFailureDiagnosis({ evidence: { task: failed, failure, attempts: [terminalAttempt],
      attempt: terminalAttempt }, eventId: diagnosisEvent.id, diagnosedAt: NOW, diagnosedBy: 'phase1s-test' });
    persistence.recordAttemptOutcome(failed, 4, terminalAttempt, failure,
      [event(task.id, 'failure.recorded'), diagnosisEvent, event(task.id, 'task.failed')], diagnosis);
    return { goal, graph, task, unfinished, attempt: terminalAttempt, failure, diagnosis };
  }

  function research(source: ReturnType<typeof seed>, decision: 'accepted' | 'rejected' | 'recorded' = 'accepted') {
    const request = createResearchRequest(persistence, { id: asIdentifier<'ResearchRequest'>(`request-${++sequence}`),
      diagnosisId: source.diagnosis.id, question: 'What exact fact supports a safe recovery?', purpose: 'Support recovery',
      requestedBy: 'phase1s-test', requestedAt: NOW, eventId: event(source.task.id, 'research.request').id });
    const evidence = recordResearchEvidence(persistence, { id: asIdentifier<'ResearchEvidence'>(`evidence-${++sequence}`),
      requestId: request.id, supplierId: 'trusted-reviewer', supplierType: 'human', suppliedAt: NOW,
      source: 'bounded-review', reference: 'finding', content: { supported: true }, recordedBy: 'phase1s-test',
      recordedAt: NOW, eventId: event(source.task.id, 'research.evidence').id });
    if (decision !== 'recorded') decideResearchEvidence(persistence, { id: asIdentifier<'ResearchDecision'>(`decision-${++sequence}`),
      evidenceId: evidence.id, decision, actor: 'phase1s-reviewer', reason: 'Final trusted review', decidedAt: NOW,
      eventId: event(source.task.id, 'research.decision').id });
    return { request, evidence };
  }

  function input(source: ReturnType<typeof seed>, evidenceId: ReturnType<typeof research>['evidence']['id']) {
    return authorizeInputRevision(persistence, { id: asIdentifier<'InputRevision'>(`input-revision-${source.task.id}`),
      diagnosisId: source.diagnosis.id, revisedInputs: { query: 'researched' }, actor: 'phase1s-test',
      authorizedAt: NOW, eventId: event(source.task.id, 'input-revision.authorized').id, researchEvidenceId: evidenceId });
  }

  function replan(source: ReturnType<typeof seed>, evidenceId: ReturnType<typeof research>['evidence']['id']) {
    const revision: TaskGraphRevision = { id: asIdentifier<'TaskGraphRevision'>(`replacement-${source.graph.id}`),
      goalId: source.goal.id, revision: 2, createdAt: NOW };
    const replacement: Task = { ...source.unfinished, id: asIdentifier<'Task'>(`replacement-${source.unfinished.id}`),
      graphRevisionId: revision.id, version: 1 };
    return authorizeReplanning(persistence, { id: asIdentifier<'ReplanningDecision'>(`replan-${source.goal.id}`),
      diagnosisId: source.diagnosis.id, revision, tasks: [replacement], dependencies: [],
      replacements: [{ supersededTaskId: source.unfinished.id, replacementTaskIds: [replacement.id] }],
      reason: 'Accepted research supports replacement', actor: 'phase1s-test', authorizedAt: NOW,
      eventIds: [event(source.goal.id, 'replan').id, event(replacement.id, 'task.created').id,
        event(source.unfinished.id, 'task.superseded').id], researchEvidenceId: evidenceId });
  }

  it('authorizes input revision from exact accepted evidence and durably inspects the immutable link', () => {
    const source = seed(); const citation = research(source); const revision = input(source, citation.evidence.id);
    expect(persistence.getTask(source.task.id)).toMatchObject({ status: 'ready', inputs: { query: 'researched' } });
    const link = persistence.getResearchRecoveryLinkByInputRevision(revision.id);
    expect(link).toMatchObject({ recoveryKind: 'input_revision', inputRevisionId: revision.id,
      requestId: citation.request.id, evidenceId: citation.evidence.id, diagnosisId: source.diagnosis.id });
    persistence.close(); persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    expect(persistence.getResearchRecoveryLinkByInputRevision(revision.id)).toEqual(link);
  });

  it('authorizes replanning from exact accepted evidence while retaining normal replacement gates', () => {
    const source = seed('replanning'); const citation = research(source); const decision = replan(source, citation.evidence.id);
    expect(persistence.getGoal(source.goal.id)?.goal.activeGraphRevisionId).toBe(decision.replacementGraphRevisionId);
    expect(persistence.getResearchRecoveryLinkByReplanningDecision(decision.id)).toMatchObject({
      recoveryKind: 'replanning', replanningDecisionId: decision.id, evidenceId: citation.evidence.id });
  });

  it('rejects merely recorded, rejected, and unrelated evidence and research alone mutates no workflow state', () => {
    const recordedSource = seed(); const before = persistence.getTask(recordedSource.task.id);
    const recorded = research(recordedSource, 'recorded');
    expect(persistence.getTask(recordedSource.task.id)).toEqual(before);
    expect(() => input(recordedSource, recorded.evidence.id)).toThrow(/accepted exact source authority/);
    const rejectedSource = seed(); const rejected = research(rejectedSource, 'rejected');
    expect(() => input(rejectedSource, rejected.evidence.id)).toThrow(/accepted exact source authority/);
    const unrelatedSource = seed(); const unrelated = research(unrelatedSource);
    expect(() => input(recordedSource, unrelated.evidence.id)).toThrow(/exact source authority/);
  });

  it('preserves Attempt-limit, approval, and unknown-outcome stop gates', () => {
    const exhausted = seed('input', 1); const exhaustedResearch = research(exhausted);
    expect(() => input(exhausted, exhaustedResearch.evidence.id)).toThrow(/limit/);
    const approval = seed(); const approvalResearch = research(approval);
    persistence.createApproval({ id: asIdentifier<'Approval'>(`approval-${++sequence}`), goalId: approval.goal.id,
      taskId: approval.task.id, attemptId: approval.attempt.id, action: 'revise_input', scope: {},
      actionDigest: 'a'.repeat(64), decision: 'requested', requestedAt: NOW }, event(approval.task.id, 'approval.requested'));
    expect(() => input(approval, approvalResearch.evidence.id)).toThrow(/approval/);
    expect(() => authorizeInputRevision(persistence, { id: asIdentifier<'InputRevision'>('unknown-stop'),
      diagnosisId: approval.diagnosis.id, revisedInputs: { query: 'x' }, actor: 'test', authorizedAt: NOW,
      eventId: event(approval.task.id, 'unknown').id })).toThrow(/ineligible/);
  });

  it('allows exact replay but rejects conflicting and cross-action evidence reuse', () => {
    const source = seed(); const citation = research(source); const revision = input(source, citation.evidence.id);
    expect(input(source, citation.evidence.id)).toEqual(revision);
    const other = seed('replanning');
    expect(() => replan(other, citation.evidence.id)).toThrow(/source authority|supports a recovery action/);
  });

  it('migrates populated schema 15 without fabricating support links', () => {
    const source = seed(); persistence.close();
    const database = new DatabaseSync(path);
    database.exec(`DROP TRIGGER memory_records_no_update; DROP TRIGGER memory_records_no_delete; DROP TABLE memory_records;
      DROP TRIGGER research_provider_executions_no_delete; DROP TRIGGER research_provider_executions_terminal_no_update;
      DROP TABLE research_provider_executions;
      DROP TRIGGER research_recovery_links_no_update; DROP TRIGGER research_recovery_links_no_delete;
      DROP TABLE research_recovery_links; DELETE FROM schema_migrations WHERE version>=16; PRAGMA user_version=15;`);
    database.close(); persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    expect(persistence.getSchemaVersion()).toBe(18);
    expect(persistence.getTask(source.task.id)).toBeDefined();
    expect(persistence.getResearchRecoveryLinkByInputRevision(asIdentifier<'InputRevision'>('absent'))).toBeUndefined();
  });

  it('fails closed when persisted support attribution is corrupt', () => {
    const source = seed(); const citation = research(source); const revision = input(source, citation.evidence.id);
    const unrelated = seed();
    persistence.close();
    const database = new DatabaseSync(path);
    database.exec('DROP TRIGGER research_recovery_links_no_update');
    database.prepare('UPDATE research_recovery_links SET task_id=? WHERE input_revision_id=?')
      .run(unrelated.task.id, revision.id);
    database.close(); persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    expect(() => persistence.getResearchRecoveryLinkByInputRevision(revision.id)).toThrow(/Corrupt persisted/);
  });
});

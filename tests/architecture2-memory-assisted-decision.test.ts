import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { DatabaseSync } from 'node:sqlite';
import { asIdentifier, type Attempt, type AuditEventInput, type Failure, type Goal, type GoalId, type MemoryId,
  type Task, type TaskGraphRevision } from '../src/architecture2/domain/index.js';
import { SqliteArchitecture2Persistence } from '../src/architecture2/persistence/index.js';
import { authorizeInputRevision, authorizeReplanning, createFailureDiagnosis, createResearchRequest,
  decideResearchEvidence, recordResearchEvidence, storeMemory, supersedeMemory, TaskStateMachine } from '../src/architecture2/workflow/index.js';

const NOW = '2026-08-15T08:00:00.000Z';
const LATER = '2026-08-15T09:00:00.000Z';

describe('Architecture 2 Phase 1V governed memory-assisted decision support', () => {
  let directory: string;
  let path: string;
  let persistence: SqliteArchitecture2Persistence;
  let sequence = 0;

  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'graci-phase1v-'));
    path = join(directory, 'phase1v.sqlite');
    persistence = new SqliteArchitecture2Persistence({ databasePath: path });
    persistence.initialize(); sequence = 0;
  });
  afterEach(() => { persistence.close(); rmSync(directory, { recursive: true, force: true }); });

  function event(aggregateId: string, eventType: string): AuditEventInput {
    return { id: asIdentifier<'Event'>(`phase1v-event-${++sequence}`), aggregateType: 'task', aggregateId,
      eventType, eventVersion: 1, actor: 'phase1v-test', occurredAt: NOW, payload: {} };
  }

  function memory(id: string, goalId: GoalId, overrides: Partial<Parameters<typeof storeMemory>[1]> = {}) {
    return storeMemory(persistence, { id: asIdentifier<'Memory'>(id), scope: 'goal', goalId,
      content: { fact: id }, sourceType: 'caller', sourceReference: `source:${id}`, createdBy: 'phase1v-test',
      createdAt: NOW, trustStatus: 'trusted', eventId: asIdentifier<'Event'>(`memory-event-${id}`), ...overrides });
  }

  function seed(kind: 'input' | 'replanning' | 'research' = 'input', maxAttempts = 3) {
    const suffix = `${kind}-${++sequence}`;
    const goal: Goal = { id: asIdentifier<'Goal'>(`g-${suffix}`), objective: 'Memory-assisted decision',
      constraints: {}, priority: 'normal', privacyClass: 'internal', status: 'active', version: 1,
      createdAt: NOW, updatedAt: NOW };
    persistence.createGoal({ goal, criteria: [] }, event(goal.id, 'goal.created'));
    const graph: TaskGraphRevision = { id: asIdentifier<'TaskGraphRevision'>(`graph-${suffix}`),
      goalId: goal.id, revision: 1, createdAt: NOW };
    persistence.createTaskGraphRevision(graph, event(graph.id, 'graph.created'));
    const base = { goalId: goal.id, graphRevisionId: graph.id, inputs: { query: 'bad' },
      requiredCapabilities: ['test.execute'], privacyClass: 'internal' as const, priority: 'normal' as const,
      required: true, retryPolicy: { maxAttempts }, verificationPlan: {}, version: 1, createdAt: NOW, updatedAt: NOW };
    const task: Task = { ...base, id: asIdentifier<'Task'>(`task-${suffix}`), title: 'Failed work',
      objective: 'Recover safely', status: 'planned' };
    const unfinished: Task = { ...base, id: asIdentifier<'Task'>(`unfinished-${suffix}`), title: 'Unfinished',
      objective: 'Replace me', inputs: {}, status: 'planned' };
    persistence.createTask(task, event(task.id, 'task.created'));
    if (kind === 'replanning') persistence.createTask(unfinished, event(unfinished.id, 'task.created'));
    persistence.updateGoal({ ...goal, activeGraphRevisionId: graph.id, version: 2 }, 1, event(goal.id, 'goal.active'));
    const machine = new TaskStateMachine();
    const ready = machine.prepare(task, 'ready', NOW, { dependenciesSatisfied: true });
    persistence.updateTask(ready, 1, event(task.id, 'task.ready'));
    const scheduled = machine.prepare(ready, 'scheduled', NOW); persistence.updateTask(scheduled, 2, event(task.id, 'task.scheduled'));
    const attempt: Attempt = { id: asIdentifier<'Attempt'>(`attempt-${suffix}`), taskId: task.id,
      attemptNumber: 1, status: 'running', inputSnapshot: { objective: task.objective, inputs: task.inputs,
        requiredCapabilities: task.requiredCapabilities }, createdAt: NOW, startedAt: NOW };
    const running = machine.prepare(scheduled, 'running', NOW, { attempt });
    persistence.startAttempt(running, 3, attempt, [event(task.id, 'attempt.started')]);
    const terminalAttempt: Attempt = { ...attempt, status: 'failed', completedAt: NOW };
    const failure: Failure = { id: asIdentifier<'Failure'>(`failure-${suffix}`), taskId: task.id,
      attemptId: attempt.id, category: kind === 'replanning' ? 'execution_defect'
        : kind === 'research' ? 'unknown' : 'invalid_input_or_precondition',
      classification: 'permanent', code: kind === 'replanning' ? 'TASK_GRAPH_STRUCTURE_INVALID'
        : kind === 'research' ? 'UNEXPLAINED_FAILURE' : 'INVALID_QUERY',
      summary: 'Durable memory is required', details: {}, retryable: false, createdAt: NOW };
    const failed = machine.prepare(running, 'failed', NOW, { attempt: terminalAttempt, terminalReason: failure.code });
    const diagnosisEvent = event(task.id, 'failure.diagnosed');
    const diagnosis = createFailureDiagnosis({ evidence: { task: failed, failure, attempts: [terminalAttempt],
      attempt: terminalAttempt }, eventId: diagnosisEvent.id, diagnosedAt: NOW, diagnosedBy: 'phase1v-test' });
    persistence.recordAttemptOutcome(failed, 4, terminalAttempt, failure,
      [event(task.id, 'failure.recorded'), diagnosisEvent, event(task.id, 'task.failed')], diagnosis);
    return { goal, graph, task, unfinished, attempt: terminalAttempt, failure, diagnosis };
  }

  function research(source: ReturnType<typeof seed>, decision: 'accepted' | 'rejected' = 'accepted') {
    const request = createResearchRequest(persistence, { id: asIdentifier<'ResearchRequest'>(`request-${++sequence}`),
      diagnosisId: source.diagnosis.id, question: 'What exact fact supports a safe recovery?', purpose: 'Support recovery',
      requestedBy: 'phase1v-test', requestedAt: NOW, eventId: event(source.task.id, 'research.request').id });
    const evidence = recordResearchEvidence(persistence, { id: asIdentifier<'ResearchEvidence'>(`evidence-${++sequence}`),
      requestId: request.id, supplierId: 'trusted-reviewer', supplierType: 'human', suppliedAt: NOW,
      source: 'bounded-review', reference: 'finding', content: { supported: true }, recordedBy: 'phase1v-test',
      recordedAt: NOW, eventId: event(source.task.id, 'research.evidence').id });
    if (decision === 'accepted') decideResearchEvidence(persistence, { id: asIdentifier<'ResearchDecision'>(`decision-${++sequence}`),
      evidenceId: evidence.id, decision: 'accepted', actor: 'phase1v-reviewer', reason: 'Final trusted review', decidedAt: NOW,
      eventId: event(source.task.id, 'research.decision').id });
    return { request, evidence };
  }

  function input(source: ReturnType<typeof seed>, memoryIds: readonly MemoryId[] = [], authorizedAt = NOW) {
    const inputEventId = asIdentifier<'Event'>(`input-revision-event-${++sequence}`);
    return authorizeInputRevision(persistence, { id: asIdentifier<'InputRevision'>(`input-revision-${source.task.id}`),
      diagnosisId: source.diagnosis.id, revisedInputs: { query: 'researched' }, actor: 'phase1v-test',
      authorizedAt, eventId: inputEventId, memoryIds });
  }

  function replan(source: ReturnType<typeof seed>, memoryIds: readonly MemoryId[] = []) {
    const revision: TaskGraphRevision = { id: asIdentifier<'TaskGraphRevision'>(`replacement-${source.graph.id}`),
      goalId: source.goal.id, revision: 2, createdAt: NOW };
    const replacement: Task = { ...source.unfinished, id: asIdentifier<'Task'>(`replacement-${source.unfinished.id}`),
      graphRevisionId: revision.id, version: 1 };
    return authorizeReplanning(persistence, { id: asIdentifier<'ReplanningDecision'>(`replan-${source.goal.id}`),
      diagnosisId: source.diagnosis.id, revision, tasks: [replacement], dependencies: [],
      replacements: [{ supersededTaskId: source.unfinished.id, replacementTaskIds: [replacement.id] }],
      reason: 'Durable memory supports replacement', actor: 'phase1v-test', authorizedAt: NOW,
      eventIds: [event(source.goal.id, 'replan').id, event(replacement.id, 'task.created').id,
        event(source.unfinished.id, 'task.superseded').id], memoryIds });
  }

  it('accepts a valid optional trusted memory citation on input revision and stores exact durable provenance', () => {
    const source = seed(); const citation = memory('citation', source.goal.id); const revision = input(source, [citation.id]);
    expect(persistence.getTask(source.task.id)).toMatchObject({ status: 'ready', inputs: { query: 'researched' } });
    const links = persistence.getMemoryDecisionLinksByInputRevision(revision.id);
    expect(links).toHaveLength(1);
    expect(links[0]).toMatchObject({ kind: 'input_revision', inputRevisionId: revision.id,
      memoryId: citation.id, goalId: source.goal.id, taskId: source.task.id });
    persistence.close(); persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    expect(persistence.getMemoryDecisionLinksByInputRevision(revision.id)).toEqual(links);
  });

  it('accepts a valid optional trusted memory citation on replanning', () => {
    const source = seed('replanning'); const citation = memory('replan-citation', source.goal.id); const decision = replan(source, [citation.id]);
    expect(persistence.getGoal(source.goal.id)?.goal.activeGraphRevisionId).toBe(decision.replacementGraphRevisionId);
    const links = persistence.getMemoryDecisionLinksByReplanningDecision(decision.id);
    expect(links).toHaveLength(1);
    expect(links[0]).toMatchObject({ kind: 'replanning', replanningDecisionId: decision.id, memoryId: citation.id });
  });

  it('accepts a valid decision with no memory citation and persists no linkage', () => {
    const source = seed(); const revision = input(source);
    expect(persistence.getMemoryDecisionLinksByInputRevision(revision.id)).toEqual([]);
    const sourceR = seed('replanning'); const decision = replan(sourceR);
    expect(persistence.getMemoryDecisionLinksByReplanningDecision(decision.id)).toEqual([]);
  });

  it('orders multiple citations deterministically independent of input order', () => {
    const source = seed();
    const a = memory('m-b', source.goal.id); const b = memory('m-a', source.goal.id); const c = memory('m-c', source.goal.id);
    const revision = input(source, [c.id, a.id, b.id]);
    const ids = persistence.getMemoryDecisionLinksByInputRevision(revision.id).map((item) => item.memoryId);
    expect(ids).toEqual(['m-a', 'm-b', 'm-c']);
    expect(input(source, [b.id, a.id, c.id])).toEqual(revision);
  });

  it('rejects duplicate memory ids within one citation set', () => {
    const source = seed(); const citation = memory('dupe', source.goal.id);
    expect(() => input(source, [citation.id, citation.id])).toThrow(/Duplicate memory citation/);
  });

  it('rejects memory cited out of the decision Goal scope', () => {
    const source = seed();
    const otherGoalId = asIdentifier<'Goal'>(`other-${source.goal.id}`);
    persistence.createGoal({ goal: { id: otherGoalId, objective: 'Unrelated goal', constraints: {},
      priority: 'normal', privacyClass: 'internal', status: 'active', version: 1, createdAt: NOW, updatedAt: NOW },
      criteria: [] }, event(otherGoalId, 'goal.created'));
    const otherGoal = memory('other-goal', otherGoalId);
    expect(() => input(source, [otherGoal.id])).toThrow(/not scoped to the decision Goal/);
  });

  it('rejects reusable memory whose durable explicit permission is absent', () => {
    const source = seed();
    expect(() => storeMemory(persistence, { id: asIdentifier<'Memory'>('no-permission-reusable'), scope: 'reusable',
      content: { fact: 'x' }, sourceType: 'caller', sourceReference: 'src', createdBy: 'phase1v-test',
      createdAt: NOW, trustStatus: 'trusted', eventId: asIdentifier<'Event'>('memory-event-no-permission') }))
      .toThrow(/reusable permission/);
    const missing = asIdentifier<'Memory'>('never-stored');
    expect(() => input(source, [missing])).toThrow(/not found/);
  });

  it('accepts reusable memory only when it carries durable explicit permission', () => {
    const source = seed();
    const permitted = storeMemory(persistence, { id: asIdentifier<'Memory'>('permitted-reusable'), scope: 'reusable',
      content: { fact: 'reusable' }, sourceType: 'caller', sourceReference: 'src', createdBy: 'phase1v-test',
      createdAt: NOW, trustStatus: 'trusted', reusablePermission: 'Product Owner permits reuse', eventId: asIdentifier<'Event'>('memory-event-permitted') });
    const revision = input(source, [permitted.id]);
    expect(persistence.getMemoryDecisionLinksByInputRevision(revision.id).map((item) => item.memoryId))
      .toEqual([permitted.id]);
  });

  it('rejects superseded memory at citation time', () => {
    const source = seed();
    const prior = memory('superseded-prior', source.goal.id);
    supersedeMemory(persistence, { ...prior, id: asIdentifier<'Memory'>('superseded-replacement'),
      eventId: asIdentifier<'Event'>('memory-event-superseded-replacement'), createdAt: LATER,
      expectedCurrentId: prior.id, supersessionEventId: asIdentifier<'Event'>('memory-event-superseded-supersession') });
    expect(() => input(source, [prior.id])).toThrow(/superseded/);
  });

  it('rejects expired memory at citation time', () => {
    const source = seed();
    const expired = memory('expired', source.goal.id, { validUntil: '2026-08-15T08:30:00.000Z' });
    expect(() => input(source, [expired.id], LATER)).toThrow(/expired/);
  });

  it('enforces trust-status: only trusted memory may be cited', () => {
    const source = seed();
    const untrusted = memory('untrusted', source.goal.id, { trustStatus: 'untrusted' });
    expect(() => input(source, [untrusted.id])).toThrow(/must be trusted/);
    const disputed = memory('disputed', source.goal.id, { trustStatus: 'disputed' });
    expect(() => input(source, [disputed.id])).toThrow(/must be trusted/);
  });

  it('commits the decision and provenance atomically and rolls back together on failure', () => {
    const source = seed();
    const before = persistence.getTask(source.task.id);
    expect(() => input(source, [asIdentifier<'Memory'>('missing-memory')])).toThrow(/not found/);
    expect(persistence.getTask(source.task.id)).toEqual(before);
    expect(persistence.getInputRevisionByDiagnosis(source.diagnosis.id)).toBeUndefined();
  });

  it('reconstructs exact provenance across close/reopen', () => {
    const source = seed(); const citation = memory('reopen', source.goal.id); const revision = input(source, [citation.id]);
    persistence.close(); persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    const links = persistence.getMemoryDecisionLinksByInputRevision(revision.id);
    expect(links).toHaveLength(1);
    expect(links[0].memoryId).toBe(citation.id);
  });

  it('later supersession does not alter historical provenance', () => {
    const source = seed();
    const cited = memory('historical', source.goal.id);
    const revision = input(source, [cited.id]);
    supersedeMemory(persistence, { ...cited, id: asIdentifier<'Memory'>('historical-successor'),
      eventId: asIdentifier<'Event'>('memory-event-historical-successor'), content: { fact: 'new' }, createdAt: LATER,
      expectedCurrentId: cited.id, supersessionEventId: asIdentifier<'Event'>('memory-event-historical-supersession') });
    const links = persistence.getMemoryDecisionLinksByInputRevision(revision.id);
    expect(links.map((item) => item.memoryId)).toEqual([cited.id]);
  });

  it('memory citation does not alter required authorization disposition', () => {
    const source = seed(); const citation = memory('disposition', source.goal.id);
    const revision = input(source, [citation.id]);
    const diagnosis = persistence.getFailureDiagnosisById(source.diagnosis.id);
    expect(diagnosis?.disposition).toBe('input_revision_required');
    expect(() => input(source, [citation.id, asIdentifier<'Memory'>('extra')])).toThrow(/authority conflict/);
  });

  it('coexists with a valid Phase 1S research citation, both independently inspectable', () => {
    const source = seed('research'); const citation = memory('coexist', source.goal.id); const res = research(source);
    const revision = authorizeInputRevision(persistence, { id: asIdentifier<'InputRevision'>(`input-${source.task.id}`),
      diagnosisId: source.diagnosis.id, revisedInputs: { query: 'researched' }, actor: 'phase1v-test',
      authorizedAt: NOW, eventId: event(source.task.id, 'input-revision.authorized').id,
      researchEvidenceId: res.evidence.id, memoryIds: [citation.id] });
    expect(persistence.getResearchRecoveryLinkByInputRevision(revision.id)?.evidenceId).toBe(res.evidence.id);
    expect(persistence.getMemoryDecisionLinksByInputRevision(revision.id).map((item) => item.memoryId))
      .toEqual([citation.id]);
  });

  it('memory cannot substitute for required Phase 1S research authority', () => {
    const source = seed(); const citation = memory('not-research', source.goal.id);
    const revision = input(source, [citation.id]);
    expect(persistence.getResearchRecoveryLinkByInputRevision(revision.id)).toBeUndefined();
    const sourceR = seed('replanning'); const citationR = memory('not-research-r', sourceR.goal.id);
    const decision = replan(sourceR, [citationR.id]);
    expect(persistence.getResearchRecoveryLinkByReplanningDecision(decision.id)).toBeUndefined();
  });

  it('migrates populated schema 18 without fabricating memory citations', () => {
    const source = seed(); const citation = memory('pre-migrate', source.goal.id);
    const revision = input(source, [citation.id]);
    persistence.close();
    const database = new DatabaseSync(path);
    database.exec(`DROP TRIGGER memory_decision_links_no_update; DROP TRIGGER memory_decision_links_no_delete;
      DROP TABLE memory_decision_links;
      DELETE FROM schema_migrations WHERE version>=19; PRAGMA user_version=18;`);
    database.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    expect(persistence.getSchemaVersion()).toBe(19);
    expect(persistence.getTask(source.task.id)).toBeDefined();
    expect(persistence.getMemoryDecisionLinksByInputRevision(revision.id)).toEqual([]);
  });
});

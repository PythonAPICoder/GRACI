import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { DatabaseSync } from 'node:sqlite';
import { asIdentifier, type Attempt, type AuditEventInput, type Failure, type Goal, type Task,
  type TaskGraphRevision } from '../src/architecture2/domain/index.js';
import { SqliteArchitecture2Persistence } from '../src/architecture2/persistence/index.js';
import { createFailureDiagnosis, createResearchRequest, decideResearchEvidence, recordResearchEvidence,
  TaskStateMachine } from '../src/architecture2/workflow/index.js';

const NOW = '2026-08-14T23:50:00.000Z';

describe('Architecture 2 Phase 1R governed research', () => {
  let directory: string;
  let path: string;
  let persistence: SqliteArchitecture2Persistence;
  let sequence: number;

  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'graci-phase1r-'));
    path = join(directory, 'research.sqlite');
    persistence = new SqliteArchitecture2Persistence({ databasePath: path });
    persistence.initialize();
    sequence = 0;
  });
  afterEach(() => { persistence.close(); rmSync(directory, { recursive: true, force: true }); });

  function eventId() { return asIdentifier<'Event'>(`phase1r-event-${++sequence}`); }
  function event(aggregateId: string, type: string): AuditEventInput {
    return { id: eventId(), aggregateType: 'task', aggregateId, eventType: type, eventVersion: 1,
      actor: 'phase1r-test', occurredAt: NOW, payload: {} };
  }

  function seed(category: Failure['category'] = 'unknown') {
    const goal: Goal = { id: asIdentifier<'Goal'>('phase1r-goal'), objective: 'Resolve an unknown defect', constraints: {},
      priority: 'normal', privacyClass: 'internal', status: 'active', version: 1, createdAt: NOW, updatedAt: NOW };
    persistence.createGoal({ goal, criteria: [] }, event(goal.id, 'goal.created'));
    const graph: TaskGraphRevision = { id: asIdentifier<'TaskGraphRevision'>('phase1r-graph'), goalId: goal.id,
      revision: 1, createdAt: NOW };
    persistence.createTaskGraphRevision(graph, event(graph.id, 'graph.created'));
    const task: Task = { id: asIdentifier<'Task'>('phase1r-task'), goalId: goal.id, graphRevisionId: graph.id,
      title: 'Diagnose', objective: 'Resolve exact failure', inputs: {}, requiredCapabilities: ['test.execute'],
      privacyClass: 'internal', priority: 'normal', status: 'planned', required: true, retryPolicy: { maxAttempts: 3 },
      verificationPlan: {}, version: 1, createdAt: NOW, updatedAt: NOW };
    persistence.createTask(task, event(task.id, 'task.created'));
    persistence.updateGoal({ ...goal, activeGraphRevisionId: graph.id, version: 2 }, 1, event(goal.id, 'goal.active'));
    const machine = new TaskStateMachine();
    const ready = machine.prepare(task, 'ready', NOW, { dependenciesSatisfied: true });
    persistence.updateTask(ready, 1, event(task.id, 'task.ready'));
    const scheduled = machine.prepare(ready, 'scheduled', NOW); persistence.updateTask(scheduled, 2, event(task.id, 'task.scheduled'));
    const attempt: Attempt = { id: asIdentifier<'Attempt'>('phase1r-attempt'), taskId: task.id, attemptNumber: 1,
      status: 'running', inputSnapshot: { objective: task.objective, inputs: {}, requiredCapabilities: task.requiredCapabilities },
      createdAt: NOW, startedAt: NOW };
    const running = machine.prepare(scheduled, 'running', NOW, { attempt });
    persistence.startAttempt(running, 3, attempt, [event(task.id, 'attempt.started')]);
    const terminalAttempt: Attempt = { ...attempt, status: category === 'external_outcome_indeterminate' ? 'indeterminate' : 'failed', completedAt: NOW };
    const failure: Failure = { id: asIdentifier<'Failure'>('phase1r-failure'), taskId: task.id, attemptId: attempt.id,
      category, classification: category === 'external_outcome_indeterminate' ? 'external_outcome_indeterminate' : 'permanent',
      code: category === 'unknown' ? 'UNEXPLAINED_FAILURE' : 'OUTCOME_UNKNOWN', summary: 'Needs trusted investigation',
      details: {}, retryable: false, createdAt: NOW };
    const failed = machine.prepare(running, 'failed', NOW, { attempt: terminalAttempt, terminalReason: failure.code });
    const diagnosisEvent = event(task.id, 'failure.diagnosed');
    const diagnosis = createFailureDiagnosis({ evidence: { task: failed, failure, attempts: [terminalAttempt], attempt: terminalAttempt },
      eventId: diagnosisEvent.id, diagnosedAt: NOW, diagnosedBy: 'phase1r-test' });
    persistence.recordAttemptOutcome(failed, 4, terminalAttempt, failure,
      [event(task.id, 'failure.recorded'), diagnosisEvent, event(task.id, 'task.failed')], diagnosis);
    return { goal, task, attempt: terminalAttempt, failure, diagnosis };
  }

  function request(source: ReturnType<typeof seed>) {
    return createResearchRequest(persistence, { id: asIdentifier<'ResearchRequest'>('phase1r-request'),
      diagnosisId: source.diagnosis.id, question: 'What authoritative technical fact explains this exact failure?',
      purpose: 'Identify information needed to resolve the persisted diagnosis safely', requestedBy: 'phase1r-test',
      requestedAt: NOW, eventId: eventId() });
  }

  it('derives lifecycle from immutable evidence and one separate accepted decision across restart', () => {
    const source = seed(); expect(source.diagnosis).toMatchObject({ disposition: 'research_recommended', outcomeCertainty: 'proven_unsuccessful' });
    const before = persistence.getTask(source.task.id); const created = request(source);
    expect(persistence.inspectResearchRequest(created.id)?.lifecycle).toBe('requested');
    const evidence = recordResearchEvidence(persistence, { id: asIdentifier<'ResearchEvidence'>('phase1r-evidence'),
      requestId: created.id, supplierId: 'vendor-docs', supplierType: 'documentation', suppliedAt: NOW,
      source: 'local-qualified-documentation', reference: 'section-4', content: { finding: 'bounded information' },
      integrity: { sha256: 'a'.repeat(64) }, recordedBy: 'phase1r-test', recordedAt: NOW, eventId: eventId() });
    expect(persistence.inspectResearchRequest(created.id)?.lifecycle).toBe('evidence_recorded');
    expect(persistence.getAcceptedResearchEvidence(created.id)).toEqual([]);
    const decision = decideResearchEvidence(persistence, { id: asIdentifier<'ResearchDecision'>('phase1r-decision'),
      evidenceId: evidence.id, decision: 'accepted', actor: 'phase1r-reviewer', reason: 'Relevant and attributable',
      decidedAt: NOW, eventId: eventId() });
    expect(persistence.getAcceptedResearchEvidence(created.id)).toEqual([evidence]);
    expect(persistence.getTask(source.task.id)).toEqual(before);
    persistence.close(); persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    expect(persistence.getSchemaVersion()).toBe(15);
    expect(persistence.inspectResearchRequest(created.id)).toMatchObject({ lifecycle: 'accepted',
      evidence: [{ evidence, decision }] });
  });

  it('fails closed for unbounded/malformed payloads and Phase 1N unknown outcomes', () => {
    const indeterminate = seed('external_outcome_indeterminate');
    expect(indeterminate.diagnosis).toMatchObject({ disposition: 'reconciliation_required', outcomeCertainty: 'indeterminate_external_outcome' });
    expect(() => request(indeterminate)).toThrow(/authority/);
  });

  it('enforces bounded questions and finite acyclic plain-JSON evidence', () => {
    const source = seed();
    expect(() => createResearchRequest(persistence, { id: asIdentifier<'ResearchRequest'>('empty-question'),
      diagnosisId: source.diagnosis.id, question: ' ', purpose: 'purpose', requestedBy: 'test', requestedAt: NOW,
      eventId: eventId() })).toThrow(/bounds/);
    const created = request(source);
    const cyclic: Record<string, unknown> = {}; cyclic.self = cyclic;
    expect(() => recordResearchEvidence(persistence, { id: asIdentifier<'ResearchEvidence'>('cyclic-evidence'),
      requestId: created.id, supplierId: 'supplier', supplierType: 'human', suppliedAt: NOW, source: 'inspection',
      reference: 'finding', content: cyclic, recordedBy: 'test', recordedAt: NOW, eventId: eventId() })).toThrow(/cyclic/);
    expect(() => recordResearchEvidence(persistence, { id: asIdentifier<'ResearchEvidence'>('large-evidence'),
      requestId: created.id, supplierId: 'supplier', supplierType: 'human', suppliedAt: NOW, source: 'inspection',
      reference: 'finding', content: { data: 'x'.repeat(65536) }, recordedBy: 'test', recordedAt: NOW,
      eventId: eventId() })).toThrow(/bounds/);
  });

  it('allows equivalent decision idempotency and rejects conflicting final authority across connections', () => {
    const created = request(seed());
    const evidence = recordResearchEvidence(persistence, { id: asIdentifier<'ResearchEvidence'>('phase1r-evidence'),
      requestId: created.id, supplierId: 'reviewer', supplierType: 'human', suppliedAt: NOW, source: 'inspection',
      reference: 'finding-1', content: { fact: true }, recordedBy: 'phase1r-test', recordedAt: NOW, eventId: eventId() });
    const command = { id: asIdentifier<'ResearchDecision'>('phase1r-decision'), evidenceId: evidence.id,
      decision: 'rejected' as const, actor: 'phase1r-reviewer', reason: 'Insufficient corroboration', decidedAt: NOW, eventId: eventId() };
    expect(decideResearchEvidence(persistence, command)).toEqual(decideResearchEvidence(persistence, command));
    expect(persistence.inspectResearchRequest(created.id)?.lifecycle).toBe('rejected');
    const second = new SqliteArchitecture2Persistence({ databasePath: path }); second.initialize();
    expect(() => decideResearchEvidence(second, { ...command, id: asIdentifier<'ResearchDecision'>('phase1r-conflict'),
      decision: 'accepted', eventId: asIdentifier<'Event'>('phase1r-conflict-event') })).toThrow(/conflicting final decision/);
    second.close();
  });

  it('reports explicit reconstruction diagnostics for corrupt persisted research state', () => {
    const created = request(seed());
    persistence.close();
    const database = new DatabaseSync(path);
    database.exec('DROP TRIGGER research_requests_no_update');
    database.prepare('UPDATE research_requests SET requested_at=? WHERE id=?').run('not-a-time', created.id);
    database.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    expect(() => persistence.inspectResearchRequest(created.id)).toThrow(/Corrupt persisted Research Request/);
  });

  it('migrates populated schema 14 without fabricating research records', () => {
    const source = seed();
    persistence.close();
    const database = new DatabaseSync(path); database.exec(`
      DROP TRIGGER research_requests_no_update; DROP TRIGGER research_requests_no_delete;
      DROP TRIGGER research_evidence_no_update; DROP TRIGGER research_evidence_no_delete;
      DROP TRIGGER research_decisions_no_update; DROP TRIGGER research_decisions_no_delete;
      DROP TABLE research_decisions; DROP TABLE research_evidence; DROP TABLE research_requests;
      DROP INDEX idx_failures_research_authority; DROP INDEX idx_diagnoses_research_authority;
      DELETE FROM schema_migrations WHERE version=15; PRAGMA user_version=14;`); database.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    expect(persistence.getSchemaVersion()).toBe(15);
    expect(persistence.getTask(source.task.id)).toBeDefined();
    expect(persistence.getAcceptedResearchEvidence(asIdentifier<'ResearchRequest'>('absent-request'))).toEqual([]);
  });
});

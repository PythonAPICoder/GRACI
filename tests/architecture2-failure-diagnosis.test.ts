import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { DatabaseSync } from 'node:sqlite';
import {
  asIdentifier,
  type AuditEventInput,
  type ChangedConditionEvidence,
  type Failure,
  type Goal,
  type Task,
  type TaskGraphRevision,
} from '../src/architecture2/domain/index.js';
import { DeterministicTestProvider, type DeterministicBehavior } from '../src/architecture2/execution/index.js';
import { SqliteArchitecture2Persistence } from '../src/architecture2/persistence/index.js';
import { migrations } from '../src/architecture2/persistence/sqlite/migrations.js';
import { DeterministicVerifier } from '../src/architecture2/verification/index.js';
import { createFailureDiagnosis, diagnosePersistedFailure, MinimalOrchestrator, PHASE_1L_DIAGNOSIS_POLICY_ID,
  PHASE_1L_DIAGNOSIS_POLICY_VERSION } from '../src/architecture2/workflow/index.js';

const NOW = '2026-08-14T18:00:00.000Z';

describe('Architecture 2 Phase 1L failure diagnosis', () => {
  let directory: string;
  let databasePath: string;
  let persistence: SqliteArchitecture2Persistence;
  let sequence: number;

  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'graci-phase1l-'));
    databasePath = join(directory, 'diagnosis.sqlite');
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    sequence = 0;
  });

  afterEach(() => {
    persistence.close();
    rmSync(directory, { recursive: true, force: true });
  });

  function event(aggregateId: string, eventType: string, id?: string): AuditEventInput {
    sequence += 1;
    return { id: asIdentifier<'Event'>(id ?? `phase1l-event-${sequence}`), aggregateType: 'test', aggregateId,
      eventType, eventVersion: 1, actor: 'phase1l-test', occurredAt: NOW, payload: {} };
  }

  function seedTask(retryPolicy: Task['retryPolicy'] = {}): Task {
    const goal: Goal = { id: asIdentifier<'Goal'>('phase1l-goal'), objective: 'Diagnose failure', constraints: {},
      priority: 'normal', privacyClass: 'internal', status: 'active', version: 1, createdAt: NOW, updatedAt: NOW };
    persistence.createGoal({ goal, criteria: [] }, event(goal.id, 'goal.created'));
    const revision: TaskGraphRevision = { id: asIdentifier<'TaskGraphRevision'>('phase1l-graph'), goalId: goal.id,
      revision: 1, createdAt: NOW };
    persistence.createTaskGraphRevision(revision, event(revision.id, 'graph.created'));
    const task: Task = { id: asIdentifier<'Task'>('phase1l-task'), goalId: goal.id, graphRevisionId: revision.id,
      title: 'Diagnose', objective: 'Diagnose the controlled failure', inputs: {}, requiredCapabilities: ['test.execute'],
      privacyClass: 'internal', priority: 'normal', status: 'planned', required: true, retryPolicy,
      verificationPlan: {}, version: 1, createdAt: NOW, updatedAt: NOW };
    persistence.createTask(task, event(task.id, 'task.created'));
    return task;
  }

  function run(behaviors: readonly DeterministicBehavior[], retryPolicy: Task['retryPolicy'] = {}) {
    const task = seedTask(retryPolicy);
    let id = 0;
    const orchestrator = new MinimalOrchestrator(persistence,
      new DeterministicTestProvider(new Map([[task.id, behaviors]])), new DeterministicVerifier(), {
        now: () => NOW, nextId: (kind) => `${kind}-phase1l-${++id}`,
      });
    return { task, result: orchestrator.run(task.graphRevisionId) };
  }

  it('deterministically diagnoses transient retry and budget exhaustion', async () => {
    const { task, result } = run([
      { outcome: 'failure', classification: 'transient' },
      { outcome: 'failure', classification: 'transient' },
    ], { maxAttempts: 2 });
    await result;
    const diagnoses = persistence.getFailureDiagnoses(task.id);
    expect(diagnoses).toHaveLength(2);
    expect(diagnoses.map(({ cause, outcomeCertainty, retryable, disposition }) =>
      ({ cause, outcomeCertainty, retryable, disposition }))).toEqual([
      { cause: 'transient_infrastructure', outcomeCertainty: 'proven_unsuccessful', retryable: true,
        disposition: 'retry_same_path' },
      { cause: 'transient_infrastructure', outcomeCertainty: 'proven_unsuccessful', retryable: false,
        disposition: 'terminal_failure' },
    ]);
    expect(diagnoses[0]?.id).toMatch(/^diagnosis-[a-f0-9]{32}$/);
    const firstFailure = persistence.getFailure(diagnoses[0]!.failureId)!;
    expect(diagnosePersistedFailure(persistence, { failureId: firstFailure.id,
      eventId: asIdentifier<'Event'>('historical-repeat-event'), diagnosedAt: NOW, diagnosedBy: 'phase1l-test' }))
      .toEqual(diagnoses[0]);
  });

  it('keeps verification completion certainty separate from opt-in retryability', async () => {
    const { task, result } = run([
      { outcome: 'success', verificationPasses: false },
      { outcome: 'success', verificationPasses: true },
    ], { maxAttempts: 2, retryVerificationFailures: true });
    await result;
    expect(persistence.getFailureDiagnoses(task.id)[0]).toMatchObject({ cause: 'verification_failure',
      outcomeCertainty: 'proven_completed', retryable: true, disposition: 'retry_same_path' });
  });

  it('preserves approval semantics without creating a diagnosis-only Approval', async () => {
    const { task, result } = run([{ outcome: 'failure', classification: 'approval_required' }]);
    await result;
    expect(persistence.getFailureDiagnoses(task.id)[0]).toMatchObject({ cause: 'policy_or_approval',
      retryable: false, disposition: 'approval_required' });
    expect(persistence.getApprovals(task.id)).toHaveLength(1);
  });

  it('fails malformed required evidence closed with one non-executing disposition', () => {
    const task = seedTask();
    const failure: Failure = { id: asIdentifier<'Failure'>('malformed-failure'), taskId: task.id,
      category: 'verification_failure', classification: 'verification_failed', code: 'MISSING',
      summary: 'Missing Verification evidence', details: {}, retryable: true, createdAt: NOW };
    persistence.createFailure(failure, event(task.id, 'failure.recorded'));
    const diagnosisEvent = event(task.id, 'failure.diagnosed', 'malformed-diagnosis-event');
    const diagnosis = createFailureDiagnosis({ evidence: { task, failure, attempts: [] },
      eventId: diagnosisEvent.id, diagnosedAt: NOW, diagnosedBy: 'phase1l-test' });
    expect(diagnosis).toMatchObject({ cause: 'unknown', outcomeCertainty: 'insufficient_or_malformed_evidence',
      retryable: false, disposition: 'terminal_failure' });
    persistence.recordFailureDiagnosis(diagnosis, diagnosisEvent);
    expect(persistence.getFailureDiagnoses(task.id)).toEqual([diagnosis]);
  });

  it('fails contradictory category, classification, and Attempt evidence closed', () => {
    const task = seedTask({ maxAttempts: 3 });
    const attempt = { id: asIdentifier<'Attempt'>('contradictory-attempt'), taskId: task.id, attemptNumber: 1,
      status: 'succeeded' as const, inputSnapshot: {}, completedAt: NOW, createdAt: NOW };
    const failure: Failure = { id: asIdentifier<'Failure'>('contradictory-failure'), taskId: task.id,
      attemptId: attempt.id, category: 'execution_defect', classification: 'transient', code: 'CONTRADICTORY',
      summary: 'Contradictory evidence', details: {}, retryable: true, createdAt: NOW };
    expect(createFailureDiagnosis({ evidence: { task, failure, attempts: [attempt], attempt },
      eventId: asIdentifier<'Event'>('contradictory-event'), diagnosedAt: NOW, diagnosedBy: 'phase1l-test' }))
      .toMatchObject({ cause: 'unknown', outcomeCertainty: 'insufficient_or_malformed_evidence',
        retryable: false, disposition: 'terminal_failure' });
  });

  it('prevents duplicate authority and reconstructs immutable diagnosis exactly', () => {
    const task = seedTask();
    const failure: Failure = { id: asIdentifier<'Failure'>('standalone-failure'), taskId: task.id,
      category: 'unknown', classification: 'permanent', code: 'UNKNOWN', summary: 'Unknown valid failure',
      details: {}, retryable: false, createdAt: NOW };
    persistence.createFailure(failure, event(task.id, 'failure.recorded'));
    const diagnosisEvent = event(task.id, 'failure.diagnosed', 'standalone-diagnosis-event');
    const diagnosis = createFailureDiagnosis({ evidence: { task, failure, attempts: [] }, eventId: diagnosisEvent.id,
      diagnosedAt: NOW, diagnosedBy: 'phase1l-test' });
    expect(persistence.recordFailureDiagnosis(diagnosis, diagnosisEvent)).toEqual(diagnosis);
    expect(persistence.recordFailureDiagnosis(diagnosis, event(task.id, 'failure.diagnosed.repeat'))).toEqual(diagnosis);
    expect(() => persistence.recordFailureDiagnosis({ ...diagnosis, evidenceFingerprint: 'f'.repeat(64) },
      event(task.id, 'failure.diagnosed.conflict'))).toThrow(/authority conflict/);
    persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    expect(persistence.getFailureDiagnosis(failure.id, PHASE_1L_DIAGNOSIS_POLICY_ID,
      PHASE_1L_DIAGNOSIS_POLICY_VERSION)).toEqual(diagnosis);
    persistence.close();
    const direct = new DatabaseSync(databasePath);
    expect(() => direct.prepare(`UPDATE failure_diagnoses SET disposition = 'terminal_failure' WHERE id = ?`)
      .run(diagnosis.id)).toThrow(/immutable/);
    direct.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
  });

  it('persists bounded factual changed-condition evidence without authorizing recovery', () => {
    const task = seedTask();
    const failure: Failure = { id: asIdentifier<'Failure'>('changed-failure'), taskId: task.id,
      category: 'invalid_input_or_precondition', classification: 'permanent', code: 'INVALID_INPUT',
      summary: 'Input invalid', details: {}, retryable: true, createdAt: NOW };
    persistence.createFailure(failure, event(task.id, 'failure.recorded'));
    const diagnosisEvent = event(task.id, 'failure.diagnosed');
    const diagnosis = createFailureDiagnosis({ evidence: { task, failure, attempts: [] }, eventId: diagnosisEvent.id,
      diagnosedAt: NOW, diagnosedBy: 'phase1l-test' });
    persistence.recordFailureDiagnosis(diagnosis, diagnosisEvent);
    const condition: ChangedConditionEvidence = { id: asIdentifier<'ChangedConditionEvidence'>('condition-1'),
      diagnosisId: diagnosis.id, conditionType: 'input_revision', priorFactReference: 'artifact:input:v1',
      changedFactReference: 'artifact:input:v2', source: 'verified-artifact-revision', observedAt: NOW,
      eventId: asIdentifier<'Event'>('changed-condition-event') };
    persistence.recordChangedConditionEvidence(condition,
      { ...event(task.id, 'failure.changed-condition-recorded'), id: condition.eventId, aggregateType: 'task' });
    expect(persistence.getChangedConditionEvidence(diagnosis.id)).toEqual([condition]);
    expect(persistence.getFailureDiagnosis(failure.id, diagnosis.policyId, diagnosis.policyVersion)?.disposition)
      .toBe('input_revision_required');
    expect(() => persistence.recordChangedConditionEvidence({ ...condition,
      id: asIdentifier<'ChangedConditionEvidence'>('condition-secret'), source: 'token=do-not-store',
      eventId: asIdentifier<'Event'>('condition-secret-event') },
    { ...event(task.id, 'failure.changed-condition-recorded'), id: asIdentifier<'Event'>('condition-secret-event'),
      aggregateType: 'task' }))
      .toThrow(/factual reference/);
  });

  it('migrates populated schema 8 without fabricating historical diagnoses', () => {
    persistence.close();
    rmSync(databasePath, { force: true });
    const prior = new DatabaseSync(databasePath);
    prior.exec('PRAGMA foreign_keys = ON');
    prior.exec(`CREATE TABLE schema_migrations (
      version INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, applied_at TEXT NOT NULL
    ) STRICT`);
    for (const migration of migrations.slice(0, 8)) {
      migration.up(prior);
      prior.prepare('INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)')
        .run(migration.version, migration.name, NOW);
    }
    prior.exec('PRAGMA user_version = 8');
    prior.prepare(`INSERT INTO goals
      (id, objective, constraints_json, priority, privacy_class, status, version, created_at, updated_at)
      VALUES ('schema8-goal', 'preserve', '{}', 'normal', 'internal', 'active', 1, ?, ?)`).run(NOW, NOW);
    prior.prepare(`INSERT INTO task_graph_revisions (id, goal_id, revision, created_at)
      VALUES ('schema8-graph', 'schema8-goal', 1, ?)`).run(NOW);
    prior.prepare(`INSERT INTO tasks
      (id, goal_id, graph_revision_id, title, objective, inputs_json, required_capabilities_json, privacy_class,
       priority, status, required, retry_policy_json, verification_plan_json, terminal_reason, version,
       created_at, updated_at, completed_at)
      VALUES ('schema8-task', 'schema8-goal', 'schema8-graph', 'task', 'task', '{}', '[]', 'internal', 'normal',
       'failed', 1, '{}', '{}', 'SCHEMA8_FAILURE', 1, ?, ?, ?)`).run(NOW, NOW, NOW);
    prior.prepare(`INSERT INTO failures
      (id, task_id, category, classification, code, summary, details_json, retryable, created_at)
      VALUES ('schema8-failure', 'schema8-task', 'execution_defect', 'permanent', 'SCHEMA8_FAILURE',
       'Preserved failure', '{}', 0, ?)`).run(NOW);
    prior.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    expect(persistence.getSchemaVersion()).toBe(9);
    expect(persistence.getFailure(asIdentifier<'Failure'>('schema8-failure'))?.summary).toBe('Preserved failure');
    expect(persistence.getFailureDiagnoses(asIdentifier<'Task'>('schema8-task'))).toEqual([]);
  });
});

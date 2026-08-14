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
  type Node,
  type NodeInspectionObservation,
  type OfferingLocation,
  type ResourceLease,
  type ResourceSchedulingDecision,
  type WorkstationWorkloadEvaluation,
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
    expect(persistence.getSchemaVersion()).toBe(17);
    expect(persistence.getEvents()).toEqual([]);
  });

  it('atomically persists and reconstructs provider registry evidence', () => {
    const providerId = asIdentifier<'Provider'>('provider-ollama');
    const capabilityId = asIdentifier<'Capability'>('model.generate-text');
    const offeringId = asIdentifier<'ProviderOffering'>('offering-ollama-test');
    persistence.registerProvider({
      provider: { id: providerId, adapterType: 'ollama', adapterVersion: '1',
        configurationReference: 'config:ollama.test', createdAt: NOW },
      capabilities: [{ id: capabilityId, contractVersion: 1, description: 'Generate text',
        inputSchemaReference: 'schema:text-request:1', outputSchemaReference: 'schema:text-result:1', createdAt: NOW }],
      offerings: [{ id: offeringId, providerId, capabilityId, contractVersion: 1, modelIdentity: 'test-model',
        privacyDestinations: ['internal'], permissions: [], features: ['text'], supportedFormats: ['text/plain'],
        inputSchemaReference: 'schema:text-request:1', outputSchemaReference: 'schema:text-result:1',
        qualificationFingerprint: 'adapter:model:runtime', qualityLevel: 2, expectedLatencyMs: 100,
        maximumCost: 0, sideEffectClass: 'none', createdAt: NOW }],
    }, [event(providerId, 'provider.registered')]);
    persistence.recordQualification({ id: asIdentifier<'Qualification'>('qualification-1'), offeringId,
      status: 'qualified', level: 2, evidence: { suite: 'frozen-v1' }, qualifiedAt: NOW,
      expiresAt: '2026-09-13T20:00:00.000Z', triggerFingerprint: 'adapter:model:runtime' },
    event(offeringId, 'offering.qualified'));
    persistence.recordProviderHealth({ id: asIdentifier<'HealthObservation'>('health-1'), offeringId,
      status: 'healthy', evidence: { version: 'test' }, observedAt: NOW }, event(offeringId, 'offering.health-observed'));

    persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    expect(persistence.getProvider(providerId)?.adapterType).toBe('ollama');
    expect(persistence.getCapabilities().map((value) => value.id)).toEqual([capabilityId]);
    expect(persistence.getProviderOfferings(capabilityId)[0]?.id).toBe(offeringId);
    expect(persistence.getQualifications(offeringId)[0]?.status).toBe('qualified');
    expect(persistence.getProviderHealth(offeringId)[0]?.status).toBe('healthy');
    expect(persistence.getEvents()).toHaveLength(3);
  });

  it('rolls back provider registration when its audit event fails', () => {
    const providerId = asIdentifier<'Provider'>('provider-rollback');
    expect(() => persistence.registerProvider({ provider: { id: providerId, adapterType: 'test', adapterVersion: '1',
      configurationReference: 'config:test', createdAt: NOW }, capabilities: [], offerings: [] },
    [event(providerId, 'provider.registered', 'duplicate-event'), event(providerId, 'provider.registered', 'duplicate-event')])).toThrow();
    expect(persistence.getProvider(providerId)).toBeUndefined();
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
      expect(second.getSchemaVersion()).toBe(17);
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
    expect(persistence.getSchemaVersion()).toBe(17);
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

  it('migrates populated schema 4 and preserves attempts', () => {
    persistence.close();
    rmSync(databasePath, { force: true });
    const prior = new DatabaseSync(databasePath);
    prior.exec('PRAGMA foreign_keys = ON');
    prior.exec(`CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, applied_at TEXT NOT NULL) STRICT`);
    for (const migration of migrations.slice(0, 4)) {
      migration.up(prior);
      prior.prepare('INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)').run(migration.version, migration.name, NOW);
    }
    prior.exec('PRAGMA user_version = 4');
    prior.prepare(`INSERT INTO goals (id, objective, constraints_json, priority, privacy_class, status, version, created_at, updated_at)
      VALUES ('old-goal', 'old', '{}', 'normal', 'internal', 'active', 1, ?, ?)`).run(NOW, NOW);
    prior.prepare(`INSERT INTO task_graph_revisions (id, goal_id, revision, created_at) VALUES ('old-graph', 'old-goal', 1, ?)`).run(NOW);
    prior.prepare(`INSERT INTO tasks (id, goal_id, graph_revision_id, title, objective, inputs_json, required_capabilities_json,
      privacy_class, priority, status, required, retry_policy_json, verification_plan_json, version, created_at, updated_at)
      VALUES ('old-task', 'old-goal', 'old-graph', 'old', 'old', '{}', '[]', 'internal', 'normal', 'ready', 1, '{}', '{}', 1, ?, ?)`)
      .run(NOW, NOW);
    prior.prepare(`INSERT INTO attempts (id, task_id, attempt_number, status, input_snapshot_json, completed_at, created_at)
      VALUES ('old-attempt', 'old-task', 1, 'failed', '{}', ?, ?)`).run(NOW, NOW);
    prior.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    expect(persistence.getSchemaVersion()).toBe(17);
    expect(persistence.getAttempts(asIdentifier<'Task'>('old-task')).map((value) => value.id)).toEqual(['old-attempt']);
  });

  it('migrates populated schema 3 through Phase 1F without losing durable records', () => {
    persistence.close();
    rmSync(databasePath, { force: true });
    const prior = new DatabaseSync(databasePath);
    prior.exec('PRAGMA foreign_keys = ON');
    prior.exec(`CREATE TABLE schema_migrations (
      version INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, applied_at TEXT NOT NULL
    ) STRICT`);
    for (const migration of migrations.slice(0, 3)) {
      migration.up(prior);
      prior.prepare('INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)')
        .run(migration.version, migration.name, NOW);
    }
    prior.exec('PRAGMA user_version = 3');
    prior.prepare(`INSERT INTO goals
      (id, objective, constraints_json, priority, privacy_class, status, version, created_at, updated_at)
      VALUES ('schema3-goal', 'Preserve schema 3', '{"constraint":"retained"}', 'normal', 'internal', 'active', 2, ?, ?)`)
      .run(NOW, NOW);
    prior.prepare(`INSERT INTO task_graph_revisions (id, goal_id, revision, rationale, created_at)
      VALUES ('schema3-graph', 'schema3-goal', 1, 'Original schema 3 graph', ?)`).run(NOW);
    prior.prepare(`INSERT INTO tasks
      (id, goal_id, graph_revision_id, title, objective, inputs_json, required_capabilities_json,
       privacy_class, priority, status, required, retry_policy_json, verification_plan_json, version, created_at, updated_at)
      VALUES ('schema3-task', 'schema3-goal', 'schema3-graph', 'Schema 3 task', 'Preserve task',
       '{"input":"retained"}', '["model.generate-text"]', 'internal', 'normal', 'ready', 1,
       '{"maxAttempts":3}', '{"method":"deterministic"}', 3, ?, ?)`).run(NOW, NOW);
    prior.prepare(`INSERT INTO attempts
      (id, task_id, attempt_number, status, input_snapshot_json, result_json, completed_at, created_at)
      VALUES ('schema3-attempt', 'schema3-task', 1, 'failed', '{"input":"retained"}',
       '{"code":"ORIGINAL_FAILURE"}', ?, ?)`).run(NOW, NOW);
    const digest = 'a'.repeat(64);
    prior.prepare(`INSERT INTO legacy_import_operations
      (id, source_digest, source_reference, assessment_version, imported_record_count, imported_at)
      VALUES ('schema3-import', ?, 'legacy:schema3', 1, 1, ?)`).run(digest, NOW);
    prior.prepare(`INSERT INTO legacy_history_records
      (import_operation_id, source_digest, source_reference, source_section, source_key, legacy_status,
       payload_json, assessment_version, imported_at)
      VALUES ('schema3-import', ?, 'legacy:schema3', 'tasks', 'legacy-task', 'completed',
       '{"id":"legacy-task","status":"completed"}', 1, ?)`).run(digest, NOW);
    prior.close();

    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();

    expect(persistence.getSchemaVersion()).toBe(17);
    expect(persistence.getGoal(asIdentifier<'Goal'>('schema3-goal'))?.goal).toMatchObject({
      id: 'schema3-goal', objective: 'Preserve schema 3', constraints: { constraint: 'retained' }, version: 2,
    });
    expect(persistence.getTask(asIdentifier<'Task'>('schema3-task'))).toMatchObject({
      id: 'schema3-task', inputs: { input: 'retained' }, requiredCapabilities: ['model.generate-text'], version: 3,
    });
    expect(persistence.getAttempts(asIdentifier<'Task'>('schema3-task'))).toEqual([
      expect.objectContaining({ id: 'schema3-attempt', status: 'failed', result: { code: 'ORIGINAL_FAILURE' } }),
    ]);
    expect(persistence.getLegacyImport(digest)).toMatchObject({ id: 'schema3-import', importedRecordCount: 1 });
    expect(persistence.getLegacyHistory(digest)).toEqual([
      expect.objectContaining({ sourceKey: 'legacy-task', legacyStatus: 'completed',
        payload: { id: 'legacy-task', status: 'completed' } }),
    ]);

    expect(persistence.getCapabilities()).toEqual([]);
    expect(persistence.getProviderOfferings()).toEqual([]);
    const providerId = asIdentifier<'Provider'>('schema3-migrated-provider');
    const capabilityId = asIdentifier<'Capability'>('schema3-migrated-capability');
    const offeringId = asIdentifier<'ProviderOffering'>('schema3-migrated-offering');
    persistence.registerProvider({ provider: { id: providerId, adapterType: 'test', adapterVersion: '1',
      configurationReference: 'config:schema3-migration-test', createdAt: NOW }, capabilities: [{ id: capabilityId,
      contractVersion: 1, description: 'Migration provider structure', inputSchemaReference: 'in',
      outputSchemaReference: 'out', createdAt: NOW }], offerings: [{ id: offeringId, providerId, capabilityId,
      contractVersion: 1, privacyDestinations: ['internal'], permissions: [], features: [], supportedFormats: [],
      inputSchemaReference: 'in', outputSchemaReference: 'out', qualificationFingerprint: 'migration-test',
      qualityLevel: 1, expectedLatencyMs: 1, maximumCost: 0, sideEffectClass: 'none', createdAt: NOW }] },
    [event(providerId, 'provider.registered')]);
    expect(persistence.getProvider(providerId)?.adapterType).toBe('test');
    expect(persistence.getCapabilities().map((value) => value.id)).toEqual([capabilityId]);
    expect(persistence.getProviderOfferings(capabilityId).map((value) => value.id)).toEqual([offeringId]);
  });

  it('atomically registers, reopens, leases capacity, and releases', () => {
    createGraphWithTasks();
    const providerId = asIdentifier<'Provider'>('lease-provider');
    const capabilityId = asIdentifier<'Capability'>('lease-capability');
    const offeringId = asIdentifier<'ProviderOffering'>('lease-offering');
    persistence.registerProvider({ provider: { id: providerId, adapterType: 'test', adapterVersion: '1',
      configurationReference: 'config:test', createdAt: NOW }, capabilities: [{ id: capabilityId, contractVersion: 1,
      description: 'test', inputSchemaReference: 'in', outputSchemaReference: 'out', createdAt: NOW }], offerings: [{
      id: offeringId, providerId, capabilityId, contractVersion: 1, privacyDestinations: ['internal'], permissions: [],
      features: [], supportedFormats: [], inputSchemaReference: 'in', outputSchemaReference: 'out',
      qualificationFingerprint: 'test', qualityLevel: 1, expectedLatencyMs: 1, maximumCost: 0,
      sideEffectClass: 'none', createdAt: NOW }] }, [event(providerId, 'provider.registered')]);
    const node: Node = { id: asIdentifier<'Node'>('node-1'), name: 'Node 1', administrativeState: 'active',
      configurationReference: 'config:node-1', createdAt: NOW };
    const location: OfferingLocation = { id: asIdentifier<'OfferingLocation'>('location-1'), nodeId: node.id, offeringId,
      enabled: true, capacity: 2, privacyClasses: ['internal'], createdAt: NOW };
    persistence.registerNode(node, [location], [event(node.id, 'node.registered')]);
    persistence.recordNodeHealth({ id: asIdentifier<'NodeHealthObservation'>('node-health-1'), nodeId: node.id,
      status: 'healthy', observedAt: NOW }, event(node.id, 'node.health-observed'));
    persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    expect(persistence.getNodes()).toEqual([{ ...node, version: 1 }]);
    expect(persistence.getOfferingLocations(offeringId)).toEqual([location]);
    expect(persistence.getNodeHealth(node.id)[0]?.status).toBe('healthy');

    const decision = (id: string): ResourceSchedulingDecision => ({ request: { id: asIdentifier<'ResourceSchedulingDecision'>(id),
      offeringId, privacyClass: 'internal', requiredCapacity: 2, maximumHealthAgeMs: 60_000, requestedAt: NOW },
      candidates: [{ locationId: location.id, nodeId: node.id, eligible: true, rejectionReasons: [], availableCapacity: 2,
        healthObservedAt: NOW }], selectedLocationId: location.id, selectedNodeId: node.id, explanation: 'selected', decidedAt: NOW });
    const lease = (id: string, decisionId: ResourceSchedulingDecision['request']['id']): ResourceLease => ({
      id: asIdentifier<'ResourceLease'>(id), decisionId, offeringId, locationId: location.id, nodeId: node.id,
      capacity: 2, status: 'active', acquiredAt: NOW, expiresAt: '2026-08-12T21:00:00.000Z' });
    const firstDecision = decision('decision-1');
    const firstLease = lease('lease-1', firstDecision.request.id);
    const planned = persistence.getTask(asIdentifier<'Task'>('task-1'))!;
    const ready: Task = { ...planned, status: 'ready', version: 2, updatedAt: NOW };
    persistence.updateTask(ready, planned.version, event(ready.id, 'task.transitioned.ready'));
    const scheduled: Task = { ...ready, status: 'scheduled', version: 3, updatedAt: NOW };
    expect(persistence.scheduleTaskWithResource(scheduled, ready.version, firstDecision, firstLease,
      [event(firstDecision.request.id, 'resource.scheduled'), event(scheduled.id, 'task.transitioned.scheduled')])).toBe(true);
    expect(persistence.getTask(scheduled.id)?.status).toBe('scheduled');
    persistence.transitionNodeAdministrativeState(node.id, 1, 'active', 'draining', 'phase1a-test',
      'Stop new work while preserving the active lease', NOW, event(node.id, 'node.administrative-state-transitioned'));
    expect(persistence.getResourceLeases(location.id)).toEqual([firstLease]);
    const conflictDecision = decision('decision-2');
    expect(() => persistence.recordResourceSchedulingDecision(conflictDecision, lease('lease-2', conflictDecision.request.id),
      [event(conflictDecision.request.id, 'resource.scheduled')])).toThrow(/capacity conflict/);
    expect(persistence.getResourceSchedulingDecision(conflictDecision.request.id)).toBeUndefined();
    expect(persistence.getResourceLeases(location.id)).toEqual([firstLease]);
    const released: ResourceLease = { ...firstLease, status: 'released', releasedAt: '2026-08-12T20:30:00.000Z' };
    persistence.releaseResourceLease(released, event(firstLease.id, 'resource.released'));
    expect(persistence.getResourceLeases(location.id)).toEqual([released]);
    persistence.recordResourceSchedulingDecision(conflictDecision, lease('lease-2', conflictDecision.request.id),
      [event(conflictDecision.request.id, 'resource.scheduled')]);
    expect(persistence.getResourceSchedulingDecision(firstDecision.request.id)).toEqual(firstDecision);
    expect(persistence.getResourceLeases(location.id)).toHaveLength(2);
  });

  it('defers an atomic workflow resource admission without changing Task, lease, decision, or Events', () => {
    createGraphWithTasks();
    const providerId = asIdentifier<'Provider'>('defer-provider');
    const capabilityId = asIdentifier<'Capability'>('defer-capability');
    const offeringId = asIdentifier<'ProviderOffering'>('defer-offering');
    persistence.registerProvider({ provider: { id: providerId, adapterType: 'test', adapterVersion: '1',
      configurationReference: 'config:test', createdAt: NOW }, capabilities: [{ id: capabilityId, contractVersion: 1,
      description: 'test', inputSchemaReference: 'in', outputSchemaReference: 'out', createdAt: NOW }], offerings: [{
      id: offeringId, providerId, capabilityId, contractVersion: 1, privacyDestinations: ['internal'], permissions: [],
      features: [], supportedFormats: [], inputSchemaReference: 'in', outputSchemaReference: 'out',
      qualificationFingerprint: 'test', qualityLevel: 1, expectedLatencyMs: 1, maximumCost: 0,
      sideEffectClass: 'none', createdAt: NOW }] }, [event(providerId, 'provider.registered')]);
    const node: Node = { id: asIdentifier<'Node'>('defer-node'), name: 'Defer Node', administrativeState: 'active',
      configurationReference: 'config:defer', createdAt: NOW };
    const location: OfferingLocation = { id: asIdentifier<'OfferingLocation'>('defer-location'), nodeId: node.id,
      offeringId, enabled: true, capacity: 1, privacyClasses: ['internal'], createdAt: NOW };
    persistence.registerNode(node, [location], [event(node.id, 'node.registered')]);
    const activeDecisionId = asIdentifier<'ResourceSchedulingDecision'>('defer-active-decision');
    const activeDecision: ResourceSchedulingDecision = { request: { id: activeDecisionId, offeringId,
      privacyClass: 'internal', requiredCapacity: 1, maximumHealthAgeMs: 60_000, requestedAt: NOW }, candidates: [],
      selectedLocationId: location.id, selectedNodeId: node.id, explanation: 'selected', decidedAt: NOW };
    persistence.recordResourceSchedulingDecision(activeDecision, { id: asIdentifier<'ResourceLease'>('defer-active-lease'),
      decisionId: activeDecisionId, offeringId, locationId: location.id, nodeId: node.id, capacity: 1, status: 'active',
      acquiredAt: NOW, expiresAt: '2026-08-12T21:00:00.000Z' }, [event(activeDecisionId, 'resource.scheduled')]);
    const original = persistence.getTask(asIdentifier<'Task'>('task-1'))!;
    const ready: Task = { ...original, status: 'ready', version: 2, updatedAt: NOW };
    persistence.updateTask(ready, original.version, event(ready.id, 'task.ready'));
    const scheduled: Task = { ...ready, status: 'scheduled', version: 3, updatedAt: NOW };
    const deferredDecisionId = asIdentifier<'ResourceSchedulingDecision'>('defer-blocked-decision');
    const deferredDecision: ResourceSchedulingDecision = { ...activeDecision,
      request: { ...activeDecision.request, id: deferredDecisionId }, decidedAt: NOW };
    const beforeEvents = persistence.getEvents().length;
    expect(persistence.scheduleTaskWithResource(scheduled, ready.version, deferredDecision, {
      id: asIdentifier<'ResourceLease'>('defer-blocked-lease'), decisionId: deferredDecisionId, offeringId,
      locationId: location.id, nodeId: node.id, capacity: 1, status: 'active', acquiredAt: NOW,
      expiresAt: '2026-08-12T21:00:00.000Z' }, [event(deferredDecisionId, 'resource.scheduled')])).toBe(false);
    expect(persistence.getTask(ready.id)).toEqual(ready);
    expect(persistence.getResourceSchedulingDecision(deferredDecisionId)).toBeUndefined();
    expect(persistence.getResourceLeases()).toHaveLength(1);
    expect(persistence.getEvents()).toHaveLength(beforeEvents);
  });

  it('rolls back node registration when its event fails', () => {
    const node: Node = { id: asIdentifier<'Node'>('node-rollback'), name: 'Rollback', administrativeState: 'active',
      configurationReference: 'config:rollback', createdAt: NOW };
    expect(() => persistence.registerNode(node, [], [event(node.id, 'node.registered', 'same-node-event'),
      event(node.id, 'node.registered', 'same-node-event')])).toThrow();
    expect(persistence.getNodes()).toEqual([]);
  });

  it('migrates populated schema 5 with node version 1', () => {
    persistence.close();
    rmSync(databasePath, { force: true });
    const prior = new DatabaseSync(databasePath);
    prior.exec('PRAGMA foreign_keys = ON');
    prior.exec(`CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, applied_at TEXT NOT NULL) STRICT`);
    for (const migration of migrations.slice(0, 5)) {
      migration.up(prior);
      prior.prepare('INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)')
        .run(migration.version, migration.name, NOW);
    }
    prior.prepare(`INSERT INTO nodes (id, name, administrative_state, configuration_reference, created_at)
      VALUES ('old-node', 'Old Node', 'draining', 'config:old', ?)`).run(NOW);
    prior.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    expect(persistence.getSchemaVersion()).toBe(17);
    expect(persistence.getNodes()).toEqual([{ id: 'old-node', name: 'Old Node', administrativeState: 'draining',
      configurationReference: 'config:old', createdAt: NOW, version: 1 }]);
  });

  it('atomically records and reconstructs append-only node inspections', () => {
    const node: Node = { id: asIdentifier<'Node'>('inspection-node'), name: 'Inspection Node',
      administrativeState: 'active', configurationReference: 'config:inspection', createdAt: NOW };
    persistence.registerNode(node, [], [event(node.id, 'node.registered')]);
    const observation: NodeInspectionObservation = { id: asIdentifier<'NodeInspection'>('inspection-1'), nodeId: node.id,
      adapterId: 'ollama', adapterVersion: 1, health: { outcome: 'success', version: '0.11.4' },
      inventory: { outcome: 'success', items: [{ name: 'a-model', digest: 'bbb' }, { name: 'z-model' }] },
      inspectedAt: NOW };
    persistence.recordNodeInspection(observation, event(node.id, 'node.inspected'));
    persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    expect(persistence.getNodeInspections(node.id)).toEqual([observation]);

    const failed: NodeInspectionObservation = { ...observation,
      id: asIdentifier<'NodeInspection'>('inspection-rollback'), inspectedAt: '2026-08-12T20:01:00.000Z' };
    persistence.appendEvent(event('seed', 'seed.created', 'inspection-duplicate-event'));
    expect(() => persistence.recordNodeInspection(failed,
      event(node.id, 'node.inspected', 'inspection-duplicate-event'))).toThrow();
    expect(persistence.getNodeInspections(node.id)).toEqual([observation]);
  });

  it('supports every non-no-op administrative transition and rejects stale or invalid commands', () => {
    const first: Node = { id: asIdentifier<'Node'>('admin-node-1'), name: 'Admin 1', administrativeState: 'active',
      configurationReference: 'config:admin-1', createdAt: NOW };
    const second: Node = { ...first, id: asIdentifier<'Node'>('admin-node-2'), name: 'Admin 2',
      configurationReference: 'config:admin-2' };
    persistence.registerNode(first, [], [event(first.id, 'node.registered')]);
    persistence.registerNode(second, [], [event(second.id, 'node.registered')]);
    const transition = (nodeId: Node['id'], version: number, from: Node['administrativeState'],
      to: Node['administrativeState']) => persistence.transitionNodeAdministrativeState(nodeId, version, from, to,
      'administrator', `${from} to ${to}`, NOW,
      { ...event(nodeId, 'node.administrative-state-transitioned'), actor: 'administrator' });
    expect(transition(first.id, 1, 'active', 'draining').administrativeState).toBe('draining');
    expect(transition(first.id, 2, 'draining', 'disabled').administrativeState).toBe('disabled');
    expect(transition(first.id, 3, 'disabled', 'active').version).toBe(4);
    expect(transition(second.id, 1, 'active', 'disabled').administrativeState).toBe('disabled');
    expect(transition(second.id, 2, 'disabled', 'draining').administrativeState).toBe('draining');
    expect(transition(second.id, 3, 'draining', 'active').version).toBe(4);
    expect(() => transition(first.id, 1, 'active', 'disabled')).toThrow(/concurrency conflict/);
    expect(() => transition(first.id, 4, 'active', 'active')).toThrow(/no-op/);
    expect(() => persistence.transitionNodeAdministrativeState(first.id, 4, 'active', 'disabled', 'administrator',
      '   ', NOW, { ...event(first.id, 'node.admin'), actor: 'administrator' })).toThrow(/reason/);
    expect(() => transition(first.id, 4, 'invalid' as Node['administrativeState'], 'disabled')).toThrow(/Invalid/);
  });

  it('migrates populated schema 6 without changing node evidence', () => {
    persistence.close();
    rmSync(databasePath, { force: true });
    const prior = new DatabaseSync(databasePath);
    prior.exec('PRAGMA foreign_keys = ON');
    prior.exec(`CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, applied_at TEXT NOT NULL) STRICT`);
    for (const migration of migrations.slice(0, 6)) {
      migration.up(prior);
      prior.prepare('INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)')
        .run(migration.version, migration.name, NOW);
    }
    prior.prepare(`INSERT INTO nodes (id, name, administrative_state, configuration_reference, created_at, version)
      VALUES ('schema6-node', 'Schema 6 Node', 'draining', 'config:schema6', ?, 3)`).run(NOW);
    prior.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    expect(persistence.getSchemaVersion()).toBe(17);
    expect(persistence.getNodes()).toEqual([{ id: 'schema6-node', name: 'Schema 6 Node', administrativeState: 'draining',
      configurationReference: 'config:schema6', createdAt: NOW, version: 3 }]);
    expect(persistence.getWorkstationWorkloadEvaluations(asIdentifier<'Node'>('schema6-node'))).toEqual([]);
  });

  it('atomically records, deterministically reconstructs, and reopens workstation availability evidence', () => {
    const node: Node = { id: asIdentifier<'Node'>('availability-node'), name: 'Availability Node',
      administrativeState: 'active', configurationReference: 'config:availability', createdAt: NOW };
    persistence.registerNode(node, [], [event(node.id, 'node.registered')]);
    const later: WorkstationWorkloadEvaluation = {
      id: asIdentifier<'WorkstationWorkloadEvaluation'>('availability-z'), nodeId: node.id,
      ruleFingerprint: 'rules-v1', processBasenames: ['game.exe', 'modorganizer.exe'],
      matchedRuleIds: ['game', 'mod-organizer-2'], recommendation: 'recommend_draining',
      evaluatedAt: '2026-08-12T20:02:00.000Z',
    };
    const earlier: WorkstationWorkloadEvaluation = { ...later,
      id: asIdentifier<'WorkstationWorkloadEvaluation'>('availability-a'), processBasenames: [], matchedRuleIds: [],
      recommendation: 'recommend_active', evaluatedAt: '2026-08-12T20:01:00.000Z' };
    persistence.recordWorkstationWorkloadEvaluation(later, event(node.id, 'node.availability-evaluated'));
    persistence.recordWorkstationWorkloadEvaluation(earlier, event(node.id, 'node.availability-evaluated'));
    expect(persistence.getWorkstationWorkloadEvaluations(node.id)).toEqual([earlier, later]);
    persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    expect(persistence.getWorkstationWorkloadEvaluations(node.id)).toEqual([earlier, later]);
    expect(persistence.getNodes()).toEqual([{ ...node, version: 1 }]);
    expect(persistence.getResourceLeases()).toEqual([]);
  });

  it('rolls back workstation availability evidence when its Event fails', () => {
    const node: Node = { id: asIdentifier<'Node'>('availability-rollback-node'), name: 'Rollback Node',
      administrativeState: 'active', configurationReference: 'config:rollback', createdAt: NOW };
    persistence.registerNode(node, [], [event(node.id, 'node.registered')]);
    persistence.appendEvent(event('seed', 'seed.created', 'availability-duplicate-event'));
    const evaluation: WorkstationWorkloadEvaluation = {
      id: asIdentifier<'WorkstationWorkloadEvaluation'>('availability-rollback'), nodeId: node.id,
      ruleFingerprint: 'rules-v1', processBasenames: [], matchedRuleIds: [], recommendation: 'inconclusive', evaluatedAt: NOW,
    };
    expect(() => persistence.recordWorkstationWorkloadEvaluation(evaluation,
      event(node.id, 'node.availability-evaluated', 'availability-duplicate-event'))).toThrow();
    expect(persistence.getWorkstationWorkloadEvaluations(node.id)).toEqual([]);
    expect(persistence.getNodes()).toEqual([{ ...node, version: 1 }]);
    expect(persistence.getResourceLeases()).toEqual([]);
  });

  it('rejects mutation and reports malformed workstation availability reconstruction explicitly', () => {
    const node: Node = { id: asIdentifier<'Node'>('availability-corrupt-node'), name: 'Corrupt Node',
      administrativeState: 'active', configurationReference: 'config:corrupt', createdAt: NOW };
    persistence.registerNode(node, [], [event(node.id, 'node.registered')]);
    const evaluation: WorkstationWorkloadEvaluation = {
      id: asIdentifier<'WorkstationWorkloadEvaluation'>('availability-corrupt'), nodeId: node.id,
      ruleFingerprint: 'rules-v1', processBasenames: ['game.exe'], matchedRuleIds: ['game'],
      recommendation: 'recommend_draining', evaluatedAt: NOW,
    };
    persistence.recordWorkstationWorkloadEvaluation(evaluation, event(node.id, 'node.availability-evaluated'));
    persistence.close();
    const direct = new DatabaseSync(databasePath);
    expect(() => direct.prepare(`UPDATE workstation_availability_evaluations SET recommendation = 'recommend_active'
      WHERE id = ?`).run(evaluation.id)).toThrow(/append-only/);
    direct.exec('DROP TRIGGER workstation_availability_no_update');
    direct.prepare(`UPDATE workstation_availability_evaluations SET process_basenames_json = '[1]' WHERE id = ?`).run(evaluation.id);
    direct.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    expect(() => persistence.getWorkstationWorkloadEvaluations(node.id))
      .toThrow(/Corrupt persisted Workstation Workload Evaluation: availability-corrupt/);
  });
});

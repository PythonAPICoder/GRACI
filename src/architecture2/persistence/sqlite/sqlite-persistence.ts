import { createHash } from 'node:crypto';
import { dirname, resolve } from 'node:path';
import { mkdirSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';
import type {
  Approval,
  ArtifactMetadata,
  Attempt,
  AuditEvent,
  AuditEventInput,
  Failure,
  Goal,
  GoalBundle,
  GoalId,
  GoalSuccessCriterion,
  JsonObject,
  Task,
  TaskDependency,
  TaskGraphRevision,
  TaskGraphRevisionId,
  TaskId,
  Verification,
} from '../../domain/index.js';
import { assertIdentifier } from '../../domain/index.js';
import type { Architecture2Persistence } from '../contract.js';
import { migrate } from './migrations.js';

type Row = Record<string, unknown>;

export interface SqlitePersistenceOptions {
  databasePath: string;
}

function canonicalize(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(',')}]`;
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${canonicalize(object[key])}`).join(',')}}`;
}

function json(value: unknown): string {
  return canonicalize(value);
}

function parseObject(value: unknown): JsonObject {
  return JSON.parse(String(value)) as JsonObject;
}

function parseArray(value: unknown): string[] {
  return JSON.parse(String(value)) as string[];
}

function optionalString(value: unknown): string | undefined {
  return value === null || value === undefined ? undefined : String(value);
}

function bool(value: unknown): boolean {
  return Number(value) === 1;
}

function validateTimestamp(value: string, label: string): void {
  if (!value || Number.isNaN(Date.parse(value))) throw new Error(`Invalid ${label}: ${JSON.stringify(value)}`);
}

function validateEvent(event: AuditEventInput): void {
  assertIdentifier(event.id, 'event id');
  assertIdentifier(event.aggregateId, 'event aggregate id');
  if (!event.aggregateType.trim() || !event.eventType.trim() || !event.actor.trim()) {
    throw new Error('Event aggregate type, event type, and actor are required');
  }
  if (event.eventVersion < 1 || !Number.isInteger(event.eventVersion)) throw new Error('Event version must be a positive integer');
  validateTimestamp(event.occurredAt, 'event timestamp');
}

export class SqliteArchitecture2Persistence implements Architecture2Persistence {
  private database?: DatabaseSync;
  private readonly databasePath: string;

  constructor(options: SqlitePersistenceOptions) {
    if (!options.databasePath.trim()) throw new Error('A database path is required');
    this.databasePath = options.databasePath === ':memory:' ? ':memory:' : resolve(options.databasePath);
  }

  initialize(): void {
    if (this.database) return;
    if (this.databasePath !== ':memory:') mkdirSync(dirname(this.databasePath), { recursive: true });
    const database = new DatabaseSync(this.databasePath, { enableForeignKeyConstraints: true });
    try {
      database.exec('PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL; PRAGMA synchronous = FULL; PRAGMA busy_timeout = 5000;');
      migrate(database);
      this.database = database;
    } catch (error) {
      database.close();
      throw error;
    }
  }

  close(): void {
    this.database?.close();
    this.database = undefined;
  }

  [Symbol.dispose](): void {
    this.close();
  }

  getSchemaVersion(): number {
    return Number((this.db().prepare('SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations').get() as Row).version);
  }

  createGoal(bundle: GoalBundle, event: AuditEventInput): void {
    const { goal, criteria } = bundle;
    this.validateGoal(goal);
    this.transaction(() => {
      this.db().prepare(`INSERT INTO goals
        (id, objective, constraints_json, priority, privacy_class, status, active_graph_revision_id, terminal_reason, version, created_at, updated_at, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
        .run(goal.id, goal.objective, json(goal.constraints), goal.priority, goal.privacyClass, goal.status,
          goal.activeGraphRevisionId ?? null, goal.terminalReason ?? null, goal.version, goal.createdAt, goal.updatedAt, goal.completedAt ?? null);
      for (const criterion of criteria) this.insertCriterion(criterion);
      this.insertEvent(event);
    });
  }

  getGoal(id: GoalId): GoalBundle | undefined {
    const row = this.db().prepare('SELECT * FROM goals WHERE id = ?').get(id) as Row | undefined;
    if (!row) return undefined;
    const criteria = this.db().prepare('SELECT * FROM goal_success_criteria WHERE goal_id = ? ORDER BY position, id').all(id) as Row[];
    return { goal: this.mapGoal(row), criteria: criteria.map(this.mapCriterion) };
  }

  updateGoal(goal: Goal, expectedVersion: number, event: AuditEventInput): void {
    this.validateGoal(goal);
    if (goal.version !== expectedVersion + 1) throw new Error('Goal version must increment exactly once');
    this.transaction(() => {
      const result = this.db().prepare(`UPDATE goals SET
        objective = ?, constraints_json = ?, priority = ?, privacy_class = ?, status = ?,
        active_graph_revision_id = ?, terminal_reason = ?, version = ?, updated_at = ?, completed_at = ?
        WHERE id = ? AND version = ?`)
        .run(goal.objective, json(goal.constraints), goal.priority, goal.privacyClass, goal.status,
          goal.activeGraphRevisionId ?? null, goal.terminalReason ?? null, goal.version, goal.updatedAt,
          goal.completedAt ?? null, goal.id, expectedVersion);
      if (Number(result.changes) !== 1) throw new Error(`Goal concurrency conflict: ${goal.id}`);
      this.insertEvent(event);
    });
  }

  createTaskGraphRevision(revision: TaskGraphRevision, event: AuditEventInput): void {
    assertIdentifier(revision.id, 'task graph revision id');
    assertIdentifier(revision.goalId, 'goal id');
    validateTimestamp(revision.createdAt, 'task graph revision timestamp');
    this.transaction(() => {
      this.db().prepare('INSERT INTO task_graph_revisions(id, goal_id, revision, rationale, created_at) VALUES (?, ?, ?, ?, ?)')
        .run(revision.id, revision.goalId, revision.revision, revision.rationale ?? null, revision.createdAt);
      this.insertEvent(event);
    });
  }

  getTaskGraphRevisions(goalId: GoalId): TaskGraphRevision[] {
    return (this.db().prepare('SELECT * FROM task_graph_revisions WHERE goal_id = ? ORDER BY revision, id').all(goalId) as Row[])
      .map((row) => ({ id: String(row.id) as TaskGraphRevision['id'], goalId: String(row.goal_id) as GoalId,
        revision: Number(row.revision), rationale: optionalString(row.rationale), createdAt: String(row.created_at) }));
  }

  createTask(task: Task, event: AuditEventInput): void {
    assertIdentifier(task.id, 'task id');
    assertIdentifier(task.goalId, 'goal id');
    assertIdentifier(task.graphRevisionId, 'task graph revision id');
    validateTimestamp(task.createdAt, 'task creation timestamp');
    validateTimestamp(task.updatedAt, 'task update timestamp');
    this.transaction(() => {
      this.db().prepare(`INSERT INTO tasks
        (id, goal_id, graph_revision_id, parent_task_id, title, objective, inputs_json, required_capabilities_json,
         privacy_class, priority, status, required, retry_policy_json, verification_plan_json, terminal_reason,
         version, created_at, updated_at, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
        .run(task.id, task.goalId, task.graphRevisionId, task.parentTaskId ?? null, task.title, task.objective,
          json(task.inputs), json(task.requiredCapabilities), task.privacyClass, task.priority, task.status,
          task.required ? 1 : 0, json(task.retryPolicy), json(task.verificationPlan), task.terminalReason ?? null,
          task.version, task.createdAt, task.updatedAt, task.completedAt ?? null);
      this.insertEvent(event);
    });
  }

  getTask(id: TaskId): Task | undefined {
    const row = this.db().prepare('SELECT * FROM tasks WHERE id = ?').get(id) as Row | undefined;
    return row ? this.mapTask(row) : undefined;
  }

  updateTask(task: Task, expectedVersion: number, event: AuditEventInput): void {
    assertIdentifier(task.id, 'task id');
    if (task.version !== expectedVersion + 1) throw new Error('Task version must increment exactly once');
    validateTimestamp(task.updatedAt, 'task update timestamp');
    this.transaction(() => {
      const result = this.db().prepare(`UPDATE tasks SET
        status = ?, terminal_reason = ?, version = ?, updated_at = ?, completed_at = ?
        WHERE id = ? AND version = ?`)
        .run(task.status, task.terminalReason ?? null, task.version, task.updatedAt,
          task.completedAt ?? null, task.id, expectedVersion);
      if (Number(result.changes) !== 1) throw new Error(`Task concurrency conflict: ${task.id}`);
      this.insertEvent(event);
    });
  }

  createTaskDependency(dependency: TaskDependency, event: AuditEventInput): void {
    if (dependency.condition === 'predicate' && !dependency.predicate) throw new Error('Predicate dependency requires a predicate');
    validateTimestamp(dependency.createdAt, 'task dependency timestamp');
    this.transaction(() => {
      this.db().prepare(`INSERT INTO task_dependencies
        (graph_revision_id, predecessor_task_id, successor_task_id, condition, predicate_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)`)
        .run(dependency.graphRevisionId, dependency.predecessorTaskId, dependency.successorTaskId,
          dependency.condition, dependency.predicate ? json(dependency.predicate) : null, dependency.createdAt);
      this.insertEvent(event);
    });
  }

  getTaskDependencies(revisionId: TaskGraphRevisionId): TaskDependency[] {
    return (this.db().prepare(`SELECT * FROM task_dependencies WHERE graph_revision_id = ?
      ORDER BY predecessor_task_id, successor_task_id`).all(revisionId) as Row[]).map((row) => ({
      graphRevisionId: String(row.graph_revision_id) as TaskGraphRevisionId,
      predecessorTaskId: String(row.predecessor_task_id) as TaskId,
      successorTaskId: String(row.successor_task_id) as TaskId,
      condition: String(row.condition) as TaskDependency['condition'],
      predicate: row.predicate_json === null ? undefined : parseObject(row.predicate_json),
      createdAt: String(row.created_at),
    }));
  }

  createAttempt(attempt: Attempt, event: AuditEventInput): void {
    assertIdentifier(attempt.id, 'attempt id');
    validateTimestamp(attempt.createdAt, 'attempt creation timestamp');
    this.transaction(() => {
      this.db().prepare(`INSERT INTO attempts
        (id, task_id, attempt_number, status, provider_offering_id, compute_node_id, input_snapshot_json,
         result_json, idempotency_key, started_at, completed_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
        .run(attempt.id, attempt.taskId, attempt.attemptNumber, attempt.status, attempt.providerOfferingId ?? null,
          attempt.computeNodeId ?? null, json(attempt.inputSnapshot), attempt.result ? json(attempt.result) : null,
          attempt.idempotencyKey ?? null, attempt.startedAt ?? null, attempt.completedAt ?? null, attempt.createdAt);
      this.insertEvent(event);
    });
  }

  getAttempts(taskId: TaskId): Attempt[] {
    return (this.db().prepare('SELECT * FROM attempts WHERE task_id = ? ORDER BY attempt_number, id').all(taskId) as Row[])
      .map((row) => ({ id: String(row.id) as Attempt['id'], taskId: String(row.task_id) as TaskId,
        attemptNumber: Number(row.attempt_number), status: String(row.status) as Attempt['status'],
        providerOfferingId: optionalString(row.provider_offering_id), computeNodeId: optionalString(row.compute_node_id),
        inputSnapshot: parseObject(row.input_snapshot_json), result: row.result_json === null ? undefined : parseObject(row.result_json),
        idempotencyKey: optionalString(row.idempotency_key), startedAt: optionalString(row.started_at),
        completedAt: optionalString(row.completed_at), createdAt: String(row.created_at) }));
  }

  createVerification(value: Verification, event: AuditEventInput): void {
    this.transaction(() => {
      this.db().prepare(`INSERT INTO verifications
        (id, task_id, attempt_id, verdict, plan_version, verifier, criterion_results_json, evidence_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`)
        .run(value.id, value.taskId, value.attemptId ?? null, value.verdict, value.planVersion, value.verifier,
          json(value.criterionResults), json(value.evidence), value.createdAt);
      this.insertEvent(event);
    });
  }

  createFailure(value: Failure, event: AuditEventInput): void {
    this.transaction(() => {
      this.db().prepare(`INSERT INTO failures
        (id, task_id, attempt_id, category, code, summary, details_json, retryable, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`)
        .run(value.id, value.taskId, value.attemptId ?? null, value.category, value.code, value.summary,
          json(value.details), value.retryable ? 1 : 0, value.createdAt);
      this.insertEvent(event);
    });
  }

  createApproval(value: Approval, event: AuditEventInput): void {
    this.transaction(() => {
      this.db().prepare(`INSERT INTO approvals
        (id, goal_id, task_id, attempt_id, action, scope_json, action_digest, decision, decided_by, requested_at, decided_at, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
        .run(value.id, value.goalId, value.taskId ?? null, value.attemptId ?? null, value.action, json(value.scope),
          value.actionDigest, value.decision, value.decidedBy ?? null, value.requestedAt, value.decidedAt ?? null, value.expiresAt ?? null);
      this.insertEvent(event);
    });
  }

  createArtifact(value: ArtifactMetadata, event: AuditEventInput): void {
    this.transaction(() => {
      this.db().prepare(`INSERT INTO artifacts
        (id, logical_name, version, media_type, storage_reference, sha256, size_bytes, privacy_class, producer_attempt_id, provenance_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
        .run(value.id, value.logicalName, value.version, value.mediaType, value.storageReference, value.sha256,
          value.sizeBytes ?? null, value.privacyClass, value.producerAttemptId ?? null, json(value.provenance), value.createdAt);
      this.insertEvent(event);
    });
  }

  appendEvent(event: AuditEventInput): AuditEvent {
    return this.transaction(() => this.insertEvent(event));
  }

  getEvents(afterSequence = 0): AuditEvent[] {
    if (!Number.isInteger(afterSequence) || afterSequence < 0) throw new Error('afterSequence must be a non-negative integer');
    return (this.db().prepare('SELECT * FROM events WHERE sequence > ? ORDER BY sequence').all(afterSequence) as Row[])
      .map((row) => ({ sequence: Number(row.sequence), id: String(row.id) as AuditEvent['id'],
        aggregateType: String(row.aggregate_type), aggregateId: String(row.aggregate_id), eventType: String(row.event_type),
        eventVersion: Number(row.event_version), actor: String(row.actor), correlationId: optionalString(row.correlation_id),
        causationId: optionalString(row.causation_id) as AuditEvent['causationId'], occurredAt: String(row.occurred_at),
        payload: parseObject(row.payload_json), previousHash: optionalString(row.previous_hash), eventHash: String(row.event_hash) }));
  }

  private db(): DatabaseSync {
    if (!this.database) throw new Error('Persistence provider is not initialized');
    return this.database;
  }

  private transaction<T>(operation: () => T): T {
    const database = this.db();
    database.exec('BEGIN IMMEDIATE');
    try {
      const result = operation();
      database.exec('COMMIT');
      return result;
    } catch (error) {
      database.exec('ROLLBACK');
      throw error;
    }
  }

  private insertEvent(event: AuditEventInput): AuditEvent {
    validateEvent(event);
    const previous = this.db().prepare('SELECT event_hash FROM events ORDER BY sequence DESC LIMIT 1').get() as Row | undefined;
    const previousHash = previous ? String(previous.event_hash) : undefined;
    const eventHash = createHash('sha256').update(canonicalize({ previousHash: previousHash ?? null, ...event })).digest('hex');
    const result = this.db().prepare(`INSERT INTO events
      (id, aggregate_type, aggregate_id, event_type, event_version, actor, correlation_id, causation_id,
       occurred_at, payload_json, previous_hash, event_hash)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .run(event.id, event.aggregateType, event.aggregateId, event.eventType, event.eventVersion, event.actor,
        event.correlationId ?? null, event.causationId ?? null, event.occurredAt, json(event.payload), previousHash ?? null, eventHash);
    return { ...event, sequence: Number(result.lastInsertRowid), previousHash, eventHash };
  }

  private validateGoal(goal: Goal): void {
    assertIdentifier(goal.id, 'goal id');
    if (!goal.objective.trim()) throw new Error('Goal objective is required');
    validateTimestamp(goal.createdAt, 'goal creation timestamp');
    validateTimestamp(goal.updatedAt, 'goal update timestamp');
  }

  private insertCriterion(criterion: GoalSuccessCriterion): void {
    assertIdentifier(criterion.id, 'goal criterion id');
    validateTimestamp(criterion.createdAt, 'criterion creation timestamp');
    this.db().prepare(`INSERT INTO goal_success_criteria
      (id, goal_id, description, required, verification_method, position, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)`)
      .run(criterion.id, criterion.goalId, criterion.description, criterion.required ? 1 : 0,
        criterion.verificationMethod, criterion.position, criterion.createdAt);
  }

  private mapGoal(row: Row): Goal {
    return { id: String(row.id) as Goal['id'], objective: String(row.objective), constraints: parseObject(row.constraints_json),
      priority: String(row.priority) as Goal['priority'], privacyClass: String(row.privacy_class) as Goal['privacyClass'],
      status: String(row.status) as Goal['status'], activeGraphRevisionId: optionalString(row.active_graph_revision_id) as Goal['activeGraphRevisionId'],
      terminalReason: optionalString(row.terminal_reason), version: Number(row.version), createdAt: String(row.created_at),
      updatedAt: String(row.updated_at), completedAt: optionalString(row.completed_at) };
  }

  private mapCriterion(row: Row): GoalSuccessCriterion {
    return { id: String(row.id) as GoalSuccessCriterion['id'], goalId: String(row.goal_id) as GoalId,
      description: String(row.description), required: bool(row.required), verificationMethod: String(row.verification_method),
      position: Number(row.position), createdAt: String(row.created_at) };
  }

  private mapTask(row: Row): Task {
    return { id: String(row.id) as TaskId, goalId: String(row.goal_id) as GoalId,
      graphRevisionId: String(row.graph_revision_id) as TaskGraphRevisionId, parentTaskId: optionalString(row.parent_task_id) as TaskId,
      title: String(row.title), objective: String(row.objective), inputs: parseObject(row.inputs_json),
      requiredCapabilities: parseArray(row.required_capabilities_json), privacyClass: String(row.privacy_class) as Task['privacyClass'],
      priority: String(row.priority) as Task['priority'], status: String(row.status) as Task['status'], required: bool(row.required),
      retryPolicy: parseObject(row.retry_policy_json), verificationPlan: parseObject(row.verification_plan_json),
      terminalReason: optionalString(row.terminal_reason), version: Number(row.version), createdAt: String(row.created_at),
      updatedAt: String(row.updated_at), completedAt: optionalString(row.completed_at) };
  }
}

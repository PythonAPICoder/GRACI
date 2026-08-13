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
import { validateTaskGraph } from '../../workflow/task-graph-validator.js';
import { migrate } from './migrations.js';

type Row = Record<string, unknown>;

const TASK_STATUSES = new Set<Task['status']>([
  'planned', 'blocked', 'ready', 'waiting_for_approval', 'scheduled', 'running', 'verifying',
  'retry_pending', 'succeeded', 'failed', 'cancelled', 'superseded',
]);
const TASK_PRIORITIES = new Set<Task['priority']>(['critical', 'interactive', 'normal', 'background', 'idle']);
const PRIVACY_CLASSES = new Set<Task['privacyClass']>(['public', 'internal', 'personal', 'confidential', 'secret']);
const ATTEMPT_STATUSES = new Set<Attempt['status']>(['created', 'running', 'succeeded', 'failed', 'cancelled', 'indeterminate']);

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
  let parsed: unknown;
  try {
    parsed = JSON.parse(String(value));
  } catch {
    throw new Error('Corrupt persisted JSON object');
  }
  if (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error('Corrupt persisted JSON: expected an object');
  }
  return parsed as JsonObject;
}

function parseArray(value: unknown): string[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(String(value));
  } catch {
    throw new Error('Corrupt persisted JSON array');
  }
  if (!Array.isArray(parsed) || parsed.some((entry) => typeof entry !== 'string')) {
    throw new Error('Corrupt persisted JSON: expected a string array');
  }
  return parsed;
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
    this.validateTaskGraphRevision(revision);
    this.transaction(() => {
      this.insertTaskGraphRevision(revision);
      this.insertEvent(event);
    });
  }

  admitTaskGraph(revision: TaskGraphRevision, tasks: readonly Task[], dependencies: readonly TaskDependency[],
    events: readonly AuditEventInput[]): void {
    this.validateTaskGraphRevision(revision);
    for (const task of tasks) this.validateTask(task);
    for (const dependency of dependencies) validateTimestamp(dependency.createdAt, 'task dependency timestamp');
    validateTaskGraph(revision, tasks, dependencies);
    const expectedEvents = 1 + tasks.length + dependencies.length;
    if (events.length !== expectedEvents) {
      throw new Error(`Graph admission requires exactly ${expectedEvents} structural events`);
    }
    this.transaction(() => {
      this.insertTaskGraphRevision(revision);
      for (const task of tasks) this.insertTask(task);
      for (const dependency of dependencies) this.insertTaskDependency(dependency);
      this.insertEvents(events);
    });
  }

  getTaskGraphRevision(id: TaskGraphRevisionId): TaskGraphRevision | undefined {
    const row = this.db().prepare('SELECT * FROM task_graph_revisions WHERE id = ?').get(id) as Row | undefined;
    return row ? this.mapTaskGraphRevision(row) : undefined;
  }

  getTaskGraphRevisions(goalId: GoalId): TaskGraphRevision[] {
    return (this.db().prepare('SELECT * FROM task_graph_revisions WHERE goal_id = ? ORDER BY revision, id').all(goalId) as Row[])
      .map((row) => this.mapTaskGraphRevision(row));
  }

  createTask(task: Task, event: AuditEventInput): void {
    this.validateTask(task);
    this.transaction(() => {
      this.insertTask(task);
      this.insertEvent(event);
    });
  }

  getTask(id: TaskId): Task | undefined {
    const row = this.db().prepare('SELECT * FROM tasks WHERE id = ?').get(id) as Row | undefined;
    return row ? this.mapTask(row) : undefined;
  }

  getTasks(revisionId: TaskGraphRevisionId): Task[] {
    return (this.db().prepare(`SELECT * FROM tasks WHERE graph_revision_id = ?
      ORDER BY created_at, id`).all(revisionId) as Row[]).map((row) => this.mapTask(row));
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
      this.insertTaskDependency(dependency);
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
      createdAt: this.validatedTimestamp(row.created_at, 'persisted task dependency timestamp'),
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
      .map((row) => this.mapAttempt(row));
  }

  startAttempt(task: Task, expectedVersion: number, attempt: Attempt, events: readonly AuditEventInput[]): void {
    this.transaction(() => {
      this.updateTaskRow(task, expectedVersion);
      this.insertAttempt(attempt);
      this.insertEvents(events);
    });
  }

  recordAttemptOutcome(
    task: Task,
    expectedVersion: number,
    attempt: Attempt,
    failure: Failure | undefined,
    events: readonly AuditEventInput[],
  ): void {
    this.transaction(() => {
      this.updateAttemptRow(attempt);
      if (failure) this.insertFailure(failure);
      this.updateTaskRow(task, expectedVersion);
      this.insertEvents(events);
    });
  }

  recordVerificationOutcome(
    task: Task,
    expectedVersion: number,
    verification: Verification,
    failure: Failure | undefined,
    events: readonly AuditEventInput[],
  ): void {
    this.transaction(() => {
      this.insertVerification(verification);
      if (failure) this.insertFailure(failure);
      this.updateTaskRow(task, expectedVersion);
      this.insertEvents(events);
    });
  }

  recordTaskFailure(task: Task, expectedVersion: number, failure: Failure, events: readonly AuditEventInput[]): void {
    this.transaction(() => {
      this.insertFailure(failure);
      this.updateTaskRow(task, expectedVersion);
      this.insertEvents(events);
    });
  }

  createVerification(value: Verification, event: AuditEventInput): void {
    this.transaction(() => {
      this.insertVerification(value);
      this.insertEvent(event);
    });
  }

  getVerifications(taskId: TaskId): Verification[] {
    return (this.db().prepare('SELECT * FROM verifications WHERE task_id = ? ORDER BY created_at, id').all(taskId) as Row[])
      .map((row) => ({ id: String(row.id) as Verification['id'], taskId: String(row.task_id) as TaskId,
        attemptId: optionalString(row.attempt_id) as Verification['attemptId'], verdict: String(row.verdict) as Verification['verdict'],
        planVersion: Number(row.plan_version), verifier: String(row.verifier), criterionResults: parseObject(row.criterion_results_json),
        evidence: parseObject(row.evidence_json), createdAt: String(row.created_at) }));
  }

  createFailure(value: Failure, event: AuditEventInput): void {
    this.transaction(() => {
      this.insertFailure(value);
      this.insertEvent(event);
    });
  }

  getFailures(taskId: TaskId): Failure[] {
    return (this.db().prepare('SELECT * FROM failures WHERE task_id = ? ORDER BY created_at, id').all(taskId) as Row[])
      .map((row) => ({ id: String(row.id) as Failure['id'], taskId: String(row.task_id) as TaskId,
        attemptId: optionalString(row.attempt_id) as Failure['attemptId'], category: String(row.category) as Failure['category'],
        classification: String(row.classification) as Failure['classification'],
        code: String(row.code), summary: String(row.summary), details: parseObject(row.details_json),
        retryable: bool(row.retryable), createdAt: String(row.created_at) }));
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

  getApprovals(taskId: TaskId): Approval[] {
    return (this.db().prepare('SELECT * FROM approvals WHERE task_id = ? ORDER BY requested_at, id').all(taskId) as Row[])
      .map((row) => ({ id: String(row.id) as Approval['id'], goalId: String(row.goal_id) as GoalId,
        taskId: optionalString(row.task_id) as Approval['taskId'], attemptId: optionalString(row.attempt_id) as Approval['attemptId'],
        action: String(row.action), scope: parseObject(row.scope_json), actionDigest: String(row.action_digest),
        decision: String(row.decision) as Approval['decision'], decidedBy: optionalString(row.decided_by),
        requestedAt: String(row.requested_at), decidedAt: optionalString(row.decided_at), expiresAt: optionalString(row.expires_at) }));
  }

  recordApprovalPause(task: Task, expectedVersion: number, attempt: Attempt, failure: Failure,
    approval: Approval, events: readonly AuditEventInput[]): void {
    this.transaction(() => {
      this.updateAttemptRow(attempt);
      this.insertFailure(failure);
      this.insertApproval(approval);
      this.updateTaskRow(task, expectedVersion);
      this.insertEvents(events);
    });
  }

  recordApprovalDecision(task: Task, expectedVersion: number, approval: Approval,
    events: readonly AuditEventInput[]): void {
    this.transaction(() => {
      const result = this.db().prepare(`UPDATE approvals SET decision = ?, decided_by = ?, decided_at = ?, scope_json = ?
        WHERE id = ? AND decision = 'requested'`).run(approval.decision, approval.decidedBy ?? null,
          approval.decidedAt ?? null, json(approval.scope), approval.id);
      if (Number(result.changes) !== 1) throw new Error(`Approval is not pending: ${approval.id}`);
      this.updateTaskRow(task, expectedVersion);
      this.insertEvents(events);
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

  private insertEvents(events: readonly AuditEventInput[]): void {
    if (events.length === 0) throw new Error('At least one workflow event is required');
    for (const event of events) this.insertEvent(event);
  }

  private insertTaskGraphRevision(revision: TaskGraphRevision): void {
    this.db().prepare('INSERT INTO task_graph_revisions(id, goal_id, revision, rationale, created_at) VALUES (?, ?, ?, ?, ?)')
      .run(revision.id, revision.goalId, revision.revision, revision.rationale ?? null, revision.createdAt);
  }

  private insertTask(task: Task): void {
    this.db().prepare(`INSERT INTO tasks
      (id, goal_id, graph_revision_id, parent_task_id, title, objective, inputs_json, required_capabilities_json,
       privacy_class, priority, status, required, retry_policy_json, verification_plan_json, terminal_reason,
       version, created_at, updated_at, completed_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .run(task.id, task.goalId, task.graphRevisionId, task.parentTaskId ?? null, task.title, task.objective,
        json(task.inputs), json(task.requiredCapabilities), task.privacyClass, task.priority, task.status,
        task.required ? 1 : 0, json(task.retryPolicy), json(task.verificationPlan), task.terminalReason ?? null,
        task.version, task.createdAt, task.updatedAt, task.completedAt ?? null);
  }

  private insertTaskDependency(dependency: TaskDependency): void {
    this.db().prepare(`INSERT INTO task_dependencies
      (graph_revision_id, predecessor_task_id, successor_task_id, condition, predicate_json, created_at)
      VALUES (?, ?, ?, ?, ?, ?)`)
      .run(dependency.graphRevisionId, dependency.predecessorTaskId, dependency.successorTaskId,
        dependency.condition, dependency.predicate === undefined ? null : json(dependency.predicate), dependency.createdAt);
  }

  private updateTaskRow(task: Task, expectedVersion: number): void {
    assertIdentifier(task.id, 'task id');
    if (task.version !== expectedVersion + 1) throw new Error('Task version must increment exactly once');
    validateTimestamp(task.updatedAt, 'task update timestamp');
    const result = this.db().prepare(`UPDATE tasks SET
      status = ?, terminal_reason = ?, version = ?, updated_at = ?, completed_at = ?
      WHERE id = ? AND version = ?`)
      .run(task.status, task.terminalReason ?? null, task.version, task.updatedAt,
        task.completedAt ?? null, task.id, expectedVersion);
    if (Number(result.changes) !== 1) throw new Error(`Task concurrency conflict: ${task.id}`);
  }

  private insertAttempt(attempt: Attempt): void {
    assertIdentifier(attempt.id, 'attempt id');
    validateTimestamp(attempt.createdAt, 'attempt creation timestamp');
    this.db().prepare(`INSERT INTO attempts
      (id, task_id, attempt_number, status, provider_offering_id, compute_node_id, input_snapshot_json,
       result_json, idempotency_key, started_at, completed_at, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .run(attempt.id, attempt.taskId, attempt.attemptNumber, attempt.status, attempt.providerOfferingId ?? null,
        attempt.computeNodeId ?? null, json(attempt.inputSnapshot), attempt.result ? json(attempt.result) : null,
        attempt.idempotencyKey ?? null, attempt.startedAt ?? null, attempt.completedAt ?? null, attempt.createdAt);
  }

  private updateAttemptRow(attempt: Attempt): void {
    assertIdentifier(attempt.id, 'attempt id');
    if (!attempt.completedAt || !['succeeded', 'failed', 'cancelled', 'indeterminate'].includes(attempt.status)) {
      throw new Error('Attempt outcome must be terminal and include completedAt');
    }
    const result = this.db().prepare(`UPDATE attempts SET status = ?, result_json = ?, completed_at = ?
      WHERE id = ? AND task_id = ? AND status = 'running'`)
      .run(attempt.status, attempt.result ? json(attempt.result) : null, attempt.completedAt, attempt.id, attempt.taskId);
    if (Number(result.changes) !== 1) throw new Error(`Attempt concurrency conflict: ${attempt.id}`);
  }

  private insertVerification(value: Verification): void {
    this.db().prepare(`INSERT INTO verifications
      (id, task_id, attempt_id, verdict, plan_version, verifier, criterion_results_json, evidence_json, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .run(value.id, value.taskId, value.attemptId ?? null, value.verdict, value.planVersion, value.verifier,
        json(value.criterionResults), json(value.evidence), value.createdAt);
  }

  private insertFailure(value: Failure): void {
    this.db().prepare(`INSERT INTO failures
      (id, task_id, attempt_id, category, classification, code, summary, details_json, retryable, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .run(value.id, value.taskId, value.attemptId ?? null, value.category, value.classification, value.code, value.summary,
        json(value.details), value.retryable ? 1 : 0, value.createdAt);
  }

  private insertApproval(value: Approval): void {
    this.db().prepare(`INSERT INTO approvals
      (id, goal_id, task_id, attempt_id, action, scope_json, action_digest, decision, decided_by, requested_at, decided_at, expires_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .run(value.id, value.goalId, value.taskId ?? null, value.attemptId ?? null, value.action, json(value.scope),
        value.actionDigest, value.decision, value.decidedBy ?? null, value.requestedAt, value.decidedAt ?? null, value.expiresAt ?? null);
  }

  private validateGoal(goal: Goal): void {
    assertIdentifier(goal.id, 'goal id');
    if (!goal.objective.trim()) throw new Error('Goal objective is required');
    validateTimestamp(goal.createdAt, 'goal creation timestamp');
    validateTimestamp(goal.updatedAt, 'goal update timestamp');
  }

  private validateTaskGraphRevision(revision: TaskGraphRevision): void {
    assertIdentifier(revision.id, 'task graph revision id');
    assertIdentifier(revision.goalId, 'goal id');
    if (!Number.isInteger(revision.revision) || revision.revision < 1) {
      throw new Error('Task graph revision number must be a positive integer');
    }
    validateTimestamp(revision.createdAt, 'task graph revision timestamp');
  }

  private validateTask(task: Task): void {
    assertIdentifier(task.id, 'task id');
    assertIdentifier(task.goalId, 'goal id');
    assertIdentifier(task.graphRevisionId, 'task graph revision id');
    if (task.parentTaskId) assertIdentifier(task.parentTaskId, 'parent task id');
    if (!task.title.trim() || !task.objective.trim()) throw new Error('Task title and objective are required');
    if (!TASK_STATUSES.has(task.status)) throw new Error(`Invalid Task status: ${task.status}`);
    if (!TASK_PRIORITIES.has(task.priority)) throw new Error(`Invalid Task priority: ${task.priority}`);
    if (!PRIVACY_CLASSES.has(task.privacyClass)) throw new Error(`Invalid Task privacy class: ${task.privacyClass}`);
    if (!Number.isInteger(task.version) || task.version < 1) throw new Error('Task version must be a positive integer');
    if (!Array.isArray(task.requiredCapabilities) || task.requiredCapabilities.some((value) => typeof value !== 'string')) {
      throw new Error('Task required capabilities must be a string array');
    }
    validateTimestamp(task.createdAt, 'task creation timestamp');
    validateTimestamp(task.updatedAt, 'task update timestamp');
    if (task.completedAt) validateTimestamp(task.completedAt, 'task completion timestamp');
  }

  private validatedTimestamp(value: unknown, label: string): string {
    const timestamp = String(value);
    validateTimestamp(timestamp, label);
    return timestamp;
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

  private mapTaskGraphRevision(row: Row): TaskGraphRevision {
    const revision: TaskGraphRevision = {
      id: String(row.id) as TaskGraphRevisionId,
      goalId: String(row.goal_id) as GoalId,
      revision: Number(row.revision),
      rationale: optionalString(row.rationale),
      createdAt: this.validatedTimestamp(row.created_at, 'persisted task graph revision timestamp'),
    };
    this.validateTaskGraphRevision(revision);
    return revision;
  }

  private mapCriterion(row: Row): GoalSuccessCriterion {
    return { id: String(row.id) as GoalSuccessCriterion['id'], goalId: String(row.goal_id) as GoalId,
      description: String(row.description), required: bool(row.required), verificationMethod: String(row.verification_method),
      position: Number(row.position), createdAt: String(row.created_at) };
  }

  private mapTask(row: Row): Task {
    const task = { id: String(row.id) as TaskId, goalId: String(row.goal_id) as GoalId,
      graphRevisionId: String(row.graph_revision_id) as TaskGraphRevisionId, parentTaskId: optionalString(row.parent_task_id) as TaskId,
      title: String(row.title), objective: String(row.objective), inputs: parseObject(row.inputs_json),
      requiredCapabilities: parseArray(row.required_capabilities_json), privacyClass: String(row.privacy_class) as Task['privacyClass'],
      priority: String(row.priority) as Task['priority'], status: String(row.status) as Task['status'], required: bool(row.required),
      retryPolicy: parseObject(row.retry_policy_json) as Task['retryPolicy'], verificationPlan: parseObject(row.verification_plan_json),
      terminalReason: optionalString(row.terminal_reason), version: Number(row.version), createdAt: String(row.created_at),
      updatedAt: String(row.updated_at), completedAt: optionalString(row.completed_at) };
    this.validateTask(task);
    const isTerminal = ['succeeded', 'failed', 'cancelled', 'superseded'].includes(task.status);
    if (isTerminal !== Boolean(task.completedAt)) throw new Error(`Corrupt persisted Task completion state: ${task.id}`);
    return task;
  }

  private mapAttempt(row: Row): Attempt {
    const attempt = { id: String(row.id) as Attempt['id'], taskId: String(row.task_id) as TaskId,
      attemptNumber: Number(row.attempt_number), status: String(row.status) as Attempt['status'],
      providerOfferingId: optionalString(row.provider_offering_id), computeNodeId: optionalString(row.compute_node_id),
      inputSnapshot: parseObject(row.input_snapshot_json), result: row.result_json === null ? undefined : parseObject(row.result_json),
      idempotencyKey: optionalString(row.idempotency_key), startedAt: optionalString(row.started_at),
      completedAt: optionalString(row.completed_at), createdAt: String(row.created_at) };
    assertIdentifier(attempt.id, 'persisted attempt id');
    assertIdentifier(attempt.taskId, 'persisted attempt task id');
    if (!Number.isInteger(attempt.attemptNumber) || attempt.attemptNumber < 1) throw new Error('Corrupt persisted Attempt number');
    if (!ATTEMPT_STATUSES.has(attempt.status)) throw new Error(`Corrupt persisted Attempt status: ${attempt.status}`);
    validateTimestamp(attempt.createdAt, 'persisted attempt creation timestamp');
    if (attempt.startedAt) validateTimestamp(attempt.startedAt, 'persisted attempt start timestamp');
    if (attempt.completedAt) validateTimestamp(attempt.completedAt, 'persisted attempt completion timestamp');
    const isTerminal = ['succeeded', 'failed', 'cancelled', 'indeterminate'].includes(attempt.status);
    if (isTerminal !== Boolean(attempt.completedAt)) throw new Error(`Corrupt persisted Attempt completion state: ${attempt.id}`);
    return attempt;
  }
}

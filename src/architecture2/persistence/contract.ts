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
  Task,
  TaskDependency,
  TaskGraphRevision,
  TaskGraphRevisionId,
  TaskId,
  Verification,
} from '../domain/index.js';

export interface Architecture2Persistence extends Disposable {
  initialize(): void;
  close(): void;
  getSchemaVersion(): number;

  createGoal(bundle: GoalBundle, event: AuditEventInput): void;
  getGoal(id: GoalId): GoalBundle | undefined;
  updateGoal(goal: Goal, expectedVersion: number, event: AuditEventInput): void;
  createTaskGraphRevision(revision: TaskGraphRevision, event: AuditEventInput): void;
  admitTaskGraph(revision: TaskGraphRevision, tasks: readonly Task[], dependencies: readonly TaskDependency[],
    events: readonly AuditEventInput[]): void;
  getTaskGraphRevision(id: TaskGraphRevisionId): TaskGraphRevision | undefined;
  getTaskGraphRevisions(goalId: GoalId): TaskGraphRevision[];
  createTask(task: Task, event: AuditEventInput): void;
  getTask(id: TaskId): Task | undefined;
  getTasks(revisionId: TaskGraphRevisionId): Task[];
  updateTask(task: Task, expectedVersion: number, event: AuditEventInput): void;
  createTaskDependency(dependency: TaskDependency, event: AuditEventInput): void;
  getTaskDependencies(revisionId: TaskGraphRevisionId): TaskDependency[];

  createAttempt(attempt: Attempt, event: AuditEventInput): void;
  getAttempts(taskId: TaskId): Attempt[];
  startAttempt(task: Task, expectedVersion: number, attempt: Attempt, events: readonly AuditEventInput[]): void;
  recordAttemptOutcome(
    task: Task,
    expectedVersion: number,
    attempt: Attempt,
    failure: Failure | undefined,
    events: readonly AuditEventInput[],
  ): void;
  recordVerificationOutcome(
    task: Task,
    expectedVersion: number,
    verification: Verification,
    failure: Failure | undefined,
    events: readonly AuditEventInput[],
  ): void;
  recordTaskFailure(task: Task, expectedVersion: number, failure: Failure, events: readonly AuditEventInput[]): void;
  createVerification(verification: Verification, event: AuditEventInput): void;
  getVerifications(taskId: TaskId): Verification[];
  createFailure(failure: Failure, event: AuditEventInput): void;
  getFailures(taskId: TaskId): Failure[];
  createApproval(approval: Approval, event: AuditEventInput): void;
  getApprovals(taskId: TaskId): Approval[];
  recordApprovalPause(task: Task, expectedVersion: number, attempt: Attempt, failure: Failure,
    approval: Approval, events: readonly AuditEventInput[]): void;
  recordApprovalDecision(task: Task, expectedVersion: number, approval: Approval,
    events: readonly AuditEventInput[]): void;
  createArtifact(artifact: ArtifactMetadata, event: AuditEventInput): void;

  appendEvent(event: AuditEventInput): AuditEvent;
  getEvents(afterSequence?: number): AuditEvent[];
}

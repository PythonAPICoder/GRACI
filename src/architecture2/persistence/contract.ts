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
  getTaskGraphRevisions(goalId: GoalId): TaskGraphRevision[];
  createTask(task: Task, event: AuditEventInput): void;
  getTask(id: TaskId): Task | undefined;
  updateTask(task: Task, expectedVersion: number, event: AuditEventInput): void;
  createTaskDependency(dependency: TaskDependency, event: AuditEventInput): void;
  getTaskDependencies(revisionId: TaskGraphRevisionId): TaskDependency[];

  createAttempt(attempt: Attempt, event: AuditEventInput): void;
  getAttempts(taskId: TaskId): Attempt[];
  createVerification(verification: Verification, event: AuditEventInput): void;
  createFailure(failure: Failure, event: AuditEventInput): void;
  createApproval(approval: Approval, event: AuditEventInput): void;
  createArtifact(artifact: ArtifactMetadata, event: AuditEventInput): void;

  appendEvent(event: AuditEventInput): AuditEvent;
  getEvents(afterSequence?: number): AuditEvent[];
}

import type {
  ApprovalId,
  ArtifactId,
  AttemptId,
  EventId,
  FailureId,
  GoalCriterionId,
  GoalId,
  TaskGraphRevisionId,
  TaskId,
  VerificationId,
} from './ids.js';

export type IsoTimestamp = string;
export type JsonObject = Record<string, unknown>;
export type PrivacyClass = 'public' | 'internal' | 'personal' | 'confidential' | 'secret';

export type GoalStatus =
  | 'draft'
  | 'planning'
  | 'active'
  | 'waiting_for_approval'
  | 'blocked'
  | 'verifying'
  | 'succeeded'
  | 'failed'
  | 'cancelled';

export interface Goal {
  id: GoalId;
  objective: string;
  constraints: JsonObject;
  priority: 'critical' | 'interactive' | 'normal' | 'background' | 'idle';
  privacyClass: PrivacyClass;
  status: GoalStatus;
  activeGraphRevisionId?: TaskGraphRevisionId;
  terminalReason?: string;
  version: number;
  createdAt: IsoTimestamp;
  updatedAt: IsoTimestamp;
  completedAt?: IsoTimestamp;
}

export interface GoalSuccessCriterion {
  id: GoalCriterionId;
  goalId: GoalId;
  description: string;
  required: boolean;
  verificationMethod: string;
  position: number;
  createdAt: IsoTimestamp;
}

export interface TaskGraphRevision {
  id: TaskGraphRevisionId;
  goalId: GoalId;
  revision: number;
  rationale?: string;
  createdAt: IsoTimestamp;
}

export type TaskStatus =
  | 'planned'
  | 'blocked'
  | 'ready'
  | 'waiting_for_approval'
  | 'scheduled'
  | 'running'
  | 'verifying'
  | 'retry_pending'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | 'superseded';

export interface Task {
  id: TaskId;
  goalId: GoalId;
  graphRevisionId: TaskGraphRevisionId;
  parentTaskId?: TaskId;
  title: string;
  objective: string;
  inputs: JsonObject;
  requiredCapabilities: readonly string[];
  privacyClass: PrivacyClass;
  priority: Goal['priority'];
  status: TaskStatus;
  required: boolean;
  retryPolicy: JsonObject;
  verificationPlan: JsonObject;
  terminalReason?: string;
  version: number;
  createdAt: IsoTimestamp;
  updatedAt: IsoTimestamp;
  completedAt?: IsoTimestamp;
}

export interface TaskDependency {
  graphRevisionId: TaskGraphRevisionId;
  predecessorTaskId: TaskId;
  successorTaskId: TaskId;
  condition: 'success' | 'completion' | 'predicate';
  predicate?: JsonObject;
  createdAt: IsoTimestamp;
}

export type AttemptStatus = 'created' | 'running' | 'succeeded' | 'failed' | 'cancelled' | 'indeterminate';

export interface Attempt {
  id: AttemptId;
  taskId: TaskId;
  attemptNumber: number;
  status: AttemptStatus;
  providerOfferingId?: string;
  computeNodeId?: string;
  inputSnapshot: JsonObject;
  result?: JsonObject;
  idempotencyKey?: string;
  startedAt?: IsoTimestamp;
  completedAt?: IsoTimestamp;
  createdAt: IsoTimestamp;
}

export interface Verification {
  id: VerificationId;
  taskId: TaskId;
  attemptId?: AttemptId;
  verdict: 'passed' | 'failed' | 'inconclusive' | 'requires_human_acceptance';
  planVersion: number;
  verifier: string;
  criterionResults: JsonObject;
  evidence: JsonObject;
  createdAt: IsoTimestamp;
}

export interface Failure {
  id: FailureId;
  taskId: TaskId;
  attemptId?: AttemptId;
  category:
    | 'transient_infrastructure'
    | 'resource_unavailable'
    | 'provider_or_capability_mismatch'
    | 'invalid_input_or_precondition'
    | 'policy_or_approval'
    | 'execution_defect'
    | 'verification_failure'
    | 'external_outcome_indeterminate'
    | 'cancelled_or_preempted'
    | 'unknown';
  code: string;
  summary: string;
  details: JsonObject;
  retryable: boolean;
  createdAt: IsoTimestamp;
}

export interface Approval {
  id: ApprovalId;
  goalId: GoalId;
  taskId?: TaskId;
  attemptId?: AttemptId;
  action: string;
  scope: JsonObject;
  actionDigest: string;
  decision: 'requested' | 'approved' | 'denied' | 'expired' | 'revoked';
  decidedBy?: string;
  requestedAt: IsoTimestamp;
  decidedAt?: IsoTimestamp;
  expiresAt?: IsoTimestamp;
}

export interface ArtifactMetadata {
  id: ArtifactId;
  logicalName: string;
  version: number;
  mediaType: string;
  storageReference: string;
  sha256: string;
  sizeBytes?: number;
  privacyClass: PrivacyClass;
  producerAttemptId?: AttemptId;
  provenance: JsonObject;
  createdAt: IsoTimestamp;
}

export interface AuditEventInput {
  id: EventId;
  aggregateType: string;
  aggregateId: string;
  eventType: string;
  eventVersion: number;
  actor: string;
  correlationId?: string;
  causationId?: EventId;
  occurredAt: IsoTimestamp;
  payload: JsonObject;
}

export interface AuditEvent extends AuditEventInput {
  sequence: number;
  previousHash?: string;
  eventHash: string;
}

export interface GoalBundle {
  goal: Goal;
  criteria: readonly GoalSuccessCriterion[];
}

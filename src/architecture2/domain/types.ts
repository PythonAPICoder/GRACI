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
  ProviderId, CapabilityId, ProviderOfferingId, QualificationId, HealthObservationId,
  ResolutionDecisionId,
  NodeId, OfferingLocationId, NodeHealthObservationId, ResourceSchedulingDecisionId, ResourceLeaseId,
  NodeInspectionId,
  WorkstationWorkloadEvaluationId,
  WorkstationAvailabilityPolicyApplicationId,
  FailureDiagnosisId,
  ChangedConditionEvidenceId,
  AlternativeRecoveryDecisionId,
  ReconciliationDecisionId,
  CircuitId, CircuitTransitionId, CircuitEvidenceId, CircuitProbeId,
  InputRevisionId, ReplanningDecisionId, ResearchRequestId, ResearchEvidenceId, ResearchDecisionId,
} from './ids.js';

export type IsoTimestamp = string;
export type JsonObject = Record<string, unknown>;
export type PrivacyClass = 'public' | 'internal' | 'personal' | 'confidential' | 'secret';

export interface RetryPolicy extends JsonObject {
  maxAttempts?: number;
  retryVerificationFailures?: boolean;
}

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
  retryPolicy: RetryPolicy;
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

export interface ReplanningReplacement {
  supersededTaskId: TaskId;
  replacementTaskIds: readonly TaskId[];
}

export interface ReplanningDecision {
  id: ReplanningDecisionId;
  goalId: GoalId;
  sourceGraphRevisionId: TaskGraphRevisionId;
  replacementGraphRevisionId: TaskGraphRevisionId;
  diagnosisId: FailureDiagnosisId;
  failureId: FailureId;
  sourceTaskId: TaskId;
  replacements: readonly ReplanningReplacement[];
  reason: string;
  actor: string;
  authorizedAt: IsoTimestamp;
  eventId: EventId;
}

export interface ResearchRequest {
  id: ResearchRequestId;
  goalId: GoalId;
  taskId: TaskId;
  attemptId: AttemptId;
  failureId: FailureId;
  diagnosisId: FailureDiagnosisId;
  question: string;
  purpose: string;
  requestedBy: string;
  requestedAt: IsoTimestamp;
  eventId: EventId;
}

export interface ResearchEvidence {
  id: ResearchEvidenceId;
  requestId: ResearchRequestId;
  supplierId: string;
  supplierType: string;
  suppliedAt: IsoTimestamp;
  source: string;
  reference: string;
  content: JsonObject;
  integrity?: JsonObject;
  recordedBy: string;
  recordedAt: IsoTimestamp;
  eventId: EventId;
}

export interface ResearchDecision {
  id: ResearchDecisionId;
  evidenceId: ResearchEvidenceId;
  decision: 'accepted' | 'rejected';
  actor: string;
  reason: string;
  decidedAt: IsoTimestamp;
  eventId: EventId;
}

export type ResearchRequestLifecycle = 'requested' | 'evidence_recorded' | 'accepted' | 'rejected';

export interface ResearchRequestInspection {
  request: ResearchRequest;
  lifecycle: ResearchRequestLifecycle;
  evidence: ReadonlyArray<{ evidence: ResearchEvidence; decision?: ResearchDecision }>;
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
  classification: 'transient' | 'permanent' | 'verification_failed' | 'approval_required' | 'external_outcome_indeterminate';
  code: string;
  summary: string;
  details: JsonObject;
  retryable: boolean;
  createdAt: IsoTimestamp;
}

export type FailureOutcomeCertainty =
  | 'proven_completed'
  | 'proven_unsuccessful'
  | 'indeterminate_external_outcome'
  | 'insufficient_or_malformed_evidence';

export type RecoveryDisposition =
  | 'terminal_failure'
  | 'retry_same_path'
  | 'alternative_offering_recommended'
  | 'alternative_node_recommended'
  | 'reconciliation_required'
  | 'approval_required'
  | 'input_revision_required'
  | 'replanning_recommended'
  | 'research_recommended';

export interface FailureDiagnosis {
  id: FailureDiagnosisId;
  failureId: FailureId;
  taskId: TaskId;
  attemptId?: AttemptId;
  verificationId?: VerificationId;
  approvalId?: ApprovalId;
  providerOfferingId?: string;
  computeNodeId?: string;
  offeringLocationId?: OfferingLocationId;
  cause: Failure['category'];
  outcomeCertainty: FailureOutcomeCertainty;
  retryable: boolean;
  retryReason: string;
  disposition: RecoveryDisposition;
  diagnosticReason: string;
  policyId: string;
  policyVersion: number;
  evidenceFingerprint: string;
  diagnosedBy: string;
  diagnosedAt: IsoTimestamp;
  eventId: EventId;
}

export interface ChangedConditionEvidence {
  id: ChangedConditionEvidenceId;
  diagnosisId: FailureDiagnosisId;
  conditionType: string;
  priorFactReference?: string;
  changedFactReference?: string;
  source: string;
  observedAt: IsoTimestamp;
  eventId: EventId;
}

export type AlternativeRecoveryDecisionDisposition = 'authorized' | 'no_candidate' | 'rejected';

export interface AlternativeRecoveryDecision {
  id: AlternativeRecoveryDecisionId;
  diagnosisId: FailureDiagnosisId;
  failureId: FailureId;
  taskId: TaskId;
  failedAttemptId: AttemptId;
  requestedDisposition: 'alternative_offering_recommended' | 'alternative_node_recommended';
  disposition: AlternativeRecoveryDecisionDisposition;
  reason: string;
  nextAttemptNumber?: number;
  failedOfferingId?: ProviderOfferingId;
  failedNodeId?: NodeId;
  failedLocationId?: OfferingLocationId;
  selectedOfferingId?: ProviderOfferingId;
  selectedNodeId?: NodeId;
  selectedLocationId?: OfferingLocationId;
  providerResolutionId?: ResolutionDecisionId;
  resourceSchedulingDecisionId?: ResourceSchedulingDecisionId;
  changedConditionEvidenceId?: ChangedConditionEvidenceId;
  actor: string;
  decidedAt: IsoTimestamp;
  eventId: EventId;
}

export type ReconciliationConclusion = 'proven_completed' | 'proven_not_completed' | 'remains_indeterminate';

export interface ReconciliationDecision {
  id: ReconciliationDecisionId;
  taskId: TaskId;
  attemptId: AttemptId;
  failureId: FailureId;
  diagnosisId: FailureDiagnosisId;
  providerId: string;
  providerVersion: number;
  operationId: string;
  evidence: JsonObject;
  evidenceFingerprint: string;
  conclusion: ReconciliationConclusion;
  reason: string;
  observationNumber: number;
  nextAttemptNumber?: number;
  verificationId?: VerificationId;
  actor: string;
  decidedAt: IsoTimestamp;
  eventId: EventId;
}

export interface InputRevision {
  id: InputRevisionId;
  taskId: TaskId;
  failedAttemptId: AttemptId;
  failureId: FailureId;
  diagnosisId: FailureDiagnosisId;
  priorInputs: JsonObject;
  priorInputsDigest: string;
  revisedInputs: JsonObject;
  revisedInputsDigest: string;
  nextAttemptNumber: number;
  actor: string;
  authorizedAt: IsoTimestamp;
  eventId: EventId;
}

export type CircuitTargetType = 'provider_offering' | 'node' | 'offering_location';
export type CircuitState = 'closed' | 'open' | 'half_open';

export interface CircuitBreakerPolicy {
  id: string;
  version: number;
  observationWindowMs: number;
  failureThreshold: number;
  cooldownMs: number;
  qualifyingCategories: readonly Failure['category'][];
}

export interface CircuitRecord {
  id: CircuitId;
  targetType: CircuitTargetType;
  targetId: string;
  state: CircuitState;
  policyId: string;
  policyVersion: number;
  observationWindowMs: number;
  failureThreshold: number;
  cooldownMs: number;
  qualifyingCategories: readonly Failure['category'][];
  openedAt?: IsoTimestamp;
  cooldownUntil?: IsoTimestamp;
  version: number;
  updatedAt: IsoTimestamp;
}

export interface CircuitTransition {
  id: CircuitTransitionId;
  circuitId: CircuitId;
  fromState: CircuitState;
  toState: CircuitState;
  reason: string;
  diagnosisId?: FailureDiagnosisId;
  verificationId?: VerificationId;
  probeId?: CircuitProbeId;
  occurredAt: IsoTimestamp;
  eventId: EventId;
}

export interface CircuitEvidence {
  id: CircuitEvidenceId;
  circuitId: CircuitId;
  diagnosisId: FailureDiagnosisId;
  observedAt: IsoTimestamp;
  eventId: EventId;
}

export interface CircuitProbe {
  id: CircuitProbeId;
  circuitId: CircuitId;
  status: 'active' | 'claimed' | 'consumed';
  authorizedAt: IsoTimestamp;
  claimedAt?: IsoTimestamp;
  consumedAt?: IsoTimestamp;
  taskId?: TaskId;
  attemptId?: AttemptId;
  attemptNumber?: number;
  providerOfferingId?: ProviderOfferingId;
  nodeId?: NodeId;
  locationId?: OfferingLocationId;
  providerResolutionId?: ResolutionDecisionId;
  resourceSchedulingDecisionId?: ResourceSchedulingDecisionId;
  verificationId?: VerificationId;
  failureDiagnosisId?: FailureDiagnosisId;
  eventId: EventId;
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

export interface Provider {
  id: ProviderId;
  adapterType: string;
  adapterVersion: string;
  configurationReference: string;
  createdAt: IsoTimestamp;
}

export interface Capability {
  id: CapabilityId;
  contractVersion: number;
  description: string;
  inputSchemaReference: string;
  outputSchemaReference: string;
  createdAt: IsoTimestamp;
}

export interface ProviderOffering {
  id: ProviderOfferingId;
  providerId: ProviderId;
  capabilityId: CapabilityId;
  contractVersion: number;
  modelIdentity?: string;
  privacyDestinations: readonly PrivacyClass[];
  permissions: readonly string[];
  features: readonly string[];
  supportedFormats: readonly string[];
  inputSchemaReference: string;
  outputSchemaReference: string;
  qualificationFingerprint: string;
  qualityLevel: number;
  expectedLatencyMs: number;
  maximumCost: number;
  sideEffectClass: 'none' | 'local' | 'external_reversible' | 'external_consequential';
  createdAt: IsoTimestamp;
}

export interface Qualification {
  id: QualificationId;
  offeringId: ProviderOfferingId;
  status: 'qualified' | 'rejected';
  level: number;
  evidence: JsonObject;
  qualifiedAt: IsoTimestamp;
  expiresAt?: IsoTimestamp;
  triggerFingerprint: string;
}

export interface ProviderHealthObservation {
  id: HealthObservationId;
  offeringId: ProviderOfferingId;
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  evidence: JsonObject;
  observedAt: IsoTimestamp;
}

export interface ProviderRegistration {
  provider: Provider;
  capabilities: readonly Capability[];
  offerings: readonly ProviderOffering[];
}

export type ResolutionRejectionReason =
  | 'contract_version_mismatch' | 'privacy_destination_disallowed' | 'permission_missing'
  | 'feature_missing' | 'qualification_missing' | 'qualification_rejected'
  | 'qualification_expired' | 'qualification_insufficient' | 'health_missing'
  | 'health_stale' | 'health_unacceptable' | 'qualification_fingerprint_mismatch'
  | 'input_schema_mismatch' | 'output_schema_mismatch' | 'format_unsupported'
  | 'side_effect_class_mismatch' | 'quality_insufficient' | 'latency_exceeded' | 'cost_exceeded'
  | 'explicitly_excluded' | 'circuit_open' | 'circuit_probe_required';

export interface ProviderResolutionRequest {
  id: ResolutionDecisionId;
  capabilityId: CapabilityId;
  contractVersion: number;
  privacyClass: PrivacyClass;
  requiredPermissions: readonly string[];
  requiredFeatures: readonly string[];
  requiredFormats?: readonly string[];
  inputSchemaReference?: string;
  outputSchemaReference?: string;
  maximumSideEffectClass?: ProviderOffering['sideEffectClass'];
  expectedQualificationFingerprint?: string;
  minimumQualificationLevel: number;
  minimumQualityLevel?: number;
  maximumLatencyMs?: number;
  maximumCost?: number;
  maximumHealthAgeMs: number;
  requestedAt: IsoTimestamp;
  excludedOfferingIds?: readonly ProviderOfferingId[];
  circuitProbeId?: CircuitProbeId;
}

export interface ProviderResolutionCandidate {
  offeringId: ProviderOfferingId;
  eligible: boolean;
  rejectionReasons: readonly ResolutionRejectionReason[];
  qualificationLevel?: number;
  healthObservedAt?: IsoTimestamp;
}

export interface ProviderResolutionDecision {
  request: ProviderResolutionRequest;
  candidates: readonly ProviderResolutionCandidate[];
  selectedOfferingId?: ProviderOfferingId;
  explanation: string;
  decidedAt: IsoTimestamp;
}

export interface Node {
  id: NodeId;
  name: string;
  administrativeState: 'active' | 'draining' | 'disabled';
  configurationReference: string;
  createdAt: IsoTimestamp;
}

export interface OfferingLocation {
  id: OfferingLocationId;
  nodeId: NodeId;
  offeringId: ProviderOfferingId;
  enabled: boolean;
  capacity: number;
  privacyClasses: readonly PrivacyClass[];
  createdAt: IsoTimestamp;
}

export interface NodeHealthObservation {
  id: NodeHealthObservationId;
  nodeId: NodeId;
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  observedAt: IsoTimestamp;
}

export interface NodeInspectionFailure {
  outcome: 'retryable_failure' | 'non_retryable_failure' | 'indeterminate_outcome';
  code: string;
  summary: string;
  httpStatus?: number;
}

export type NodeInspectionHealthOutcome =
  | { outcome: 'success'; version: string }
  | NodeInspectionFailure;

export interface NodeInspectionInventoryItem {
  name: string;
  modifiedAt?: string;
  size?: number;
  digest?: string;
}

export type NodeInspectionInventoryOutcome =
  | { outcome: 'success'; items: readonly NodeInspectionInventoryItem[] }
  | NodeInspectionFailure;

export interface NodeInspectionObservation {
  id: NodeInspectionId;
  nodeId: NodeId;
  adapterId: string;
  adapterVersion: number;
  health: NodeInspectionHealthOutcome;
  inventory: NodeInspectionInventoryOutcome;
  inspectedAt: IsoTimestamp;
}

export type ResourceSchedulingRejectionReason =
  | 'node_missing'
  | 'node_draining'
  | 'node_disabled'
  | 'location_disabled'
  | 'health_missing'
  | 'health_stale'
  | 'health_unacceptable'
  | 'privacy_incompatible'
  | 'capacity_insufficient'
  | 'node_explicitly_excluded'
  | 'location_explicitly_excluded'
  | 'node_circuit_open' | 'node_circuit_probe_required'
  | 'location_circuit_open' | 'location_circuit_probe_required';

export interface ResourceSchedulingRequest {
  id: ResourceSchedulingDecisionId;
  offeringId: ProviderOfferingId;
  privacyClass: PrivacyClass;
  requiredCapacity: number;
  maximumHealthAgeMs: number;
  requestedAt: IsoTimestamp;
  excludedNodeIds?: readonly NodeId[];
  excludedLocationIds?: readonly OfferingLocationId[];
  circuitProbeId?: CircuitProbeId;
}

export interface ResourceSchedulingCandidate {
  locationId: OfferingLocationId;
  nodeId: NodeId;
  eligible: boolean;
  rejectionReasons: readonly ResourceSchedulingRejectionReason[];
  availableCapacity: number;
  healthObservedAt?: IsoTimestamp;
}

export interface ResourceSchedulingDecision {
  request: ResourceSchedulingRequest;
  candidates: readonly ResourceSchedulingCandidate[];
  selectedLocationId?: OfferingLocationId;
  selectedNodeId?: NodeId;
  explanation: string;
  decidedAt: IsoTimestamp;
}

export interface ResourceLease {
  id: ResourceLeaseId;
  decisionId: ResourceSchedulingDecisionId;
  offeringId: ProviderOfferingId;
  locationId: OfferingLocationId;
  nodeId: NodeId;
  capacity: number;
  status: 'active' | 'released' | 'expired';
  acquiredAt: IsoTimestamp;
  expiresAt: IsoTimestamp;
  releasedAt?: IsoTimestamp;
}

export type WindowsProcessSnapshotIncompleteReason =
  | 'unsupported_platform'
  | 'execution_failed'
  | 'malformed_output'
  | 'truncated_output';

export type WindowsProcessSnapshot =
  | {
      completeness: 'complete';
      processBasenames: readonly string[];
      capturedAt: IsoTimestamp;
    }
  | {
      completeness: 'incomplete';
      processBasenames: readonly string[];
      reason: WindowsProcessSnapshotIncompleteReason;
      capturedAt: IsoTimestamp;
    };

export interface WorkstationWorkloadRule {
  id: string;
  executableBasenames: readonly string[];
}

export interface WorkstationWorkloadRules {
  version: number;
  rules: readonly WorkstationWorkloadRule[];
}

export interface WorkstationWorkloadEvaluation {
  id: WorkstationWorkloadEvaluationId;
  nodeId: NodeId;
  ruleFingerprint: string;
  processBasenames: readonly string[];
  matchedRuleIds: readonly string[];
  recommendation: 'recommend_draining' | 'recommend_active' | 'inconclusive';
  evaluatedAt: IsoTimestamp;
}

export type WorkstationAvailabilityPolicyDisposition =
  | 'applied_transition'
  | 'already_satisfied'
  | 'inconclusive'
  | 'stale_evidence'
  | 'state_version_mismatch'
  | 'rule_fingerprint_mismatch'
  | 'policy_ownership_mismatch'
  | 'disabled_node'
  | 'node_mismatch'
  | 'superseded_evidence'
  | 'invalid_evidence';

export interface WorkstationAvailabilityPolicyApplicationRequest {
  id: WorkstationAvailabilityPolicyApplicationId;
  evaluationId: WorkstationWorkloadEvaluationId;
  nodeId: NodeId;
  policyId: string;
  policyVersion: number;
  expectedRuleFingerprint: string;
  expectedNodeState: Node['administrativeState'];
  expectedNodeVersion: number;
  maximumEvidenceAgeMs: number;
  actor: string;
  reason: string;
  appliedAt: IsoTimestamp;
}

export interface WorkstationAvailabilityPolicyApplication {
  id: WorkstationAvailabilityPolicyApplicationId;
  evaluationId: WorkstationWorkloadEvaluationId;
  nodeId: NodeId;
  policyId: string;
  policyVersion: number;
  ruleFingerprint: string;
  actor: string;
  reason: string;
  expectedNodeState: Node['administrativeState'];
  expectedNodeVersion: number;
  observedNodeState: Node['administrativeState'];
  observedNodeVersion: number;
  recommendation: WorkstationWorkloadEvaluation['recommendation'];
  disposition: WorkstationAvailabilityPolicyDisposition;
  transitionOccurred: boolean;
  resultingNodeState?: Node['administrativeState'];
  resultingNodeVersion?: number;
  appliedAt: IsoTimestamp;
}

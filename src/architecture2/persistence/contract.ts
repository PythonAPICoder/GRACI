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
  Provider, Capability, ProviderOffering, ProviderRegistration, Qualification, ProviderHealthObservation,
  ProviderResolutionDecision,
  Node, OfferingLocation, NodeHealthObservation, NodeInspectionObservation, ResourceSchedulingDecision, ResourceLease,
  WorkstationWorkloadEvaluation, WorkstationAvailabilityPolicyApplication,
  WorkstationAvailabilityPolicyApplicationRequest,
  FailureDiagnosis, FailureDiagnosisId, FailureId, ChangedConditionEvidence,
  AlternativeRecoveryDecision, AlternativeRecoveryDecisionId,
  ReconciliationDecision, ReconciliationDecisionId,
  CircuitRecord, CircuitTransition, CircuitEvidence, CircuitProbe, CircuitBreakerPolicy, CircuitTargetType,
  InputRevision, InputRevisionId, ReplanningDecision, ReplanningDecisionId,
  ResearchRequest, ResearchRequestId, ResearchEvidence, ResearchEvidenceId, ResearchDecision, ResearchRequestInspection,
  ResearchRecoveryLink, ResearchProviderExecution,
  MemoryRecord, MemoryId, MemoryInspection, MemoryDecisionLink,
} from '../domain/index.js';

export interface LegacyImportOperation {
  id: string;
  sourceDigest: string;
  sourceReference: string;
  assessmentVersion: number;
  importedRecordCount: number;
  importedAt: string;
}

export interface LegacyHistoryRecord {
  importOperationId: string;
  sourceDigest: string;
  sourceReference: string;
  sourceSection: string;
  sourceKey: string;
  legacyStatus: string;
  payload: Record<string, unknown>;
  assessmentVersion: number;
  importedAt: string;
}

export interface LegacyImportWrite {
  operation: LegacyImportOperation;
  records: readonly LegacyHistoryRecord[];
}

export interface LegacyImportResult {
  operation: LegacyImportOperation;
  created: boolean;
  insertedRecordCount: number;
}

export interface Architecture2Persistence extends Disposable {
  initialize(): void;
  close(): void;
  getSchemaVersion(): number;

  registerProvider(value: ProviderRegistration, events: readonly AuditEventInput[]): void;
  getProvider(id: Provider['id']): Provider | undefined;
  getCapabilities(): Capability[];
  getProviderOfferings(capabilityId?: Capability['id']): ProviderOffering[];
  recordQualification(value: Qualification, event: AuditEventInput): void;
  getQualifications(offeringId: ProviderOffering['id']): Qualification[];
  recordProviderHealth(value: ProviderHealthObservation, event: AuditEventInput): void;
  getProviderHealth(offeringId: ProviderOffering['id']): ProviderHealthObservation[];
  recordProviderResolution(value: ProviderResolutionDecision, event: AuditEventInput): void;
  getProviderResolution(id: ProviderResolutionDecision['request']['id']): ProviderResolutionDecision | undefined;

  registerNode(node: Node, locations: readonly OfferingLocation[], events: readonly AuditEventInput[]): void;
  getNodes(): Array<Node & { version: number }>;
  getOfferingLocations(offeringId?: ProviderOffering['id']): OfferingLocation[];
  recordNodeHealth(value: NodeHealthObservation, event: AuditEventInput): void;
  getNodeHealth(nodeId: Node['id']): NodeHealthObservation[];
  recordNodeInspection(value: NodeInspectionObservation, event: AuditEventInput): void;
  getNodeInspections(nodeId: Node['id']): NodeInspectionObservation[];
  recordWorkstationWorkloadEvaluation(value: WorkstationWorkloadEvaluation, event: AuditEventInput): void;
  getWorkstationWorkloadEvaluations(nodeId: Node['id']): WorkstationWorkloadEvaluation[];
  applyWorkstationAvailabilityPolicy(request: WorkstationAvailabilityPolicyApplicationRequest,
    event: AuditEventInput): WorkstationAvailabilityPolicyApplication;
  getWorkstationAvailabilityPolicyApplications(nodeId: Node['id']): WorkstationAvailabilityPolicyApplication[];
  transitionNodeAdministrativeState(nodeId: Node['id'], expectedVersion: number,
    currentState: Node['administrativeState'], targetState: Node['administrativeState'], actor: string,
    reason: string, occurredAt: string, event: AuditEventInput): Node & { version: number };
  recordResourceSchedulingDecision(value: ResourceSchedulingDecision, lease: ResourceLease,
    events: readonly AuditEventInput[]): void;
  scheduleTaskWithResource(task: Task, expectedVersion: number, value: ResourceSchedulingDecision,
    lease: ResourceLease, events: readonly AuditEventInput[]): boolean;
  getResourceSchedulingDecision(id: ResourceSchedulingDecision['request']['id']): ResourceSchedulingDecision | undefined;
  getResourceLeases(locationId?: OfferingLocation['id']): ResourceLease[];
  releaseResourceLease(value: ResourceLease, event: AuditEventInput): void;

  importLegacyHistory(value: LegacyImportWrite): LegacyImportResult;
  getLegacyImport(sourceDigest: string): LegacyImportOperation | undefined;
  getLegacyHistory(sourceDigest?: string): LegacyHistoryRecord[];

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
  startAttempt(task: Task, expectedVersion: number, attempt: Attempt, events: readonly AuditEventInput[],
    recoveryDecisionId?: AlternativeRecoveryDecisionId, reconciliationDecisionId?: ReconciliationDecisionId,
    circuitProbeId?: CircuitProbe['id'], inputRevisionId?: InputRevisionId): void;
  recordAttemptOutcome(
    task: Task,
    expectedVersion: number,
    attempt: Attempt,
    failure: Failure | undefined,
    events: readonly AuditEventInput[],
    diagnosis?: FailureDiagnosis,
  ): void;
  recordVerificationOutcome(
    task: Task,
    expectedVersion: number,
    verification: Verification,
    failure: Failure | undefined,
    events: readonly AuditEventInput[],
    diagnosis?: FailureDiagnosis,
  ): void;
  recordTaskFailure(task: Task, expectedVersion: number, failure: Failure, events: readonly AuditEventInput[],
    diagnosis?: FailureDiagnosis): void;
  createVerification(verification: Verification, event: AuditEventInput): void;
  getVerifications(taskId: TaskId): Verification[];
  createFailure(failure: Failure, event: AuditEventInput): void;
  getFailure(id: FailureId): Failure | undefined;
  getFailures(taskId: TaskId): Failure[];
  recordFailureDiagnosis(diagnosis: FailureDiagnosis, event: AuditEventInput): FailureDiagnosis;
  getFailureDiagnosis(failureId: FailureId, policyId: string, policyVersion: number): FailureDiagnosis | undefined;
  getFailureDiagnosisById(id: FailureDiagnosisId): FailureDiagnosis | undefined;
  getFailureDiagnoses(taskId: TaskId): FailureDiagnosis[];
  recordChangedConditionEvidence(value: ChangedConditionEvidence, event: AuditEventInput): void;
  getChangedConditionEvidence(diagnosisId: FailureDiagnosisId): ChangedConditionEvidence[];
  recordAlternativeRecoveryDecision(value: AlternativeRecoveryDecision, evidence: ChangedConditionEvidence | undefined,
    task: Task | undefined, expectedTaskVersion: number | undefined, events: readonly AuditEventInput[]): AlternativeRecoveryDecision;
  getAlternativeRecoveryDecision(diagnosisId: FailureDiagnosisId): AlternativeRecoveryDecision | undefined;
  getPendingAlternativeRecovery(taskId: TaskId): AlternativeRecoveryDecision | undefined;
  recordReconciliationDecision(value: ReconciliationDecision, task: Task | undefined,
    expectedTaskVersion: number | undefined, verification: Verification | undefined, failure: Failure | undefined,
    diagnosis: FailureDiagnosis | undefined, events: readonly AuditEventInput[]): ReconciliationDecision;
  getReconciliationDecision(id: ReconciliationDecisionId): ReconciliationDecision | undefined;
  getReconciliationDecisions(diagnosisId: FailureDiagnosisId): ReconciliationDecision[];
  getPendingReconciliation(taskId: TaskId): ReconciliationDecision | undefined;
  authorizeInputRevision(value: InputRevision, task: Task, expectedTaskVersion: number,
    event: AuditEventInput, researchEvidenceId?: ResearchEvidenceId,
    memoryIds?: readonly MemoryId[]): InputRevision;
  getInputRevision(id: InputRevisionId): InputRevision | undefined;
  getInputRevisionByDiagnosis(diagnosisId: FailureDiagnosisId): InputRevision | undefined;
  getPendingInputRevision(taskId: TaskId): InputRevision | undefined;
  getMemoryDecisionLinksByInputRevision(id: InputRevisionId): MemoryDecisionLink[];
  authorizeReplanning(value: ReplanningDecision, revision: TaskGraphRevision, tasks: readonly Task[],
    dependencies: readonly TaskDependency[], expectedGoalVersion: number, events: readonly AuditEventInput[],
    researchEvidenceId?: ResearchEvidenceId, memoryIds?: readonly MemoryId[]): ReplanningDecision;
  getReplanningDecision(id: ReplanningDecisionId): ReplanningDecision | undefined;
  getReplanningDecisionByDiagnosis(diagnosisId: FailureDiagnosisId): ReplanningDecision | undefined;
  getReplanningDecisions(goalId: GoalId): ReplanningDecision[];
  getMemoryDecisionLinksByReplanningDecision(id: ReplanningDecisionId): MemoryDecisionLink[];
  createResearchRequest(value: ResearchRequest, event: AuditEventInput): ResearchRequest;
  getResearchRequest(id: ResearchRequestId): ResearchRequest | undefined;
  inspectResearchRequest(id: ResearchRequestId): ResearchRequestInspection | undefined;
  recordResearchEvidence(value: ResearchEvidence, event: AuditEventInput): ResearchEvidence;
  getResearchEvidence(id: ResearchEvidenceId): ResearchEvidence | undefined;
  decideResearchEvidence(value: ResearchDecision, event: AuditEventInput): ResearchDecision;
  getAcceptedResearchEvidence(requestId: ResearchRequestId): ResearchEvidence[];
  startResearchProviderExecution(value: ResearchProviderExecution, event: AuditEventInput): ResearchProviderExecution;
  completeResearchProviderExecution(value: ResearchProviderExecution, evidence: ResearchEvidence | undefined,
    events: readonly AuditEventInput[]): ResearchProviderExecution;
  getResearchProviderExecutions(requestId: ResearchRequestId): ResearchProviderExecution[];
  storeMemory(value: MemoryRecord, event: AuditEventInput): MemoryRecord;
  retrieveMemories(goalId: GoalId, includeReusable: boolean, asOf: string): MemoryRecord[];
  inspectMemory(id: MemoryId): MemoryInspection | undefined;
  supersedeMemory(expectedCurrentId: MemoryId, replacement: MemoryRecord,
    events: readonly AuditEventInput[]): MemoryRecord;
  getResearchRecoveryLinkByInputRevision(id: InputRevisionId): ResearchRecoveryLink | undefined;
  getResearchRecoveryLinkByReplanningDecision(id: ReplanningDecisionId): ResearchRecoveryLink | undefined;
  recordCircuitEvidence(targetType: CircuitTargetType, targetId: string, diagnosis: FailureDiagnosis,
    policy: CircuitBreakerPolicy, evidence: CircuitEvidence, transition: CircuitTransition | undefined,
    event: AuditEventInput): CircuitRecord;
  acquireCircuitProbe(circuitId: CircuitRecord['id'], probe: CircuitProbe, transition: CircuitTransition,
    events: readonly AuditEventInput[]): CircuitProbe;
  claimCircuitProbe(probe: CircuitProbe, event: AuditEventInput): CircuitProbe;
  recordCircuitProbeOutcome(probeId: CircuitProbe['id'], verification: Verification | undefined,
    diagnosis: FailureDiagnosis | undefined, transition: CircuitTransition, events: readonly AuditEventInput[]): CircuitRecord;
  getCircuits(): CircuitRecord[];
  getCircuitTransitions(circuitId: CircuitRecord['id']): CircuitTransition[];
  getCircuitEvidence(circuitId: CircuitRecord['id']): CircuitEvidence[];
  getCircuitProbes(circuitId: CircuitRecord['id']): CircuitProbe[];
  createApproval(approval: Approval, event: AuditEventInput): void;
  getApprovals(taskId: TaskId): Approval[];
  recordApprovalPause(task: Task, expectedVersion: number, attempt: Attempt, failure: Failure,
    approval: Approval, events: readonly AuditEventInput[], diagnosis?: FailureDiagnosis): void;
  recordApprovalDecision(task: Task, expectedVersion: number, approval: Approval,
    events: readonly AuditEventInput[]): void;
  createArtifact(artifact: ArtifactMetadata, event: AuditEventInput): void;

  appendEvent(event: AuditEventInput): AuditEvent;
  getEvents(afterSequence?: number): AuditEvent[];
}

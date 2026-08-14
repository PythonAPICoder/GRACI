import { randomUUID } from 'node:crypto';
import { asIdentifier, type FailureId, type TaskGraphRevisionId, type TaskId } from '../domain/index.js';
import type { TaskExecutionProvider } from '../execution/index.js';
import { assessLegacyState, importLegacyState, type LegacyImportOptions } from '../legacy/index.js';
import { SqliteArchitecture2Persistence } from '../persistence/index.js';
import type { TaskVerifier } from '../verification/index.js';
import { reconcileExternalOutcome, type ReconciliationCommand,
  type ReconciliationProvider } from '../reconciliation/index.js';
import { diagnosePersistedFailure, inspectQueue, MinimalOrchestrator, recoverWithAlternative,
  acquireCircuitProbe, claimCircuitProbe, inspectCircuits, recordCircuitFailure, recordCircuitProbeOutcome,
  authorizeInputRevision, authorizeReplanning, createResearchRequest, recordResearchEvidence, decideResearchEvidence,
  executeResearchRequest,
  type AcquireCircuitProbeCommand, type AlternativeRecoveryCommand, type OrchestratorOptions,
  type ClaimCircuitProbeCommand, type RecordCircuitFailureCommand, type RecordCircuitProbeOutcomeCommand,
  type AuthorizeInputRevisionCommand, type AuthorizeReplanningCommand, type CreateResearchRequestCommand,
  type RecordResearchEvidenceCommand, type DecideResearchEvidenceCommand, type ExecuteResearchRequestCommand,
  type ExecuteResearchRequestOptions } from '../workflow/index.js';

export interface Architecture2RuntimeConfiguration {
  databasePath: string;
  executionProvider: TaskExecutionProvider;
  verifier: TaskVerifier;
  orchestrator?: OrchestratorOptions;
}

export class Architecture2Runtime implements Disposable {
  readonly persistence: SqliteArchitecture2Persistence;
  readonly orchestrator: MinimalOrchestrator;
  private readonly verifier: TaskVerifier;

  constructor(configuration: Architecture2RuntimeConfiguration) {
    this.persistence = new SqliteArchitecture2Persistence({ databasePath: configuration.databasePath });
    this.persistence.initialize();
    this.verifier = configuration.verifier;
    this.orchestrator = new MinimalOrchestrator(this.persistence,
      configuration.executionProvider, configuration.verifier, configuration.orchestrator);
  }

  run(graphRevisionId: TaskGraphRevisionId) {
    return this.orchestrator.run(graphRevisionId);
  }

  inspect(graphRevisionId: TaskGraphRevisionId) {
    return inspectQueue(this.persistence, graphRevisionId);
  }

  approveTask(taskId: TaskId, decidedBy?: string) {
    return this.orchestrator.approveTask(taskId, decidedBy);
  }

  denyTask(taskId: TaskId, reason: string, decidedBy?: string) {
    return this.orchestrator.denyTask(taskId, reason, decidedBy);
  }

  diagnoseFailure(failureId: FailureId, diagnosedBy = 'architecture2-failure-diagnoser',
    diagnosedAt = new Date().toISOString()) {
    return diagnosePersistedFailure(this.persistence, { failureId, diagnosedBy, diagnosedAt,
      eventId: asIdentifier<'Event'>(`event-${randomUUID()}`) });
  }

  recoverAlternative(command: AlternativeRecoveryCommand) {
    return recoverWithAlternative(this.persistence, command);
  }

  reconcile(provider: ReconciliationProvider, command: ReconciliationCommand) {
    return reconcileExternalOutcome(this.persistence, this.verifier, provider, command);
  }

  authorizeInputRevision(command: AuthorizeInputRevisionCommand) {
    return authorizeInputRevision(this.persistence, command);
  }

  inspectInputRevision(id: AuthorizeInputRevisionCommand['id']) {
    return this.persistence.getInputRevision(id);
  }

  inspectInputRevisionResearchSupport(id: AuthorizeInputRevisionCommand['id']) {
    return this.persistence.getResearchRecoveryLinkByInputRevision(id);
  }

  authorizeReplanning(command: AuthorizeReplanningCommand) {
    return authorizeReplanning(this.persistence, command);
  }

  inspectReplanningDecision(id: AuthorizeReplanningCommand['id']) {
    return this.persistence.getReplanningDecision(id);
  }

  inspectReplanningResearchSupport(id: AuthorizeReplanningCommand['id']) {
    return this.persistence.getResearchRecoveryLinkByReplanningDecision(id);
  }

  inspectGraphRevisions(goalId: Parameters<SqliteArchitecture2Persistence['getTaskGraphRevisions']>[0]) {
    return { goal: this.persistence.getGoal(goalId)?.goal,
      revisions: this.persistence.getTaskGraphRevisions(goalId), decisions: this.persistence.getReplanningDecisions(goalId) };
  }

  createResearchRequest(command: CreateResearchRequestCommand) {
    return createResearchRequest(this.persistence, command);
  }

  inspectResearchRequest(id: CreateResearchRequestCommand['id']) {
    return this.persistence.inspectResearchRequest(id);
  }

  recordResearchEvidence(command: RecordResearchEvidenceCommand) {
    return recordResearchEvidence(this.persistence, command);
  }

  acceptResearchEvidence(command: Omit<DecideResearchEvidenceCommand, 'decision'>) {
    return decideResearchEvidence(this.persistence, { ...command, decision: 'accepted' });
  }

  rejectResearchEvidence(command: Omit<DecideResearchEvidenceCommand, 'decision'>) {
    return decideResearchEvidence(this.persistence, { ...command, decision: 'rejected' });
  }

  inspectAcceptedResearchEvidence(requestId: CreateResearchRequestCommand['id']) {
    return this.persistence.getAcceptedResearchEvidence(requestId);
  }

  executeResearchRequest(command: ExecuteResearchRequestCommand, options: ExecuteResearchRequestOptions) {
    return executeResearchRequest(this.persistence, command, options);
  }

  inspectResearchProviderExecutions(requestId: CreateResearchRequestCommand['id']) {
    return this.persistence.getResearchProviderExecutions(requestId);
  }

  inspectCircuits() {
    return inspectCircuits(this.persistence);
  }

  recordCircuitFailure(command: RecordCircuitFailureCommand) {
    return recordCircuitFailure(this.persistence, command);
  }

  acquireCircuitProbe(command: AcquireCircuitProbeCommand) {
    return acquireCircuitProbe(this.persistence, command);
  }

  claimCircuitProbe(command: ClaimCircuitProbeCommand) {
    return claimCircuitProbe(this.persistence, command);
  }

  recordCircuitProbeOutcome(command: RecordCircuitProbeOutcomeCommand) {
    return recordCircuitProbeOutcome(this.persistence, command);
  }

  assessLegacy(sourceReference: string) {
    return assessLegacyState(sourceReference);
  }

  importLegacy(sourceReference: string, options?: LegacyImportOptions) {
    return importLegacyState(this.assessLegacy(sourceReference), this.persistence, options);
  }

  close(): void {
    this.persistence.close();
  }

  [Symbol.dispose](): void {
    this.close();
  }
}

export function bootstrapArchitecture2(configuration: Architecture2RuntimeConfiguration): Architecture2Runtime {
  return new Architecture2Runtime(configuration);
}

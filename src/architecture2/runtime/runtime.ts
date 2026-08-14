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
  type AcquireCircuitProbeCommand, type AlternativeRecoveryCommand, type OrchestratorOptions,
  type ClaimCircuitProbeCommand, type RecordCircuitFailureCommand, type RecordCircuitProbeOutcomeCommand } from '../workflow/index.js';

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

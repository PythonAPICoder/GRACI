import type { TaskGraphRevisionId, TaskId } from '../domain/index.js';
import type { TaskExecutionProvider } from '../execution/index.js';
import { assessLegacyState, importLegacyState, type LegacyImportOptions } from '../legacy/index.js';
import { SqliteArchitecture2Persistence } from '../persistence/index.js';
import type { TaskVerifier } from '../verification/index.js';
import { inspectQueue, MinimalOrchestrator, type OrchestratorOptions } from '../workflow/index.js';

export interface Architecture2RuntimeConfiguration {
  databasePath: string;
  executionProvider: TaskExecutionProvider;
  verifier: TaskVerifier;
  orchestrator?: OrchestratorOptions;
}

export class Architecture2Runtime implements Disposable {
  readonly persistence: SqliteArchitecture2Persistence;
  readonly orchestrator: MinimalOrchestrator;

  constructor(configuration: Architecture2RuntimeConfiguration) {
    this.persistence = new SqliteArchitecture2Persistence({ databasePath: configuration.databasePath });
    this.persistence.initialize();
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

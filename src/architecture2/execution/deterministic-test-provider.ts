import type { TaskId } from '../domain/index.js';
import type { TaskExecutionProvider, TaskExecutionRequest, TaskExecutionResult } from './contract.js';

export type DeterministicBehavior =
  | { outcome: 'success'; verificationPasses: boolean }
  | { outcome: 'failure'; code?: string; summary?: string };

export class DeterministicTestProvider implements TaskExecutionProvider {
  readonly providerId = 'in-process-deterministic-test-provider';
  private readonly counts = new Map<TaskId, number>();

  constructor(private readonly behaviors: ReadonlyMap<TaskId, DeterministicBehavior> = new Map()) {}

  async execute(request: TaskExecutionRequest): Promise<TaskExecutionResult> {
    this.counts.set(request.taskId, this.getExecutionCount(request.taskId) + 1);
    const behavior = this.behaviors.get(request.taskId) ?? { outcome: 'success', verificationPasses: true };
    if (behavior.outcome === 'failure') {
      return {
        status: 'failed',
        code: behavior.code ?? 'DETERMINISTIC_EXECUTION_FAILURE',
        summary: behavior.summary ?? 'Deterministic test provider failure',
        details: { providerId: this.providerId },
      };
    }
    return {
      status: 'succeeded',
      output: { taskId: request.taskId, attemptNumber: request.attemptNumber },
      evidence: { deterministic: true, verificationPasses: behavior.verificationPasses },
    };
  }

  getExecutionCount(taskId: TaskId): number {
    return this.counts.get(taskId) ?? 0;
  }
}

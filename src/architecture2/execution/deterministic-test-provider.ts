import type { TaskId } from '../domain/index.js';
import type { TaskExecutionProvider, TaskExecutionRequest, TaskExecutionResult } from './contract.js';

export type DeterministicBehavior =
  | { outcome: 'success'; verificationPasses: boolean }
  | { outcome: 'failure'; classification?: 'transient' | 'permanent' | 'approval_required'; code?: string; summary?: string };

export class DeterministicTestProvider implements TaskExecutionProvider {
  readonly providerId = 'in-process-deterministic-test-provider';
  private readonly counts = new Map<TaskId, number>();

  constructor(private readonly behaviors: ReadonlyMap<TaskId, DeterministicBehavior | readonly DeterministicBehavior[]> = new Map()) {}

  async execute(request: TaskExecutionRequest): Promise<TaskExecutionResult> {
    const count = this.getExecutionCount(request.taskId) + 1;
    this.counts.set(request.taskId, count);
    const configured = this.behaviors.get(request.taskId);
    const behavior = (Array.isArray(configured) ? configured[Math.min(count - 1, configured.length - 1)] : configured)
      ?? { outcome: 'success', verificationPasses: true };
    if (behavior.outcome === 'failure') {
      return {
        status: 'failed',
        classification: behavior.classification ?? 'permanent',
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

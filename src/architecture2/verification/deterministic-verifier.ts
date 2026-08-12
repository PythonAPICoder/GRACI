import type { JsonObject, Task, Verification } from '../domain/index.js';
import type { TaskExecutionResult } from '../execution/index.js';

export interface VerificationDecision {
  verdict: Verification['verdict'];
  criterionResults: JsonObject;
  evidence: JsonObject;
}

export interface TaskVerifier {
  readonly verifierId: string;
  verify(task: Task, result: Extract<TaskExecutionResult, { status: 'succeeded' }>): VerificationDecision;
}

export class DeterministicVerifier implements TaskVerifier {
  readonly verifierId = 'deterministic-phase1b-verifier';

  verify(task: Task, result: Extract<TaskExecutionResult, { status: 'succeeded' }>): VerificationDecision {
    const passed = result.evidence.verificationPasses === true;
    return {
      verdict: passed ? 'passed' : 'failed',
      criterionResults: { deterministicEvidenceAccepted: passed, taskId: task.id },
      evidence: { ...result.evidence, output: result.output },
    };
  }
}

import type { AttemptId, JsonObject, TaskId } from '../domain/index.js';

export interface TaskExecutionRequest {
  taskId: TaskId;
  attemptId: AttemptId;
  attemptNumber: number;
  objective: string;
  inputs: JsonObject;
  requiredCapabilities: readonly string[];
}

export type TaskExecutionResult =
  | { status: 'succeeded'; output: JsonObject; evidence: JsonObject }
  | { status: 'failed'; code: string; summary: string; details: JsonObject };

export interface TaskExecutionProvider {
  readonly providerId: string;
  execute(request: TaskExecutionRequest): Promise<TaskExecutionResult>;
}

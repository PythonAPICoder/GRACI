import type { Attempt, AuditEventInput, Task, TaskStatus, Verification } from '../domain/index.js';
import type { Architecture2Persistence } from '../persistence/index.js';

export interface TaskTransitionContext {
  dependenciesSatisfied?: boolean;
  attempt?: Attempt;
  verification?: Verification;
  terminalReason?: string;
}

export class InvalidTaskTransitionError extends Error {
  constructor(from: TaskStatus, to: TaskStatus, reason?: string) {
    super(`Invalid task transition ${from} -> ${to}${reason ? `: ${reason}` : ''}`);
    this.name = 'InvalidTaskTransitionError';
  }
}

const TERMINAL = new Set<TaskStatus>(['succeeded', 'failed', 'cancelled', 'superseded']);

export const TASK_TRANSITIONS: Readonly<Record<TaskStatus, readonly TaskStatus[]>> = {
  planned: ['blocked', 'ready', 'cancelled', 'superseded'],
  blocked: ['ready', 'failed', 'cancelled', 'superseded'],
  ready: ['scheduled', 'failed', 'cancelled', 'superseded'],
  waiting_for_approval: ['ready', 'failed', 'cancelled', 'superseded'],
  scheduled: ['running', 'failed', 'cancelled'],
  running: ['verifying', 'failed', 'cancelled'],
  verifying: ['succeeded', 'failed', 'cancelled'],
  retry_pending: ['blocked', 'ready', 'failed', 'cancelled', 'superseded'],
  succeeded: [],
  failed: [],
  cancelled: [],
  superseded: [],
};

export class TaskStateMachine {
  prepare(task: Task, target: TaskStatus, now: string, context: TaskTransitionContext = {}): Task {
    if (!TASK_TRANSITIONS[task.status].includes(target)) {
      throw new InvalidTaskTransitionError(task.status, target);
    }
    if (target === 'ready' && context.dependenciesSatisfied !== true) {
      throw new InvalidTaskTransitionError(task.status, target, 'required dependencies are not satisfied');
    }
    if (target === 'running' && (!context.attempt || context.attempt.taskId !== task.id || context.attempt.status !== 'running')) {
      throw new InvalidTaskTransitionError(task.status, target, 'a persisted running Attempt is required');
    }
    if (target === 'verifying' && (!context.attempt || context.attempt.taskId !== task.id || context.attempt.status !== 'succeeded')) {
      throw new InvalidTaskTransitionError(task.status, target, 'a successful Attempt is required');
    }
    if (task.status === 'running' && target === 'failed' &&
      (!context.attempt || context.attempt.taskId !== task.id ||
       !['failed', 'indeterminate'].includes(context.attempt.status))) {
      throw new InvalidTaskTransitionError(task.status, target, 'a failed or indeterminate Attempt is required');
    }
    if (task.status === 'verifying' && target === 'failed' &&
      (!context.verification || context.verification.taskId !== task.id || context.verification.verdict === 'passed')) {
      throw new InvalidTaskTransitionError(task.status, target, 'a rejecting Verification is required');
    }
    if (target === 'succeeded' &&
      (!context.verification || context.verification.taskId !== task.id || context.verification.verdict !== 'passed')) {
      throw new InvalidTaskTransitionError(task.status, target, 'a passing Verification is required');
    }
    if (TERMINAL.has(target) && target !== 'succeeded' && !context.terminalReason?.trim()) {
      throw new InvalidTaskTransitionError(task.status, target, 'a terminal reason is required');
    }

    return {
      ...task,
      status: target,
      terminalReason: TERMINAL.has(target) ? context.terminalReason : context.terminalReason,
      version: task.version + 1,
      updatedAt: now,
      completedAt: TERMINAL.has(target) ? now : undefined,
    };
  }

  transition(
    persistence: Architecture2Persistence,
    task: Task,
    target: TaskStatus,
    now: string,
    event: AuditEventInput,
    context: TaskTransitionContext = {},
  ): Task {
    const updated = this.prepare(task, target, now, context);
    persistence.updateTask(updated, task.version, event);
    return updated;
  }
}

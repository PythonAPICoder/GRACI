import { randomUUID } from 'node:crypto';
import {
  asIdentifier,
  type Attempt,
  type AuditEventInput,
  type Failure,
  type JsonObject,
  type Task,
  type TaskGraphRevisionId,
  type TaskId,
  type Verification,
} from '../domain/index.js';
import type { TaskExecutionProvider, TaskExecutionResult } from '../execution/index.js';
import type { Architecture2Persistence } from '../persistence/index.js';
import type { TaskVerifier } from '../verification/index.js';
import { evaluateTaskDependencies, graphHasTerminalCondition } from './dependency-evaluator.js';
import { TaskStateMachine } from './task-state-machine.js';

export type WorkflowRunStatus = 'succeeded' | 'failed' | 'incomplete';

export interface WorkflowRunResult {
  graphRevisionId: TaskGraphRevisionId;
  status: WorkflowRunStatus;
  terminal: boolean;
  executedTaskIds: TaskId[];
  tasks: Array<Pick<Task, 'id' | 'status' | 'terminalReason' | 'version'>>;
}

export interface OrchestratorOptions {
  actor?: string;
  now?: () => string;
  nextId?: (kind: 'attempt' | 'verification' | 'failure' | 'event') => string;
}

export class MinimalOrchestrator {
  private readonly stateMachine = new TaskStateMachine();
  private readonly actor: string;
  private readonly now: () => string;
  private readonly nextId: NonNullable<OrchestratorOptions['nextId']>;

  constructor(
    private readonly persistence: Architecture2Persistence,
    private readonly provider: TaskExecutionProvider,
    private readonly verifier: TaskVerifier,
    options: OrchestratorOptions = {},
  ) {
    this.actor = options.actor ?? 'architecture2-orchestrator';
    this.now = options.now ?? (() => new Date().toISOString());
    this.nextId = options.nextId ?? ((kind) => `${kind}-${randomUUID()}`);
  }

  async run(graphRevisionId: TaskGraphRevisionId): Promise<WorkflowRunResult> {
    const executedTaskIds: TaskId[] = [];
    this.recoverInterruptedWork(graphRevisionId);

    while (true) {
      this.evaluateAndPersistEligibility(graphRevisionId);
      const runnable = this.persistence.getTasks(graphRevisionId).find((task) => task.status === 'ready');
      if (!runnable) break;
      await this.executeTask(runnable);
      executedTaskIds.push(runnable.id);
    }

    const tasks = this.persistence.getTasks(graphRevisionId);
    const requiredFailure = tasks.some((task) => task.required &&
      (task.status === 'failed' || task.status === 'cancelled' ||
       (task.status === 'blocked' && task.terminalReason === 'required_dependency_failed')));
    const allRequiredSucceeded = tasks.filter((task) => task.required).every((task) => task.status === 'succeeded');
    return {
      graphRevisionId,
      status: allRequiredSucceeded ? 'succeeded' : requiredFailure ? 'failed' : 'incomplete',
      terminal: graphHasTerminalCondition(tasks),
      executedTaskIds,
      tasks: tasks.map(({ id, status, terminalReason, version }) => ({ id, status, terminalReason, version })),
    };
  }

  private recoverInterruptedWork(graphRevisionId: TaskGraphRevisionId): void {
    for (const task of this.persistence.getTasks(graphRevisionId)) {
      if (task.status !== 'running' && task.status !== 'scheduled') continue;
      const now = this.now();
      const attempts = this.persistence.getAttempts(task.id);
      const runningAttempt = attempts.slice().reverse().find((attempt) => attempt.status === 'running');
      if (task.status === 'running' && !runningAttempt) {
        throw new Error(`Interrupted running task ${task.id} has no persisted running Attempt`);
      }
      const recoveredAttempt: Attempt | undefined = runningAttempt ? {
        ...runningAttempt,
        status: 'indeterminate',
        result: { recovery: 'outcome_indeterminate' },
        completedAt: now,
      } : undefined;
      const failure = this.failure(task, runningAttempt, 'external_outcome_indeterminate',
        task.status === 'running' ? 'INTERRUPTED_RUNNING_ATTEMPT' : 'INTERRUPTED_SCHEDULED_TASK',
        task.status === 'running'
          ? 'Execution was interrupted and its outcome cannot be proven'
          : 'Scheduling was interrupted before execution could be proven',
        { recoveredFromState: task.status }, now);
      const failedTask = this.stateMachine.prepare(task, 'failed', now, {
        attempt: recoveredAttempt,
        terminalReason: failure.code,
      });
      const events = [
        this.event(task.id, 'failure.recorded', { failureId: failure.id, code: failure.code }, now),
        this.event(task.id, 'task.transitioned', { from: task.status, to: 'failed', reason: failure.code }, now),
      ];
      if (recoveredAttempt) {
        this.persistence.recordAttemptOutcome(failedTask, task.version, recoveredAttempt, failure, [
          this.event(task.id, 'attempt.indeterminate', { attemptId: recoveredAttempt.id }, now),
          ...events,
        ]);
      } else {
        this.persistence.recordTaskFailure(failedTask, task.version, failure, events);
      }
    }
  }

  private evaluateAndPersistEligibility(graphRevisionId: TaskGraphRevisionId): void {
    let tasks = this.persistence.getTasks(graphRevisionId);
    const dependencies = this.persistence.getTaskDependencies(graphRevisionId);
    for (const original of tasks) {
      if (original.status !== 'planned') continue;
      const current = this.persistence.getTask(original.id);
      if (!current || current.status !== 'planned') continue;
      const evaluation = evaluateTaskDependencies(current, tasks, dependencies);
      const now = this.now();
      if (evaluation.disposition === 'ready') {
        this.stateMachine.transition(this.persistence, current, 'ready', now,
          this.event(current.id, 'task.transitioned', { from: 'planned', to: 'ready' }, now),
          { dependenciesSatisfied: true });
      } else if (evaluation.disposition === 'blocked_by_failure') {
        this.stateMachine.transition(this.persistence, current, 'blocked', now,
          this.event(current.id, 'task.transitioned', {
            from: 'planned', to: 'blocked', reason: 'required_dependency_failed',
            blockingTaskIds: evaluation.blockingTaskIds,
          }, now), { terminalReason: 'required_dependency_failed' });
      }
      tasks = this.persistence.getTasks(graphRevisionId);
    }
  }

  private async executeTask(task: Task): Promise<void> {
    const scheduledAt = this.now();
    const scheduled = this.stateMachine.transition(this.persistence, task, 'scheduled', scheduledAt,
      this.event(task.id, 'task.transitioned', { from: 'ready', to: 'scheduled' }, scheduledAt));
    const attempts = this.persistence.getAttempts(task.id);
    const attemptNumber = (attempts.at(-1)?.attemptNumber ?? 0) + 1;
    const startedAt = this.now();
    const attempt: Attempt = {
      id: asIdentifier<'Attempt'>(this.nextId('attempt')),
      taskId: task.id,
      attemptNumber,
      status: 'running',
      providerOfferingId: this.provider.providerId,
      inputSnapshot: { objective: task.objective, inputs: task.inputs, requiredCapabilities: task.requiredCapabilities },
      startedAt,
      createdAt: startedAt,
    };
    const running = this.stateMachine.prepare(scheduled, 'running', startedAt, { attempt });
    this.persistence.startAttempt(running, scheduled.version, attempt, [
      this.event(task.id, 'attempt.started', { attemptId: attempt.id, attemptNumber }, startedAt),
      this.event(task.id, 'task.transitioned', { from: 'scheduled', to: 'running' }, startedAt),
    ]);

    let result: TaskExecutionResult;
    try {
      result = await this.provider.execute({ taskId: task.id, attemptId: attempt.id, attemptNumber,
        objective: task.objective, inputs: task.inputs, requiredCapabilities: task.requiredCapabilities });
    } catch (error) {
      result = { status: 'failed', code: 'PROVIDER_EXCEPTION', summary: 'Execution provider threw an exception',
        details: { message: error instanceof Error ? error.message : String(error) } };
    }

    const completedAt = this.now();
    if (result.status === 'failed') {
      const failedAttempt: Attempt = { ...attempt, status: 'failed', result: { ...result }, completedAt };
      const failure = this.failure(running, failedAttempt, 'execution_defect', result.code, result.summary, result.details, completedAt);
      const failedTask = this.stateMachine.prepare(running, 'failed', completedAt, { attempt: failedAttempt, terminalReason: failure.code });
      this.persistence.recordAttemptOutcome(failedTask, running.version, failedAttempt, failure, [
        this.event(task.id, 'attempt.failed', { attemptId: attempt.id, code: failure.code }, completedAt),
        this.event(task.id, 'failure.recorded', { failureId: failure.id, code: failure.code }, completedAt),
        this.event(task.id, 'task.transitioned', { from: 'running', to: 'failed', reason: failure.code }, completedAt),
      ]);
      return;
    }

    const successfulAttempt: Attempt = {
      ...attempt,
      status: 'succeeded',
      result: { output: result.output, evidence: result.evidence },
      completedAt,
    };
    const verifying = this.stateMachine.prepare(running, 'verifying', completedAt, { attempt: successfulAttempt });
    this.persistence.recordAttemptOutcome(verifying, running.version, successfulAttempt, undefined, [
      this.event(task.id, 'attempt.succeeded', { attemptId: attempt.id }, completedAt),
      this.event(task.id, 'task.transitioned', { from: 'running', to: 'verifying' }, completedAt),
    ]);

    const decision = this.verifier.verify(verifying, result);
    const verifiedAt = this.now();
    const verification: Verification = {
      id: asIdentifier<'Verification'>(this.nextId('verification')),
      taskId: task.id,
      attemptId: attempt.id,
      verdict: decision.verdict,
      planVersion: 1,
      verifier: this.verifier.verifierId,
      criterionResults: decision.criterionResults,
      evidence: decision.evidence,
      createdAt: verifiedAt,
    };
    if (decision.verdict === 'passed') {
      const succeeded = this.stateMachine.prepare(verifying, 'succeeded', verifiedAt, { verification });
      this.persistence.recordVerificationOutcome(succeeded, verifying.version, verification, undefined, [
        this.event(task.id, 'verification.passed', { verificationId: verification.id }, verifiedAt),
        this.event(task.id, 'task.transitioned', { from: 'verifying', to: 'succeeded' }, verifiedAt),
      ]);
      return;
    }

    const failure = this.failure(verifying, successfulAttempt, 'verification_failure', 'DETERMINISTIC_VERIFICATION_FAILED',
      'Deterministic verification rejected the execution result', { verdict: decision.verdict }, verifiedAt);
    const failed = this.stateMachine.prepare(verifying, 'failed', verifiedAt, { verification, terminalReason: failure.code });
    this.persistence.recordVerificationOutcome(failed, verifying.version, verification, failure, [
      this.event(task.id, 'verification.failed', { verificationId: verification.id }, verifiedAt),
      this.event(task.id, 'failure.recorded', { failureId: failure.id, code: failure.code }, verifiedAt),
      this.event(task.id, 'task.transitioned', { from: 'verifying', to: 'failed', reason: failure.code }, verifiedAt),
    ]);
  }

  private failure(
    task: Task,
    attempt: Attempt | undefined,
    category: Failure['category'],
    code: string,
    summary: string,
    details: JsonObject,
    createdAt: string,
  ): Failure {
    return { id: asIdentifier<'Failure'>(this.nextId('failure')), taskId: task.id, attemptId: attempt?.id,
      category, code, summary, details, retryable: false, createdAt };
  }

  private event(taskId: TaskId, eventType: string, payload: JsonObject, occurredAt: string): AuditEventInput {
    return { id: asIdentifier<'Event'>(this.nextId('event')), aggregateType: 'task', aggregateId: taskId,
      eventType, eventVersion: 1, actor: this.actor, occurredAt, payload };
  }
}

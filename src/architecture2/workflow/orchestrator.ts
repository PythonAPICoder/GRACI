import { createHash, randomUUID } from 'node:crypto';
import {
  asIdentifier,
  type Attempt,
  type Approval,
  type AuditEventInput,
  type Failure,
  type JsonObject,
  type Task,
  type TaskGraphRevisionId,
  type TaskId,
  type ProviderOfferingId,
  type ResourceLease,
  type ResourceSchedulingDecision,
  type Verification,
  type FailureDiagnosis,
  type OfferingLocationId,
} from '../domain/index.js';
import type { TaskExecutionProvider, TaskExecutionResult } from '../execution/index.js';
import type { Architecture2Persistence } from '../persistence/index.js';
import type { TaskVerifier } from '../verification/index.js';
import { evaluateTaskDependencies, graphHasTerminalCondition } from './dependency-evaluator.js';
import { getReadyTasksInScheduleOrder } from './deterministic-scheduler.js';
import { validateTaskGraph } from './task-graph-validator.js';
import { TaskStateMachine } from './task-state-machine.js';
import { createFailureDiagnosis, existingRetryAuthorized, PHASE_1L_DIAGNOSIS_POLICY_ID,
  PHASE_1L_DIAGNOSIS_POLICY_VERSION } from './failure-diagnoser.js';

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
  nextId?: (kind: 'attempt' | 'verification' | 'failure' | 'approval' | 'event') => string;
  resolveOffering?: (task: Task) => ProviderOfferingId;
  resolveExecutionProvider?: (offeringId: ProviderOfferingId) => TaskExecutionProvider;
  acquireResource?: (task: Task, offeringId: ProviderOfferingId,
    recovery?: import('../domain/index.js').AlternativeRecoveryDecision) => {
    decision: ResourceSchedulingDecision;
    lease: ResourceLease;
  } | undefined;
  maxConcurrentTasks?: number;
}

export class MinimalOrchestrator {
  private readonly stateMachine = new TaskStateMachine();
  private readonly actor: string;
  private readonly now: () => string;
  private readonly nextId: NonNullable<OrchestratorOptions['nextId']>;
  private readonly resolveOffering?: OrchestratorOptions['resolveOffering'];
  private readonly acquireResource?: OrchestratorOptions['acquireResource'];
  private readonly resolveExecutionProvider?: OrchestratorOptions['resolveExecutionProvider'];
  private readonly maxConcurrentTasks: number;
  private runActive = false;

  constructor(
    private readonly persistence: Architecture2Persistence,
    private readonly provider: TaskExecutionProvider,
    private readonly verifier: TaskVerifier,
    options: OrchestratorOptions = {},
  ) {
    this.actor = options.actor ?? 'architecture2-orchestrator';
    this.now = options.now ?? (() => new Date().toISOString());
    this.nextId = options.nextId ?? ((kind) => `${kind}-${randomUUID()}`);
    this.resolveOffering = options.resolveOffering;
    this.acquireResource = options.acquireResource;
    this.resolveExecutionProvider = options.resolveExecutionProvider;
    if (this.acquireResource && !this.resolveOffering) {
      throw new Error('acquireResource requires resolveOffering');
    }
    this.maxConcurrentTasks = options.maxConcurrentTasks ?? 1;
    if (!Number.isInteger(this.maxConcurrentTasks) || this.maxConcurrentTasks < 1) {
      throw new Error('maxConcurrentTasks must be a positive integer');
    }
  }

  async run(graphRevisionId: TaskGraphRevisionId): Promise<WorkflowRunResult> {
    if (this.runActive) throw new Error('An Orchestrator run is already active');
    this.runActive = true;
    try {
      return await this.runOwned(graphRevisionId);
    } finally {
      this.runActive = false;
    }
  }

  private async runOwned(graphRevisionId: TaskGraphRevisionId): Promise<WorkflowRunResult> {
    const executedTaskIds: TaskId[] = [];
    const revision = this.persistence.getTaskGraphRevision(graphRevisionId);
    if (!revision) throw new Error(`Unknown Task Graph Revision: ${graphRevisionId}`);
    validateTaskGraph(revision, this.persistence.getTasks(graphRevisionId),
      this.persistence.getTaskDependencies(graphRevisionId));
    this.recoverInterruptedWork(graphRevisionId);

    const active = new Map<TaskId, Promise<{ taskId: TaskId; error?: unknown }>>();
    let supervisionError: unknown;
    while (true) {
      this.evaluateAndPersistEligibility(graphRevisionId);
      if (supervisionError === undefined) {
        const ready = getReadyTasksInScheduleOrder(this.persistence.getTasks(graphRevisionId));
        for (const task of ready) {
          if (active.size >= this.maxConcurrentTasks) break;
          const execution = this.startTask(task);
          if (!execution) continue;
          executedTaskIds.push(task.id);
          const supervised = execution.then(
            () => ({ taskId: task.id }),
            (error: unknown) => ({ taskId: task.id, error }),
          );
          active.set(task.id, supervised);
        }
      }
      if (active.size === 0) break;
      const settled = await Promise.race(active.values());
      active.delete(settled.taskId);
      if (settled.error !== undefined && supervisionError === undefined) supervisionError = settled.error;
    }

    if (supervisionError !== undefined) throw supervisionError;

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

  approveTask(taskId: TaskId, decidedBy = 'product-owner'): Task {
    return this.decideApproval(taskId, 'approved', decidedBy);
  }

  denyTask(taskId: TaskId, reason: string, decidedBy = 'product-owner'): Task {
    if (!reason.trim()) throw new Error('Approval denial reason is required');
    return this.decideApproval(taskId, 'denied', decidedBy, reason);
  }

  private decideApproval(taskId: TaskId, decision: 'approved' | 'denied', decidedBy: string, reason?: string): Task {
    const task = this.persistence.getTask(taskId);
    if (!task || task.status !== 'waiting_for_approval') {
      throw new Error(`Task ${taskId} is not awaiting approval`);
    }
    const pending = this.persistence.getApprovals(taskId).filter((approval) => approval.decision === 'requested').at(-1);
    if (!pending) throw new Error(`Task ${taskId} has no pending approval request`);
    const now = this.now();
    const approval: Approval = { ...pending, decision, decidedBy, decidedAt: now,
      scope: reason ? { ...pending.scope, denialReason: reason } : pending.scope };
    const target = decision === 'approved' ? 'ready' : 'failed';
    const updated = this.stateMachine.prepare(task, target, now, decision === 'approved'
      ? { dependenciesSatisfied: true, approvalResumeAuthorized: true }
      : { terminalReason: `APPROVAL_DENIED: ${reason}` });
    this.persistence.recordApprovalDecision(updated, task.version, approval, [
      this.event(task.id, `approval.${decision}`, { approvalId: approval.id, reason: reason ?? null }, now),
      this.event(task.id, 'task.transitioned', { from: task.status, to: target, reason: reason ?? null }, now),
    ]);
    return updated;
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
        'external_outcome_indeterminate',
        task.status === 'running' ? 'INTERRUPTED_RUNNING_ATTEMPT' : 'INTERRUPTED_SCHEDULED_TASK',
        task.status === 'running'
          ? 'Execution was interrupted and its outcome cannot be proven'
          : 'Scheduling was interrupted before execution could be proven',
        { recoveredFromState: task.status }, false, now);
      const failedTask = this.stateMachine.prepare(task, 'failed', now, {
        attempt: recoveredAttempt,
        terminalReason: failure.code,
      });
      const events = [
        this.event(task.id, 'failure.recorded', { failureId: failure.id, code: failure.code }, now),
        this.event(task.id, 'failure.diagnosed', { failureId: failure.id }, now),
        this.event(task.id, 'task.transitioned', { from: task.status, to: 'failed', reason: failure.code }, now),
      ];
      const diagnosis = this.diagnosis(task, failure, recoveredAttempt, undefined, undefined, undefined, events[1]!.id, now);
      if (recoveredAttempt) {
        this.persistence.recordAttemptOutcome(failedTask, task.version, recoveredAttempt, failure, [
          this.event(task.id, 'attempt.indeterminate', { attemptId: recoveredAttempt.id }, now),
          ...events,
        ], diagnosis);
      } else {
        this.persistence.recordTaskFailure(failedTask, task.version, failure, events, diagnosis);
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
    for (const original of tasks) {
      if (original.status !== 'retry_pending') continue;
      const current = this.persistence.getTask(original.id);
      if (!current || current.status !== 'retry_pending') continue;
      const now = this.now();
      const attempts = this.persistence.getAttempts(current.id);
      const latestAttempt = attempts.at(-1);
      const failures = this.persistence.getFailures(current.id);
      const latestFailure = latestAttempt
        ? failures.slice().reverse().find((failure) => failure.attemptId === latestAttempt.id)
        : undefined;
      const diagnosis = latestFailure ? this.persistence.getFailureDiagnosis(latestFailure.id,
        PHASE_1L_DIAGNOSIS_POLICY_ID, PHASE_1L_DIAGNOSIS_POLICY_VERSION) : undefined;
      if (!latestFailure || diagnosis?.disposition !== 'retry_same_path' ||
          !existingRetryAuthorized(current, latestFailure, attempts.length)) {
        const failure = this.failure(current, latestAttempt, 'execution_defect', 'permanent',
          'UNSAFE_RETRY_PENDING_STATE', 'Durable retry authorization could not be proven',
          { attemptsUsed: attempts.length, priorFailureId: latestFailure?.id ?? null }, false, now);
        const failed = this.stateMachine.prepare(current, 'failed', now, { terminalReason: failure.code });
        const diagnosisEvent = this.event(current.id, 'failure.diagnosed', { failureId: failure.id }, now);
        const unsafeDiagnosis = this.diagnosis(current, failure, latestAttempt, undefined, undefined, undefined,
          diagnosisEvent.id, now);
        this.persistence.recordTaskFailure(failed, current.version, failure, [
          this.event(current.id, 'failure.recorded', { failureId: failure.id, code: failure.code }, now),
          diagnosisEvent,
          this.event(current.id, 'task.transitioned', {
            from: 'retry_pending', to: 'failed', reason: failure.code,
          }, now),
        ], unsafeDiagnosis);
        continue;
      }
      this.stateMachine.transition(this.persistence, current, 'ready', now,
        this.event(current.id, 'task.retry_scheduled', { attemptsUsed: attempts.length, failureId: latestFailure.id }, now),
        { dependenciesSatisfied: true, retryAuthorized: true });
    }
  }

  private startTask(task: Task): Promise<void> | undefined {
    const recovery = this.persistence.getPendingAlternativeRecovery(task.id);
    const reconciliation = this.persistence.getPendingReconciliation(task.id);
    const inputRevision = this.persistence.getPendingInputRevision(task.id);
    if ([recovery, reconciliation, inputRevision].filter(Boolean).length > 1) {
      throw new Error(`Conflicting pending recovery authority: ${task.id}`);
    }
    const sourceAttempt = reconciliation ? this.persistence.getAttempts(task.id)
      .find((attempt) => attempt.id === reconciliation.attemptId) : undefined;
    const selectedOfferingId = recovery?.selectedOfferingId ??
      (sourceAttempt?.providerOfferingId as ProviderOfferingId | undefined) ?? this.resolveOffering?.(task);
    const resource = selectedOfferingId && this.acquireResource ? this.acquireResource(task, selectedOfferingId, recovery) : undefined;
    const lease = resource?.lease;
    if (this.acquireResource && selectedOfferingId && !resource) return undefined;
    if (recovery?.selectedNodeId && (resource?.lease.nodeId !== recovery.selectedNodeId ||
        resource.lease.locationId !== recovery.selectedLocationId)) return undefined;
    if (lease && lease.offeringId !== selectedOfferingId) throw new Error('Resource lease offering does not match selected offering');
    const scheduledAt = this.now();
    const schedulingEvent = this.event(task.id, 'task.transitioned', { from: 'ready', to: 'scheduled' }, scheduledAt);
    const scheduled = this.stateMachine.prepare(task, 'scheduled', scheduledAt);
    if (resource) {
      const resourceLease = resource.lease;
      const admitted = this.persistence.scheduleTaskWithResource(scheduled, task.version, resource.decision, resourceLease, [
        this.event(task.id, 'resource.scheduled', {
          decisionId: resource.decision.request.id, leaseId: resourceLease.id, nodeId: resourceLease.nodeId,
        }, scheduledAt),
        schedulingEvent,
      ]);
      if (!admitted) return undefined;
    } else {
      this.persistence.updateTask(scheduled, task.version, schedulingEvent);
    }
    const attempts = this.persistence.getAttempts(task.id);
    const attemptNumber = (attempts.at(-1)?.attemptNumber ?? 0) + 1;
    const startedAt = this.now();
    const attempt: Attempt = {
      id: asIdentifier<'Attempt'>(this.nextId('attempt')),
      taskId: task.id,
      attemptNumber,
      status: 'running',
      providerOfferingId: selectedOfferingId ?? this.provider.providerId,
      computeNodeId: lease?.nodeId,
      inputSnapshot: { objective: task.objective, inputs: task.inputs, requiredCapabilities: task.requiredCapabilities },
      idempotencyKey: `${task.id}:${attemptNumber}`,
      startedAt,
      createdAt: startedAt,
    };
    const running = this.stateMachine.prepare(scheduled, 'running', startedAt, { attempt });
    this.persistence.startAttempt(running, scheduled.version, attempt, [
      this.event(task.id, 'attempt.started', { attemptId: attempt.id, attemptNumber }, startedAt),
      this.event(task.id, 'task.transitioned', { from: 'scheduled', to: 'running' }, startedAt),
    ], recovery?.id, reconciliation?.id, undefined, inputRevision?.id);

    const executionProvider = selectedOfferingId && this.resolveExecutionProvider
      ? this.resolveExecutionProvider(selectedOfferingId) : this.provider;
    if (this.resolveExecutionProvider && executionProvider.providerId !== selectedOfferingId) {
      throw new Error(`Execution provider is not bound to selected offering: ${selectedOfferingId}`);
    }
    return this.completeTask(task, running, attempt, lease, attemptNumber, executionProvider);
  }

  private async completeTask(task: Task, running: Task, attempt: Attempt,
    lease: ResourceLease | undefined, attemptNumber: number, executionProvider: TaskExecutionProvider): Promise<void> {
    let result: TaskExecutionResult;
    try {
      result = await executionProvider.execute({ taskId: task.id, attemptId: attempt.id, attemptNumber,
        objective: task.objective, inputs: task.inputs, requiredCapabilities: task.requiredCapabilities });
    } catch (error) {
      result = { status: 'failed', classification: 'permanent', code: 'PROVIDER_EXCEPTION', summary: 'Execution provider threw an exception',
        details: { message: error instanceof Error ? error.message : String(error) } };
    }
    if (lease) {
      const releasedAt = this.now();
      this.persistence.releaseResourceLease({ ...lease, status: 'released', releasedAt },
        this.event(task.id, 'resource-lease.released', { leaseId: lease.id }, releasedAt));
    }

    const completedAt = this.now();
    if (result.status === 'failed') {
      const failedAttempt: Attempt = { ...attempt, status: 'failed', result: { ...result }, completedAt };
      const retryable = result.classification === 'transient' && attemptNumber < this.maxAttempts(task);
      const failure = this.failure(running, failedAttempt,
        result.classification === 'transient' ? 'transient_infrastructure' :
          result.classification === 'approval_required' ? 'policy_or_approval' : 'execution_defect',
        result.classification, result.code, result.summary, result.details, retryable, completedAt);
      if (result.classification === 'approval_required') {
        const approval = this.approval(task, failedAttempt, failure, completedAt);
        const diagnosisEvent = this.event(task.id, 'failure.diagnosed', { failureId: failure.id }, completedAt);
        const diagnosis = this.diagnosis(task, failure, failedAttempt, undefined, approval, lease?.locationId,
          diagnosisEvent.id, completedAt);
        const paused = this.stateMachine.prepare(running, 'waiting_for_approval', completedAt,
          { attempt: failedAttempt, approvalPauseAuthorized: true });
        this.persistence.recordApprovalPause(paused, running.version, failedAttempt, failure, approval, [
          this.event(task.id, 'attempt.failed', { attemptId: attempt.id, code: failure.code }, completedAt),
          this.event(task.id, 'failure.recorded', { failureId: failure.id, classification: failure.classification }, completedAt),
          diagnosisEvent,
          this.event(task.id, 'approval.requested', { approvalId: approval.id, reason: failure.summary }, completedAt),
          this.event(task.id, 'task.transitioned', { from: 'running', to: 'waiting_for_approval' }, completedAt),
        ], diagnosis);
        return;
      }
      const diagnosisEvent = this.event(task.id, 'failure.diagnosed', { failureId: failure.id }, completedAt);
      const diagnosis = this.diagnosis(task, failure, failedAttempt, undefined, undefined, lease?.locationId,
        diagnosisEvent.id, completedAt);
      const target = diagnosis.disposition === 'retry_same_path' ? 'retry_pending' : 'failed';
      const failedTask = this.stateMachine.prepare(running, target, completedAt,
        retryable
          ? { attempt: failedAttempt, retryAuthorized: true }
          : { attempt: failedAttempt, terminalReason: failure.code });
      this.persistence.recordAttemptOutcome(failedTask, running.version, failedAttempt, failure, [
        this.event(task.id, 'attempt.failed', { attemptId: attempt.id, code: failure.code }, completedAt),
        this.event(task.id, 'failure.recorded', { failureId: failure.id, code: failure.code }, completedAt),
        diagnosisEvent,
        this.event(task.id, 'task.transitioned', { from: 'running', to: target, reason: failure.code }, completedAt),
      ], diagnosis);
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

    const retryable = task.retryPolicy.retryVerificationFailures === true && attemptNumber < this.maxAttempts(task);
    const failure = this.failure(verifying, successfulAttempt, 'verification_failure', 'verification_failed',
      'DETERMINISTIC_VERIFICATION_FAILED', 'Deterministic verification rejected the execution result',
      { verdict: decision.verdict }, retryable, verifiedAt);
    const diagnosisEvent = this.event(task.id, 'failure.diagnosed', { failureId: failure.id }, verifiedAt);
    const diagnosis = this.diagnosis(task, failure, successfulAttempt, verification, undefined, lease?.locationId,
      diagnosisEvent.id, verifiedAt);
    const target = diagnosis.disposition === 'retry_same_path' ? 'retry_pending' : 'failed';
    const failed = this.stateMachine.prepare(verifying, target, verifiedAt,
      retryable
        ? { verification, retryAuthorized: true }
        : { verification, terminalReason: failure.code });
    this.persistence.recordVerificationOutcome(failed, verifying.version, verification, failure, [
      this.event(task.id, 'verification.failed', { verificationId: verification.id }, verifiedAt),
      this.event(task.id, 'failure.recorded', { failureId: failure.id, code: failure.code }, verifiedAt),
      diagnosisEvent,
      this.event(task.id, 'task.transitioned', { from: 'verifying', to: target, reason: failure.code }, verifiedAt),
    ], diagnosis);
  }

  private failure(
    task: Task,
    attempt: Attempt | undefined,
    category: Failure['category'],
    classification: Failure['classification'],
    code: string,
    summary: string,
    details: JsonObject,
    retryable: boolean,
    createdAt: string,
  ): Failure {
    return { id: asIdentifier<'Failure'>(this.nextId('failure')), taskId: task.id, attemptId: attempt?.id,
      category, classification, code, summary, details, retryable, createdAt };
  }

  private maxAttempts(task: Task): number {
    const configured = task.retryPolicy.maxAttempts;
    return typeof configured === 'number' && Number.isInteger(configured) && configured >= 1 ? configured : 3;
  }

  private approval(task: Task, attempt: Attempt, failure: Failure, requestedAt: string): Approval {
    const action = 'resume_task_after_approval';
    return { id: asIdentifier<'Approval'>(this.nextId('approval')), goalId: task.goalId, taskId: task.id,
      attemptId: attempt.id, action, scope: { reason: failure.summary, failureId: failure.id },
      actionDigest: createHash('sha256').update(`${task.id}:${attempt.id}:${action}:${failure.code}`).digest('hex'),
      decision: 'requested', requestedAt };
  }

  private diagnosis(task: Task, failure: Failure, attempt: Attempt | undefined, verification: Verification | undefined,
    approval: Approval | undefined, offeringLocationId: OfferingLocationId | undefined,
    eventId: AuditEventInput['id'], diagnosedAt: string): FailureDiagnosis {
    const attempts = this.persistence.getAttempts(task.id);
    return createFailureDiagnosis({ evidence: { task, failure, attempts, attempt, verification, approval, offeringLocationId },
      eventId, diagnosedAt, diagnosedBy: this.actor });
  }

  private event(taskId: TaskId, eventType: string, payload: JsonObject, occurredAt: string): AuditEventInput {
    return { id: asIdentifier<'Event'>(this.nextId('event')), aggregateType: 'task', aggregateId: taskId,
      eventType, eventVersion: 1, actor: this.actor, occurredAt, payload };
  }
}

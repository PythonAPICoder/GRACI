import type {
  Failure,
  Task,
  TaskDependency,
  TaskGraphRevisionId,
  TaskId,
  TaskStatus,
} from '../domain/index.js';
import type { Architecture2Persistence } from '../persistence/index.js';
import { compareScheduledTasks } from './deterministic-scheduler.js';
import { evaluateTaskDependencies } from './dependency-evaluator.js';
import { compareTaskIds, validateTaskGraph } from './task-graph-validator.js';

export type QueueReason =
  | 'ready'
  | 'dependencies_pending'
  | 'predicate_not_supported'
  | 'required_dependency_failed'
  | 'waiting_for_approval'
  | 'retry_pending'
  | 'scheduled'
  | 'running'
  | 'verifying'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | 'superseded';

export interface InspectedDependency {
  predecessorTaskId: TaskId;
  predecessorStatus: TaskStatus;
  condition: TaskDependency['condition'];
}

export interface QueueInspectionEntry {
  taskId: TaskId;
  title: string;
  status: TaskStatus;
  schedulerEligible: boolean;
  reason: QueueReason;
  dependencies: InspectedDependency[];
  blockingTaskIds: TaskId[];
  terminalReason?: string;
  attemptCount: number;
  latestFailure?: Pick<Failure, 'id' | 'classification' | 'code' | 'summary' | 'retryable' | 'createdAt'>;
}

function stateReason(task: Task): QueueReason {
  if (task.status === 'planned') return 'dependencies_pending';
  if (task.status === 'blocked') return 'required_dependency_failed';
  return task.status;
}

export function inspectQueue(
  persistence: Architecture2Persistence,
  graphRevisionId: TaskGraphRevisionId,
): QueueInspectionEntry[] {
  const revision = persistence.getTaskGraphRevision(graphRevisionId);
  if (!revision) throw new Error(`Unknown Task Graph Revision: ${graphRevisionId}`);
  const tasks = persistence.getTasks(graphRevisionId);
  const dependencies = persistence.getTaskDependencies(graphRevisionId);
  validateTaskGraph(revision, tasks, dependencies);
  const tasksById = new Map(tasks.map((task) => [task.id, task]));

  return [...tasks].sort(compareScheduledTasks).map((task) => {
    const incoming = dependencies
      .filter((dependency) => dependency.successorTaskId === task.id)
      .sort((left, right) => compareTaskIds(left.predecessorTaskId, right.predecessorTaskId));
    const inspectedDependencies = incoming.map((dependency) => {
      const predecessor = tasksById.get(dependency.predecessorTaskId);
      if (!predecessor) {
        throw new Error(`Persisted task graph corruption: dependency predecessor ${dependency.predecessorTaskId} is missing`);
      }
      return { predecessorTaskId: predecessor.id, predecessorStatus: predecessor.status, condition: dependency.condition };
    });
    const evaluation = evaluateTaskDependencies(task, tasks, dependencies);
    const failures = persistence.getFailures(task.id);
    const latestFailure = failures.at(-1);
    const reason: QueueReason = task.status === 'planned'
      ? evaluation.reason === 'dependencies_satisfied' ? 'ready' : evaluation.reason
      : task.status === 'blocked' ? 'required_dependency_failed' : stateReason(task);
    return {
      taskId: task.id,
      title: task.title,
      status: task.status,
      schedulerEligible: task.status === 'ready',
      reason,
      dependencies: inspectedDependencies,
      blockingTaskIds: evaluation.blockingTaskIds,
      terminalReason: task.terminalReason,
      attemptCount: persistence.getAttempts(task.id).length,
      latestFailure: latestFailure && {
        id: latestFailure.id,
        classification: latestFailure.classification,
        code: latestFailure.code,
        summary: latestFailure.summary,
        retryable: latestFailure.retryable,
        createdAt: latestFailure.createdAt,
      },
    };
  });
}

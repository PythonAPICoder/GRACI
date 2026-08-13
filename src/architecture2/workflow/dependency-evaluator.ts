import type { Task, TaskDependency, TaskId } from '../domain/index.js';
import { compareTaskIds } from './task-graph-validator.js';

export type DependencyDisposition = 'ready' | 'waiting' | 'blocked_by_failure';
export type DependencyReason = 'dependencies_satisfied' | 'dependencies_pending' |
  'predicate_not_supported' | 'required_dependency_failed';

export interface DependencyEvaluation {
  taskId: TaskId;
  disposition: DependencyDisposition;
  reason: DependencyReason;
  blockingTaskIds: TaskId[];
}

const TERMINAL = new Set<Task['status']>(['succeeded', 'failed', 'cancelled', 'superseded']);
const FAILED_UPSTREAM = new Set<Task['status']>(['failed', 'cancelled', 'superseded']);

export function evaluateTaskDependencies(
  task: Task,
  tasks: readonly Task[],
  dependencies: readonly TaskDependency[],
): DependencyEvaluation {
  const tasksById = new Map(tasks.map((candidate) => [candidate.id, candidate]));
  const incoming = dependencies.filter((dependency) => dependency.successorTaskId === task.id);
  const blockingTaskIds: TaskId[] = [];
  let failed = false;

  for (const dependency of incoming) {
    const predecessor = tasksById.get(dependency.predecessorTaskId);
    if (!predecessor) {
      throw new Error(`Persisted task graph corruption: dependency predecessor ${dependency.predecessorTaskId} is missing`);
    }
    if (dependency.condition === 'predicate') {
      blockingTaskIds.push(predecessor.id);
      continue;
    }
    if (dependency.condition === 'success') {
      if (predecessor.status === 'succeeded') continue;
      if (FAILED_UPSTREAM.has(predecessor.status) ||
        (predecessor.status === 'blocked' && predecessor.terminalReason === 'required_dependency_failed')) failed = true;
      blockingTaskIds.push(predecessor.id);
      continue;
    }
    if (dependency.condition === 'completion') {
      if (TERMINAL.has(predecessor.status)) continue;
      blockingTaskIds.push(predecessor.id);
    }
  }

  return {
    taskId: task.id,
    disposition: failed ? 'blocked_by_failure' : blockingTaskIds.length === 0 ? 'ready' : 'waiting',
    reason: failed ? 'required_dependency_failed' : blockingTaskIds.length === 0 ? 'dependencies_satisfied' :
      incoming.some((dependency) => dependency.condition === 'predicate') ? 'predicate_not_supported' : 'dependencies_pending',
    blockingTaskIds: [...new Set(blockingTaskIds)].sort(compareTaskIds),
  };
}

export function graphHasTerminalCondition(tasks: readonly Task[]): boolean {
  return tasks.every((task) => TERMINAL.has(task.status) ||
    (task.status === 'blocked' && task.terminalReason === 'required_dependency_failed'));
}

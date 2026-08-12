import type { Task, TaskDependency, TaskId } from '../domain/index.js';

export type DependencyDisposition = 'ready' | 'waiting' | 'blocked_by_failure';

export interface DependencyEvaluation {
  taskId: TaskId;
  disposition: DependencyDisposition;
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
      failed = true;
      blockingTaskIds.push(dependency.predecessorTaskId);
      continue;
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
    blockingTaskIds,
  };
}

export function graphHasTerminalCondition(tasks: readonly Task[]): boolean {
  return tasks.every((task) => TERMINAL.has(task.status) ||
    (task.status === 'blocked' && task.terminalReason === 'required_dependency_failed'));
}

import type { Task, TaskDependency, TaskGraphRevision, TaskId } from '../domain/index.js';

export type TaskGraphValidationCode =
  | 'DUPLICATE_TASK_ID'
  | 'TASK_REVISION_MISMATCH'
  | 'TASK_GOAL_MISMATCH'
  | 'UNKNOWN_PREDECESSOR_TASK'
  | 'UNKNOWN_SUCCESSOR_TASK'
  | 'DEPENDENCY_REVISION_MISMATCH'
  | 'SELF_DEPENDENCY'
  | 'DUPLICATE_DEPENDENCY'
  | 'CONFLICTING_DEPENDENCY'
  | 'INVALID_PREDICATE_DEPENDENCY'
  | 'CYCLIC_TASK_GRAPH';

export class TaskGraphValidationError extends Error {
  constructor(
    readonly code: TaskGraphValidationCode,
    message: string,
    readonly unresolvedTaskIds: readonly TaskId[] = [],
  ) {
    super(message);
    this.name = 'TaskGraphValidationError';
  }
}

export interface TaskGraphValidationResult {
  topologicalTaskIds: TaskId[];
}

export function compareTaskIds(left: TaskId, right: TaskId): number {
  return left < right ? -1 : left > right ? 1 : 0;
}

function canonicalize(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(',')}]`;
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${canonicalize(object[key])}`).join(',')}}`;
}

function insertLexically(queue: TaskId[], taskId: TaskId): void {
  const position = queue.findIndex((candidate) => compareTaskIds(candidate, taskId) > 0);
  if (position === -1) queue.push(taskId);
  else queue.splice(position, 0, taskId);
}

export function validateTaskGraph(
  revision: TaskGraphRevision,
  tasks: readonly Task[],
  dependencies: readonly TaskDependency[],
): TaskGraphValidationResult {
  const sortedTasks = [...tasks].sort((left, right) => compareTaskIds(left.id, right.id));
  const tasksById = new Map<TaskId, Task>();
  for (const task of sortedTasks) {
    if (tasksById.has(task.id)) {
      throw new TaskGraphValidationError('DUPLICATE_TASK_ID', `Duplicate Task ID: ${task.id}`);
    }
    if (task.graphRevisionId !== revision.id) {
      throw new TaskGraphValidationError('TASK_REVISION_MISMATCH', `Task ${task.id} belongs to another graph revision`);
    }
    if (task.goalId !== revision.goalId) {
      throw new TaskGraphValidationError('TASK_GOAL_MISMATCH', `Task ${task.id} belongs to another Goal`);
    }
    tasksById.set(task.id, task);
  }

  const adjacency = new Map<TaskId, TaskId[]>(sortedTasks.map((task) => [task.id, []]));
  const indegree = new Map<TaskId, number>(sortedTasks.map((task) => [task.id, 0]));
  const dependencyByPair = new Map<string, TaskDependency>();

  for (const dependency of dependencies) {
    if (dependency.graphRevisionId !== revision.id) {
      throw new TaskGraphValidationError('DEPENDENCY_REVISION_MISMATCH', 'Dependency belongs to another graph revision');
    }
    if (!tasksById.has(dependency.predecessorTaskId)) {
      throw new TaskGraphValidationError('UNKNOWN_PREDECESSOR_TASK', `Unknown predecessor Task: ${dependency.predecessorTaskId}`);
    }
    if (!tasksById.has(dependency.successorTaskId)) {
      throw new TaskGraphValidationError('UNKNOWN_SUCCESSOR_TASK', `Unknown successor Task: ${dependency.successorTaskId}`);
    }
    if (dependency.predecessorTaskId === dependency.successorTaskId) {
      throw new TaskGraphValidationError('SELF_DEPENDENCY', `Task ${dependency.predecessorTaskId} cannot depend on itself`);
    }
    const hasPredicate = dependency.predicate !== undefined;
    if ((dependency.condition === 'predicate') !== hasPredicate) {
      throw new TaskGraphValidationError('INVALID_PREDICATE_DEPENDENCY',
        `Dependency ${dependency.predecessorTaskId} -> ${dependency.successorTaskId} has an invalid predicate definition`);
    }
    const pair = `${dependency.predecessorTaskId}\u0000${dependency.successorTaskId}`;
    const existing = dependencyByPair.get(pair);
    if (existing) {
      const conflicting = existing.condition !== dependency.condition ||
        canonicalize(existing.predicate ?? null) !== canonicalize(dependency.predicate ?? null);
      throw new TaskGraphValidationError(conflicting ? 'CONFLICTING_DEPENDENCY' : 'DUPLICATE_DEPENDENCY',
        `${conflicting ? 'Conflicting' : 'Duplicate'} dependency: ${dependency.predecessorTaskId} -> ${dependency.successorTaskId}`);
    }
    dependencyByPair.set(pair, dependency);
    adjacency.get(dependency.predecessorTaskId)!.push(dependency.successorTaskId);
    indegree.set(dependency.successorTaskId, indegree.get(dependency.successorTaskId)! + 1);
  }

  for (const outgoing of adjacency.values()) outgoing.sort(compareTaskIds);
  const available = sortedTasks.filter((task) => indegree.get(task.id) === 0).map((task) => task.id);
  const topologicalTaskIds: TaskId[] = [];
  while (available.length > 0) {
    const taskId = available.shift()!;
    topologicalTaskIds.push(taskId);
    for (const successorId of adjacency.get(taskId)!) {
      const nextIndegree = indegree.get(successorId)! - 1;
      indegree.set(successorId, nextIndegree);
      if (nextIndegree === 0) insertLexically(available, successorId);
    }
  }

  if (topologicalTaskIds.length !== sortedTasks.length) {
    const unresolvedTaskIds = sortedTasks
      .filter((task) => indegree.get(task.id)! > 0)
      .map((task) => task.id);
    throw new TaskGraphValidationError('CYCLIC_TASK_GRAPH',
      `Task graph is cyclic; unresolved Tasks: ${unresolvedTaskIds.join(', ')}`, unresolvedTaskIds);
  }
  return { topologicalTaskIds };
}

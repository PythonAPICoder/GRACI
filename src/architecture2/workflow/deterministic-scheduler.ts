import type { Task } from '../domain/index.js';
import { compareTaskIds } from './task-graph-validator.js';

function timestampValue(task: Task): number {
  const value = Date.parse(task.createdAt);
  if (Number.isNaN(value)) throw new Error(`Invalid persisted Task createdAt: ${task.id}`);
  return value;
}

export function compareScheduledTasks(left: Task, right: Task): number {
  const timestampOrder = timestampValue(left) - timestampValue(right);
  return timestampOrder || compareTaskIds(left.id, right.id);
}

export function getReadyTasksInScheduleOrder(tasks: readonly Task[]): Task[] {
  return tasks.filter((task) => task.status === 'ready').sort(compareScheduledTasks);
}

export function selectNextReadyTask(tasks: readonly Task[]): Task | undefined {
  return getReadyTasksInScheduleOrder(tasks)[0];
}

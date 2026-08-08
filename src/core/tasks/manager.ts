export interface Task {
  id: string;
  type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  createdAt: number;
  startedAt?: number;
  completedAt?: number;
  errorMessage?: string;
}

export class TaskManager {
  private tasks = new Map<string, Task>();

  createTask(type: string): Task {
    const id = Math.random().toString(36).substr(2, 9);
    const task: Task = {
      id,
      type,
      status: 'pending',
      createdAt: Date.now(),
    };
    this.tasks.set(id, task);
    return task;
  }

  getTask(id: string): Task | undefined { return this.tasks.get(id); }

  listTasks(): Task[] { return Array.from(this.tasks.values()); }

  updateStatus(id: string, status: Task['status'], errorMessage?: string) {
    const task = this.tasks.get(id);
    if (!task) return;
    task.status = status;
    if (status === 'running') task.startedAt = Date.now();
    if (status === 'completed' || status === 'failed') task.completedAt = Date.now();
    if (errorMessage) task.errorMessage = errorMessage;
  }
}

export const taskManager = new TaskManager();

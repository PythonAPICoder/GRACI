import { describe, it, expect } from 'vitest';
import { taskManager } from '../src/core/tasks/manager.js';

describe('Task Manager', () => {
  it('creates and updates a task', () => {
    const t = taskManager.createTask('test');
    expect(t.status).toBe('pending');
    taskManager.updateStatus(t.id, 'running');
    const fetched = taskManager.getTask(t.id);
    expect(fetched?.status).toBe('running');
  });
});
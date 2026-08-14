import type { AuditEventInput, GoalId, JsonObject, MemoryId, MemoryRecord, MemoryScope,
  MemoryTrustStatus } from '../domain/index.js';
import type { Architecture2Persistence } from '../persistence/index.js';

export interface StoreMemoryCommand {
  id: MemoryId;
  scope: MemoryScope;
  goalId?: GoalId;
  content: JsonObject;
  sourceType: string;
  sourceReference: string;
  createdBy: string;
  createdAt: string;
  trustStatus: MemoryTrustStatus;
  validUntil?: string;
  reusablePermission?: string;
  eventId: MemoryRecord['eventId'];
}

export interface RetrieveMemoriesCommand {
  goalId: GoalId;
  includeReusable: boolean;
  asOf: string;
}

export interface SupersedeMemoryCommand extends StoreMemoryCommand {
  expectedCurrentId: MemoryId;
  supersessionEventId: MemoryRecord['eventId'];
}

export function storeMemory(persistence: Architecture2Persistence, command: StoreMemoryCommand): MemoryRecord {
  const value: MemoryRecord = { ...command };
  return persistence.storeMemory(value, memoryEvent(value.eventId, value.id, 'memory.stored', value.createdBy, value.createdAt));
}

export function retrieveMemories(persistence: Architecture2Persistence, command: RetrieveMemoriesCommand): MemoryRecord[] {
  return persistence.retrieveMemories(command.goalId, command.includeReusable, command.asOf);
}

export function supersedeMemory(persistence: Architecture2Persistence, command: SupersedeMemoryCommand): MemoryRecord {
  const { expectedCurrentId, supersessionEventId, ...record } = command;
  const replacement: MemoryRecord = { ...record, supersedesMemoryId: expectedCurrentId };
  return persistence.supersedeMemory(expectedCurrentId, replacement, [
    memoryEvent(replacement.eventId, replacement.id, 'memory.stored', replacement.createdBy, replacement.createdAt),
    memoryEvent(supersessionEventId, expectedCurrentId, 'memory.superseded', replacement.createdBy, replacement.createdAt),
  ]);
}

function memoryEvent(id: MemoryRecord['eventId'], aggregateId: string, eventType: string,
  actor: string, occurredAt: string): AuditEventInput {
  return { id, aggregateType: 'memory', aggregateId, eventType, eventVersion: 1, actor, occurredAt, payload: {} };
}

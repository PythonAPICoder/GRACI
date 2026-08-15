import { assertIdentifier, MAX_MEMORY_CITATIONS_PER_DECISION, type AuditEventInput, type GoalId,
  type JsonObject, type MemoryId, type MemoryRecord, type MemoryScope,
  type MemoryTrustStatus } from '../domain/index.js';
import type { Architecture2Persistence } from '../persistence/index.js';

export function normalizeMemoryCitations(memoryIds: readonly MemoryId[] | undefined): MemoryId[] {
  const list = memoryIds ?? [];
  const unique = new Set<string>();
  for (const id of list) {
    assertIdentifier(id, 'memory citation id');
    if (unique.has(id)) throw new Error('Duplicate memory citation in one decision');
    unique.add(id);
  }
  if (unique.size > MAX_MEMORY_CITATIONS_PER_DECISION) {
    throw new Error(`Memory citations exceed the governed bound of ${MAX_MEMORY_CITATIONS_PER_DECISION}`);
  }
  return [...unique].sort() as MemoryId[];
}

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

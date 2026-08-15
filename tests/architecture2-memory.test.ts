import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { DatabaseSync } from 'node:sqlite';
import { asIdentifier, type AuditEventInput, type Goal } from '../src/architecture2/domain/index.js';
import { SqliteArchitecture2Persistence } from '../src/architecture2/persistence/index.js';
import { retrieveMemories, storeMemory, supersedeMemory } from '../src/architecture2/workflow/index.js';

const NOW = '2026-08-14T12:00:00.000Z';
const LATER = '2026-08-14T12:01:00.000Z';
const goalId = asIdentifier<'Goal'>('memory-goal');

describe('Architecture 2 Phase 1U durable working memory', () => {
  let directory: string;
  let path: string;
  let persistence: SqliteArchitecture2Persistence;
  let sequence: number;

  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'graci-phase1u-'));
    path = join(directory, 'memory.sqlite');
    persistence = new SqliteArchitecture2Persistence({ databasePath: path });
    persistence.initialize();
    sequence = 0;
    const goal: Goal = { id: goalId, objective: 'Retain bounded context', constraints: {}, priority: 'normal',
      privacyClass: 'internal', status: 'active', version: 1, createdAt: NOW, updatedAt: NOW };
    persistence.createGoal({ goal, criteria: [] }, event(goal.id, 'goal.created'));
  });

  afterEach(() => { persistence.close(); rmSync(directory, { recursive: true, force: true }); });

  const eventId = () => asIdentifier<'Event'>(`memory-event-${++sequence}`);
  const event = (aggregateId: string, eventType: string): AuditEventInput => ({ id: eventId(), aggregateType: 'test',
    aggregateId, eventType, eventVersion: 1, actor: 'memory-test', occurredAt: NOW, payload: {} });

  function goalMemory(id: string, createdAt = NOW) {
    return { id: asIdentifier<'Memory'>(id), scope: 'goal' as const, goalId, content: { fact: id },
      sourceType: 'caller', sourceReference: `source:${id}`, createdBy: 'memory-test', createdAt,
      trustStatus: 'untrusted' as const, eventId: eventId() };
  }

  it('stores goal memory with durable provenance and retrieves it only in scope', () => {
    const value = goalMemory('goal-memory');
    storeMemory(persistence, value);
    expect(retrieveMemories(persistence, { goalId, includeReusable: false, asOf: LATER })).toEqual([value]);
    persistence.close(); persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    expect(persistence.inspectMemory(value.id)?.memory).toEqual(value);
  });

  it('requires explicit reusable permission and explicit retrieval inclusion', () => {
    const reusable = { ...goalMemory('reusable-memory'), scope: 'reusable' as const, goalId: undefined,
      reusablePermission: 'Product Owner permits reuse for technical goals', trustStatus: 'trusted' as const };
    storeMemory(persistence, reusable);
    expect(retrieveMemories(persistence, { goalId, includeReusable: false, asOf: LATER })).toEqual([]);
    expect(retrieveMemories(persistence, { goalId, includeReusable: true, asOf: LATER })).toEqual([reusable]);
    expect(() => storeMemory(persistence, { ...reusable, id: asIdentifier<'Memory'>('invalid-reusable'),
      reusablePermission: undefined, eventId: eventId() })).toThrow(/reusable permission/);
  });

  it('orders current applicable memory deterministically and excludes stale records', () => {
    const older = goalMemory('z-older', NOW);
    const sameA = goalMemory('a-same', LATER);
    const sameB = goalMemory('b-same', LATER);
    const stale = { ...goalMemory('stale', NOW), validUntil: '2026-08-14T12:00:30.000Z' };
    for (const value of [sameB, stale, older, sameA]) storeMemory(persistence, value);
    expect(retrieveMemories(persistence, { goalId, includeReusable: false,
      asOf: '2026-08-14T12:02:00.000Z' }).map((item) => item.id)).toEqual(['a-same', 'b-same', 'z-older']);
  });

  it('supersedes without rewriting history and rejects stale competing supersession', () => {
    const prior = goalMemory('prior'); storeMemory(persistence, prior);
    const replacement = { ...goalMemory('replacement', LATER), expectedCurrentId: prior.id,
      supersessionEventId: eventId(), trustStatus: 'trusted' as const };
    supersedeMemory(persistence, replacement);
    expect(retrieveMemories(persistence, { goalId, includeReusable: false, asOf: LATER }).map((item) => item.id))
      .toEqual(['replacement']);
    expect(persistence.inspectMemory(prior.id)).toMatchObject({ supersededByMemoryId: 'replacement',
      history: [{ id: 'prior' }, { id: 'replacement' }] });
    const competing = new SqliteArchitecture2Persistence({ databasePath: path }); competing.initialize();
    expect(() => supersedeMemory(competing, { ...goalMemory('competing', LATER), expectedCurrentId: prior.id,
      supersessionEventId: eventId() })).toThrow(/stale or already superseded/);
    competing.close();
  });

  it('fails closed on corrupt supersession relationships', () => {
    const prior = goalMemory('corrupt-prior'); storeMemory(persistence, prior);
    const replacement = { ...goalMemory('corrupt-replacement', LATER), expectedCurrentId: prior.id,
      supersessionEventId: eventId() };
    supersedeMemory(persistence, replacement);
    persistence.close();
    const database = new DatabaseSync(path);
    database.exec('DROP TRIGGER memory_records_no_update;');
    database.prepare("UPDATE memory_records SET goal_id=NULL,scope='reusable',reusable_permission='corrupt' WHERE id=?")
      .run(replacement.id);
    database.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    expect(() => persistence.inspectMemory(prior.id)).toThrow(/Corrupt persisted Memory supersession/);
  });

  it('creates information only and no execution or recovery authority', () => {
    const database = new DatabaseSync(path);
    const counts = () => Object.fromEntries(['tasks', 'attempts', 'failures', 'alternative_recovery_decisions',
      'reconciliation_decisions', 'input_revisions', 'replanning_decisions', 'research_requests']
      .map((table) => [table, Number((database.prepare(`SELECT COUNT(*) count FROM ${table}`).get() as { count: number }).count)]));
    const before = counts();
    storeMemory(persistence, goalMemory('information-only'));
    expect(counts()).toEqual(before);
    database.close();
  });

  it('migrates populated schema 17 without fabricating memories', () => {
    persistence.close();
    const database = new DatabaseSync(path);
    database.exec(`DROP TRIGGER memory_records_no_delete;
      DROP TRIGGER memory_records_no_update;
      DROP INDEX idx_memory_reusable_retrieval;
      DROP INDEX idx_memory_goal_retrieval;
      DROP TABLE memory_records;
      DROP TABLE memory_decision_links;
      DELETE FROM schema_migrations WHERE version>=18;
      PRAGMA user_version=17;`);
    database.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath: path }); persistence.initialize();
    expect(persistence.getSchemaVersion()).toBe(19);
    expect(persistence.getGoal(goalId)?.goal.id).toBe(goalId);
    expect(retrieveMemories(persistence, { goalId, includeReusable: true, asOf: LATER })).toEqual([]);
  });
});

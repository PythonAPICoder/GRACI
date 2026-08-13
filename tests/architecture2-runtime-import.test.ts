import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DeterministicTestProvider } from '../src/architecture2/execution/index.js';
import { assessLegacyState } from '../src/architecture2/legacy/index.js';
import { bootstrapArchitecture2, type Architecture2Runtime } from '../src/architecture2/runtime/index.js';
import { DeterministicVerifier } from '../src/architecture2/verification/index.js';

const IMPORTED_AT = '2026-08-13T21:00:00.000Z';

describe('Architecture 2 Phase 1E runtime and legacy import', () => {
  let directory: string;
  let databasePath: string;
  let legacyPath: string;
  let runtime: Architecture2Runtime | undefined;

  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'graci-phase1e-'));
    databasePath = join(directory, 'architecture2.sqlite');
    legacyPath = join(directory, 'graci_state.json');
  });

  afterEach(() => {
    runtime?.close();
    rmSync(directory, { recursive: true, force: true });
  });

  function write(value: unknown): Buffer {
    const source = Buffer.from(JSON.stringify(value, null, 2));
    writeFileSync(legacyPath, source);
    return source;
  }

  function bootstrap(): Architecture2Runtime {
    return bootstrapArchitecture2({ databasePath, executionProvider: new DeterministicTestProvider(),
      verifier: new DeterministicVerifier() });
  }

  it('assesses valid state deterministically without promoting registries or completed lifecycle evidence', () => {
    write({
      registeredModels: { local: 'qwen' },
      tasks: {
        completed: { id: 'completed', type: 'legacy-work', status: 'completed', createdAt: 1, completedAt: 2 },
        pending: { id: 'pending', type: 'legacy-work', status: 'pending', createdAt: 3 },
      },
    });
    const first = assessLegacyState(legacyPath);
    const second = assessLegacyState(legacyPath);
    expect(second).toEqual(first);
    expect(first.counts).toEqual({ importable: 2, unsupported: 1, ambiguous: 0, malformed: 0 });
    expect(first.records.map(({ section, key, classification, reason }) => ({ section, key, classification, reason }))).toEqual([
      { section: 'registeredModels', key: 'local', classification: 'unsupported', reason: 'legacy_registry_not_qualified' },
      { section: 'tasks', key: 'completed', classification: 'importable', reason: 'legacy_task_history_preservable' },
      { section: 'tasks', key: 'pending', classification: 'importable', reason: 'legacy_task_history_preservable' },
    ]);
  });

  it('handles empty and partially populated state explicitly', () => {
    write({});
    expect(assessLegacyState(legacyPath).records).toEqual([]);
    write({ tasks: {}, registeredTools: {} });
    expect(assessLegacyState(legacyPath).records).toEqual([]);
  });

  it.each([
    ['invalid JSON', '{', 'invalid_json'],
    ['array root', '[]', 'state_root_must_be_object'],
    ['malformed section', '{"tasks":[]}', 'section_must_be_object'],
  ])('classifies malformed %s', (_name, source, reason) => {
    writeFileSync(legacyPath, source);
    expect(assessLegacyState(legacyPath).records).toEqual([
      expect.objectContaining({ classification: 'malformed', reason }),
    ]);
  });

  it('classifies unsupported, ambiguous, and malformed records without guessing', () => {
    write({
      future: { anything: true },
      registeredNodes: { node: { host: 'legacy' } },
      tasks: {
        mismatch: { id: 'different', type: 'work', status: 'pending', createdAt: 1 },
        missingType: { id: 'missingType', status: 'pending', createdAt: 1 },
        unsupportedStatus: { id: 'unsupportedStatus', type: 'work', status: 'paused', createdAt: 1 },
        badTimestamp: { id: 'badTimestamp', type: 'work', status: 'failed', createdAt: 'yesterday' },
        scalar: 'not-a-task',
      },
    });
    const assessment = assessLegacyState(legacyPath);
    expect(assessment.counts).toEqual({ importable: 0, unsupported: 3, ambiguous: 2, malformed: 2 });
    expect(assessment.records.map((entry) => entry.reason)).toEqual([
      'unknown_top_level_section', 'legacy_registry_not_qualified', 'task_created_at_invalid',
      'task_id_key_mismatch', 'task_type_missing', 'task_must_be_object', 'task_status_unsupported',
    ]);
  });

  it('imports non-canonical history idempotently with provenance and leaves source untouched', () => {
    const source = write({ tasks: {
      done: { id: 'done', type: 'legacy-work', status: 'completed', createdAt: 1, completedAt: 2 },
      bad: { id: 'wrong', type: 'legacy-work', status: 'pending', createdAt: 3 },
    } });
    runtime = bootstrap();
    const first = runtime.importLegacy(legacyPath, { operationId: 'legacy-import-1', importedAt: IMPORTED_AT });
    const second = runtime.importLegacy(legacyPath, { operationId: 'legacy-import-2', importedAt: '2026-08-13T22:00:00.000Z' });
    expect(first).toMatchObject({ created: true, insertedRecordCount: 1 });
    expect(second).toMatchObject({ created: false, insertedRecordCount: 0, operation: { id: 'legacy-import-1' } });
    expect(readFileSync(legacyPath)).toEqual(source);
    const history = runtime.persistence.getLegacyHistory(first.operation.sourceDigest);
    expect(history).toEqual([expect.objectContaining({ sourceReference: legacyPath, sourceSection: 'tasks', sourceKey: 'done',
      legacyStatus: 'completed', payload: expect.objectContaining({ status: 'completed' }), assessmentVersion: 1 })]);
    expect(runtime.persistence.getEvents()).toEqual([]);
  });

  it('durably records an idempotent import operation when no records are eligible', () => {
    write({ registeredTools: { shell: 'legacy shell' } });
    runtime = bootstrap();
    const assessment = runtime.assessLegacy(legacyPath);
    expect(assessment.counts.importable).toBe(0);
    const first = runtime.importLegacy(legacyPath, { operationId: 'legacy-import-empty', importedAt: IMPORTED_AT });
    const second = runtime.importLegacy(legacyPath,
      { operationId: 'legacy-import-empty-repeat', importedAt: '2026-08-13T22:00:00.000Z' });
    expect(first).toMatchObject({ created: true, insertedRecordCount: 0,
      operation: { id: 'legacy-import-empty', importedRecordCount: 0 } });
    expect(runtime.persistence.getLegacyImport(assessment.sourceDigest)).toEqual(first.operation);
    expect(runtime.persistence.getLegacyHistory(assessment.sourceDigest)).toEqual([]);
    expect(second).toEqual({ operation: first.operation, created: false, insertedRecordCount: 0 });
  });

  it('bootstraps a real SQLite runtime, imports, closes, reopens, and reconstructs durable history', () => {
    write({ tasks: { one: { id: 'one', type: 'legacy-work', status: 'failed', createdAt: 1, errorMessage: 'legacy failure' } } });
    runtime = bootstrap();
    expect(runtime.persistence.getSchemaVersion()).toBe(8);
    const imported = runtime.importLegacy(legacyPath, { operationId: 'legacy-import-reopen', importedAt: IMPORTED_AT });
    runtime.close();
    runtime = bootstrap();
    expect(runtime.persistence.getLegacyImport(imported.operation.sourceDigest)).toEqual(imported.operation);
    expect(runtime.persistence.getLegacyHistory()).toEqual([
      expect.objectContaining({ importOperationId: 'legacy-import-reopen', sourceKey: 'one', legacyStatus: 'failed' }),
    ]);
  });
});

import { createHash, randomUUID } from 'node:crypto';
import { readFileSync } from 'node:fs';
import type { Architecture2Persistence, LegacyImportResult } from '../persistence/index.js';

export const LEGACY_ASSESSMENT_VERSION = 1;

export type LegacyClassification = 'importable' | 'unsupported' | 'ambiguous' | 'malformed';

export interface LegacyAssessmentRecord {
  section: string;
  key: string;
  classification: LegacyClassification;
  reason: string;
  payload?: Record<string, unknown>;
}

export interface LegacyStateAssessment {
  assessmentVersion: number;
  sourceReference: string;
  sourceDigest: string;
  records: LegacyAssessmentRecord[];
  counts: Record<LegacyClassification, number>;
}

export interface LegacyImportOptions {
  importedAt?: string;
  operationId?: string;
}

const KNOWN_SECTIONS = new Set([
  'registeredTools', 'registeredCapabilities', 'registeredModels', 'registeredNodes', 'tasks',
]);
const REGISTRY_SECTIONS = new Set(['registeredTools', 'registeredCapabilities', 'registeredModels', 'registeredNodes']);
const LEGACY_STATUSES = new Set(['pending', 'running', 'completed', 'failed']);

function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function record(section: string, key: string, classification: LegacyClassification, reason: string,
  payload?: Record<string, unknown>): LegacyAssessmentRecord {
  return { section, key, classification, reason, payload };
}

function classifyTask(key: string, value: unknown): LegacyAssessmentRecord {
  if (!key.trim()) return record('tasks', key, 'malformed', 'empty_record_key');
  if (!isObject(value)) return record('tasks', key, 'malformed', 'task_must_be_object');
  if (typeof value.id !== 'string' || !value.id.trim()) return record('tasks', key, 'ambiguous', 'task_id_missing');
  if (value.id !== key) return record('tasks', key, 'ambiguous', 'task_id_key_mismatch');
  if (typeof value.type !== 'string' || !value.type.trim()) return record('tasks', key, 'ambiguous', 'task_type_missing');
  if (typeof value.status !== 'string' || !LEGACY_STATUSES.has(value.status)) {
    return record('tasks', key, 'unsupported', 'task_status_unsupported');
  }
  if (typeof value.createdAt !== 'number' || !Number.isFinite(value.createdAt) || value.createdAt < 0) {
    return record('tasks', key, 'malformed', 'task_created_at_invalid');
  }
  for (const field of ['startedAt', 'completedAt'] as const) {
    const fieldValue = value[field];
    if (fieldValue !== undefined && (typeof fieldValue !== 'number' || !Number.isFinite(fieldValue) || fieldValue < 0)) {
      return record('tasks', key, 'malformed', `task_${field}_invalid`);
    }
  }
  if (value.errorMessage !== undefined && typeof value.errorMessage !== 'string') {
    return record('tasks', key, 'malformed', 'task_error_message_invalid');
  }
  return record('tasks', key, 'importable', 'legacy_task_history_preservable', value);
}

function emptyCounts(): Record<LegacyClassification, number> {
  return { importable: 0, unsupported: 0, ambiguous: 0, malformed: 0 };
}

export function assessLegacyState(sourceReference: string): LegacyStateAssessment {
  if (!sourceReference.trim()) throw new Error('A legacy source reference is required');
  const source = readFileSync(sourceReference);
  const sourceDigest = createHash('sha256').update(source).digest('hex');
  const records: LegacyAssessmentRecord[] = [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(source.toString('utf8'));
  } catch {
    records.push(record('$root', '$root', 'malformed', 'invalid_json'));
  }
  if (records.length === 0 && !isObject(parsed)) {
    records.push(record('$root', '$root', 'malformed', 'state_root_must_be_object'));
  }
  if (records.length === 0) {
    for (const section of Object.keys(parsed as Record<string, unknown>).sort()) {
      const value = (parsed as Record<string, unknown>)[section];
      if (!KNOWN_SECTIONS.has(section)) {
        records.push(record(section, '$section', 'unsupported', 'unknown_top_level_section'));
        continue;
      }
      if (!isObject(value)) {
        records.push(record(section, '$section', 'malformed', 'section_must_be_object'));
        continue;
      }
      for (const key of Object.keys(value).sort()) {
        if (REGISTRY_SECTIONS.has(section)) {
          records.push(record(section, key, 'unsupported', 'legacy_registry_not_qualified'));
        } else {
          records.push(classifyTask(key, value[key]));
        }
      }
    }
  }
  records.sort((left, right) => left.section.localeCompare(right.section) || left.key.localeCompare(right.key));
  const counts = emptyCounts();
  for (const entry of records) counts[entry.classification] += 1;
  return { assessmentVersion: LEGACY_ASSESSMENT_VERSION, sourceReference, sourceDigest, records, counts };
}

export function importLegacyState(assessment: LegacyStateAssessment, persistence: Architecture2Persistence,
  options: LegacyImportOptions = {}): LegacyImportResult {
  const importedAt = options.importedAt ?? new Date().toISOString();
  const operationId = options.operationId ?? `legacy-import-${randomUUID()}`;
  const importable = assessment.records.filter((entry) => entry.classification === 'importable');
  return persistence.importLegacyHistory({
    operation: { id: operationId, sourceDigest: assessment.sourceDigest, sourceReference: assessment.sourceReference,
      assessmentVersion: assessment.assessmentVersion, importedRecordCount: importable.length, importedAt },
    records: importable.map((entry) => ({ importOperationId: operationId, sourceDigest: assessment.sourceDigest,
      sourceReference: assessment.sourceReference, sourceSection: entry.section, sourceKey: entry.key,
      legacyStatus: String(entry.payload?.status), payload: entry.payload!, assessmentVersion: assessment.assessmentVersion, importedAt })),
  });
}

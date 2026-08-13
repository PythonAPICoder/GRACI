import { createHash } from 'node:crypto';
import type {
  Node,
  WindowsProcessSnapshot,
  WorkstationWorkloadEvaluation,
  WorkstationWorkloadRules,
} from '../domain/index.js';
import type { WorkstationWorkloadEvaluationId } from '../domain/ids.js';

export interface WorkstationWorkloadEvaluationRequest {
  id: WorkstationWorkloadEvaluationId;
  evaluatedAt: string;
}

function normalizeBasename(value: string): string {
  const normalized = value.toLocaleLowerCase('en-US');
  if (!normalized || normalized !== normalized.trim() || /[\\/\x00-\x1f]/.test(normalized)) {
    throw new Error(`Invalid executable basename: ${JSON.stringify(value)}`);
  }
  return normalized;
}

export function evaluateWorkstationWorkload(
  node: Node,
  rules: WorkstationWorkloadRules,
  snapshot: WindowsProcessSnapshot,
  request: WorkstationWorkloadEvaluationRequest,
): WorkstationWorkloadEvaluation {
  if (!Number.isInteger(rules.version) || rules.version < 1) throw new Error('Rule version must be a positive integer');
  const canonicalRules = rules.rules.map((rule) => ({
    id: rule.id,
    executableBasenames: [...new Set(rule.executableBasenames.map(normalizeBasename))].sort(),
  })).sort((left, right) => left.id.localeCompare(right.id, 'en-US'));
  if (canonicalRules.some((rule) => !rule.id || rule.id !== rule.id.trim())) throw new Error('Rule IDs must be non-empty');
  if (new Set(canonicalRules.map((rule) => rule.id)).size !== canonicalRules.length) throw new Error('Rule IDs must be unique');

  const processBasenames = [...new Set(snapshot.processBasenames.map(normalizeBasename))].sort();
  const running = new Set(processBasenames);
  const matchedRuleIds = canonicalRules
    .filter((rule) => rule.executableBasenames.some((basename) => running.has(basename)))
    .map((rule) => rule.id);
  const ruleFingerprint = createHash('sha256')
    .update(JSON.stringify({ version: rules.version, rules: canonicalRules }))
    .digest('hex');

  return {
    id: request.id,
    nodeId: node.id,
    ruleFingerprint,
    processBasenames,
    matchedRuleIds,
    recommendation: snapshot.completeness === 'incomplete'
      ? 'inconclusive'
      : matchedRuleIds.length > 0 ? 'recommend_draining' : 'recommend_active',
    evaluatedAt: request.evaluatedAt,
  };
}

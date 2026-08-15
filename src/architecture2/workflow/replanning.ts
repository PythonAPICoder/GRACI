import { assertIdentifier, type AuditEventInput, type MemoryId, type ReplanningDecision, type Task,
  type TaskDependency, type TaskGraphRevision } from '../domain/index.js';
import type { ResearchEvidenceId } from '../domain/index.js';
import type { Architecture2Persistence } from '../persistence/index.js';
import { PHASE_1L_DIAGNOSIS_POLICY_ID, PHASE_1L_DIAGNOSIS_POLICY_VERSION } from './failure-diagnoser.js';
import { validateTaskGraph } from './task-graph-validator.js';
import { normalizeMemoryCitations } from './memory.js';

export interface AuthorizeReplanningCommand {
  id: ReplanningDecision['id'];
  diagnosisId: ReplanningDecision['diagnosisId'];
  revision: TaskGraphRevision;
  tasks: readonly Task[];
  dependencies: readonly TaskDependency[];
  replacements: ReplanningDecision['replacements'];
  reason: string;
  actor: string;
  authorizedAt: string;
  eventIds: readonly ReplanningDecision['eventId'][];
  researchEvidenceId?: ResearchEvidenceId;
  memoryIds?: readonly MemoryId[];
}

export function authorizeReplanning(persistence: Architecture2Persistence,
  command: AuthorizeReplanningCommand): ReplanningDecision {
  assertIdentifier(command.id, 'replanning decision id');
  assertIdentifier(command.diagnosisId, 'failure diagnosis id');
  if (command.researchEvidenceId) assertIdentifier(command.researchEvidenceId, 'research evidence id');
  const memoryIds = normalizeMemoryCitations(command.memoryIds);
  if (!command.reason.trim() || !command.actor.trim()) throw new Error('Replanning reason and actor are required');
  const time = new Date(command.authorizedAt);
  if (Number.isNaN(time.valueOf()) || time.toISOString() !== command.authorizedAt) {
    throw new Error('Replanning authorization time must be canonical UTC');
  }
  const existing = persistence.getReplanningDecisionByDiagnosis(command.diagnosisId);
  if (existing) {
    const link = persistence.getResearchRecoveryLinkByReplanningDecision(existing.id);
    const cited = persistence.getMemoryDecisionLinksByReplanningDecision(existing.id).map((item) => item.memoryId);
    if (existing.id !== command.id || existing.replacementGraphRevisionId !== command.revision.id ||
        link?.evidenceId !== command.researchEvidenceId || (!link && command.researchEvidenceId) ||
        JSON.stringify([...cited].sort()) !== JSON.stringify(memoryIds)) {
      throw new Error(`Replanning authority conflict: ${command.diagnosisId}`);
    }
    return existing;
  }
  validateTaskGraph(command.revision, command.tasks, command.dependencies);
  const diagnosis = persistence.getFailureDiagnosisById(command.diagnosisId);
  if (!diagnosis || diagnosis.policyId !== PHASE_1L_DIAGNOSIS_POLICY_ID ||
      diagnosis.policyVersion !== PHASE_1L_DIAGNOSIS_POLICY_VERSION ||
       diagnosis.disposition !== (command.researchEvidenceId ? 'research_recommended' : 'replanning_recommended') ||
       diagnosis.outcomeCertainty !== 'proven_unsuccessful') {
    throw new Error('Replanning source authority is stale, contradictory, or ineligible');
  }
  const sourceTask = persistence.getTask(diagnosis.taskId);
  if (!sourceTask) throw new Error(`Replanning source Task not found: ${diagnosis.taskId}`);
  if (persistence.getFailure(diagnosis.failureId)?.code !== 'TASK_GRAPH_STRUCTURE_INVALID') {
    throw new Error('Replanning requires TASK_GRAPH_STRUCTURE_INVALID source authority');
  }
  const goal = persistence.getGoal(sourceTask.goalId)?.goal;
  if (!goal || goal.activeGraphRevisionId !== sourceTask.graphRevisionId) {
    throw new Error('Replanning source graph is not authoritative');
  }
  const expectedEvents = 1 + command.tasks.length + command.dependencies.length + command.replacements.length;
  if (command.eventIds.length !== expectedEvents) throw new Error(`Replanning requires exactly ${expectedEvents} events`);
  const value: ReplanningDecision = { id: command.id, goalId: goal.id,
    sourceGraphRevisionId: sourceTask.graphRevisionId, replacementGraphRevisionId: command.revision.id,
    diagnosisId: diagnosis.id, failureId: diagnosis.failureId, sourceTaskId: sourceTask.id,
    replacements: command.replacements, reason: command.reason, actor: command.actor,
    authorizedAt: command.authorizedAt, eventId: command.eventIds[0]! };
  const events: AuditEventInput[] = command.eventIds.map((id, index) => ({ id, aggregateType: 'goal',
    aggregateId: goal.id, eventType: index === 0 ? 'graph-revision.activated' : 'graph-revision.structure',
    eventVersion: 1, actor: command.actor, occurredAt: command.authorizedAt,
    payload: { replanningDecisionId: value.id, replacementGraphRevisionId: command.revision.id, index } }));
  return persistence.authorizeReplanning(value, command.revision, command.tasks, command.dependencies, goal.version, events,
    command.researchEvidenceId, memoryIds);
}

import { assertIdentifier, type AuditEventInput, type JsonObject, type ResearchDecision,
  type ResearchEvidence, type ResearchRequest } from '../domain/index.js';
import type { Architecture2Persistence } from '../persistence/index.js';

export interface CreateResearchRequestCommand {
  id: ResearchRequest['id'];
  diagnosisId: ResearchRequest['diagnosisId'];
  question: string;
  purpose: string;
  requestedBy: string;
  requestedAt: string;
  eventId: ResearchRequest['eventId'];
}

export interface RecordResearchEvidenceCommand {
  id: ResearchEvidence['id'];
  requestId: ResearchEvidence['requestId'];
  supplierId: string;
  supplierType: string;
  suppliedAt: string;
  source: string;
  reference: string;
  content: JsonObject;
  integrity?: JsonObject;
  recordedBy: string;
  recordedAt: string;
  eventId: ResearchEvidence['eventId'];
}

export interface DecideResearchEvidenceCommand {
  id: ResearchDecision['id'];
  evidenceId: ResearchDecision['evidenceId'];
  decision: ResearchDecision['decision'];
  actor: string;
  reason: string;
  decidedAt: string;
  eventId: ResearchDecision['eventId'];
}

export function createResearchRequest(persistence: Architecture2Persistence,
  command: CreateResearchRequestCommand): ResearchRequest {
  assertIdentifier(command.id, 'research request id');
  assertIdentifier(command.diagnosisId, 'research diagnosis id');
  assertIdentifier(command.eventId, 'research request event id');
  const diagnosis = persistence.getFailureDiagnosisById(command.diagnosisId);
  if (!diagnosis) throw new Error(`Failure diagnosis not found: ${command.diagnosisId}`);
  const task = persistence.getTask(diagnosis.taskId);
  if (!task || !diagnosis.attemptId) throw new Error('Research request requires exact Goal, Task, and Attempt context');
  const value: ResearchRequest = { id: command.id, goalId: task.goalId, taskId: task.id,
    attemptId: diagnosis.attemptId, failureId: diagnosis.failureId, diagnosisId: diagnosis.id,
    question: command.question, purpose: command.purpose, requestedBy: command.requestedBy,
    requestedAt: command.requestedAt, eventId: command.eventId };
  return persistence.createResearchRequest(value, researchEvent(command.eventId, value.id, 'research.requested',
    command.requestedBy, command.requestedAt, { diagnosisId: diagnosis.id }));
}

export function recordResearchEvidence(persistence: Architecture2Persistence,
  command: RecordResearchEvidenceCommand): ResearchEvidence {
  const value: ResearchEvidence = { ...command };
  return persistence.recordResearchEvidence(value, researchEvent(command.eventId, command.requestId,
    'research.evidence-recorded', command.recordedBy, command.recordedAt, { evidenceId: command.id }));
}

export function decideResearchEvidence(persistence: Architecture2Persistence,
  command: DecideResearchEvidenceCommand): ResearchDecision {
  const value: ResearchDecision = { ...command };
  const event: AuditEventInput = { id: command.eventId, aggregateType: 'research_evidence',
    aggregateId: command.evidenceId, eventType: `research.${command.decision}`, eventVersion: 1,
    actor: command.actor, occurredAt: command.decidedAt, payload: { decisionId: command.id, reason: command.reason } };
  return persistence.decideResearchEvidence(value, event);
}

function researchEvent(id: AuditEventInput['id'], aggregateId: string, eventType: string, actor: string,
  occurredAt: string, payload: JsonObject): AuditEventInput {
  return { id, aggregateType: 'research_request', aggregateId, eventType, eventVersion: 1, actor, occurredAt, payload };
}

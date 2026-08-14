import { assertIdentifier, type AuditEventInput, type JsonObject, type ResearchDecision,
  type ResearchEvidence, type ResearchRequest } from '../domain/index.js';
import type { Architecture2Persistence } from '../persistence/index.js';
import { DeterministicProviderResolver, RESEARCH_PROVIDER_CONTRACT_VERSION,
  type ResearchProvider } from '../providers/index.js';

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

export interface ExecuteResearchRequestCommand {
  executionId: import('../domain/index.js').ResearchProviderExecution['id'];
  requestId: ResearchRequest['id'];
  resolutionRequest: import('../domain/index.js').ProviderResolutionRequest;
  evidenceId: ResearchEvidence['id'];
  startedAt: string;
  deadline: string;
  completedAt: string;
  actor: string;
  resolutionEventId: AuditEventInput['id'];
  startEventId: AuditEventInput['id'];
  evidenceEventId: AuditEventInput['id'];
  completionEventId: AuditEventInput['id'];
}

export interface ExecuteResearchRequestOptions {
  resolveProvider: (offeringId: import('../domain/index.js').ProviderOfferingId) => ResearchProvider | undefined;
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

export async function executeResearchRequest(persistence: Architecture2Persistence,
  command: ExecuteResearchRequestCommand, options: ExecuteResearchRequestOptions) {
  const request = persistence.getResearchRequest(command.requestId);
  if (!request) throw new Error(`Research request not found: ${command.requestId}`);
  const task = persistence.getTask(request.taskId);
  if (!task) throw new Error(`Research request Task not found: ${request.taskId}`);
  if (command.resolutionRequest.requestedAt !== command.startedAt ||
      command.resolutionRequest.privacyClass !== task.privacyClass ||
      command.resolutionRequest.contractVersion !== RESEARCH_PROVIDER_CONTRACT_VERSION) {
    throw new Error('Research provider resolution request does not match governed request context');
  }
  const resolver = new DeterministicProviderResolver(persistence, { nextEvent: (decision) => ({
    id: command.resolutionEventId, aggregateType: 'provider-resolution', aggregateId: decision.request.id,
    eventType: 'provider.resolved', eventVersion: 1, actor: command.actor, occurredAt: command.startedAt,
    payload: { researchRequestId: request.id },
  }) });
  const resolution = resolver.resolve(command.resolutionRequest);
  if (!resolution.selectedOfferingId) throw new Error('No eligible research provider offering');
  const offering = persistence.getProviderOfferings().find((value) => value.id === resolution.selectedOfferingId);
  if (!offering) throw new Error('Selected research provider offering is missing');
  const provider = options.resolveProvider(offering.id);
  if (!provider || provider.providerId !== offering.providerId || provider.offeringId !== offering.id ||
      provider.contractVersion !== RESEARCH_PROVIDER_CONTRACT_VERSION) {
    throw new Error('Resolved research provider adapter does not match selected offering');
  }
  const execution: import('../domain/index.js').ResearchProviderExecution = {
    id: command.executionId, requestId: request.id, resolutionDecisionId: resolution.request.id,
    providerId: provider.providerId, offeringId: provider.offeringId,
    providerContractVersion: provider.contractVersion, idempotencyKey: `research:${request.id}`,
    status: 'running', startedAt: command.startedAt, startEventId: command.startEventId,
  };
  persistence.startResearchProviderExecution(execution, {
    id: command.startEventId, aggregateType: 'research_provider_execution', aggregateId: execution.id,
    eventType: 'research.provider-execution-started', eventVersion: 1, actor: command.actor,
    occurredAt: command.startedAt, payload: { requestId: request.id, providerId: provider.providerId,
      offeringId: provider.offeringId, resolutionDecisionId: resolution.request.id },
  });
  let result: Awaited<ReturnType<ResearchProvider['research']>>;
  try {
    result = await provider.research({ requestId: request.id, question: request.question, purpose: request.purpose,
      privacyClass: task.privacyClass, idempotencyKey: execution.idempotencyKey, deadline: command.deadline });
  } catch (error) {
    result = { status: 'non_retryable_failure', failure: { code: 'RESEARCH_PROVIDER_EXCEPTION',
      summary: error instanceof Error ? error.message : 'Research provider threw a non-Error value' } };
  }
  if (result.status === 'success') {
    const evidence: ResearchEvidence = { id: command.evidenceId, requestId: request.id,
      supplierId: String(provider.providerId), supplierType: 'research_provider', suppliedAt: result.value.suppliedAt,
      source: result.value.source, reference: result.value.reference, content: result.value.content,
      ...(result.value.integrity ? { integrity: result.value.integrity } : {}), recordedBy: command.actor,
      recordedAt: command.completedAt, eventId: command.evidenceEventId };
    const completed = { ...execution, status: 'succeeded' as const, completedAt: command.completedAt,
      evidenceId: evidence.id, completionEventId: command.completionEventId };
    return persistence.completeResearchProviderExecution(completed, evidence, [
      researchEvent(command.evidenceEventId, request.id, 'research.evidence-recorded', command.actor,
        command.completedAt, { evidenceId: evidence.id, executionId: execution.id }),
      executionCompletionEvent(command, execution.id, 'research.provider-execution-succeeded', {}),
    ]);
  }
  const indeterminate = result.status === 'indeterminate_outcome';
  const completed = { ...execution, status: indeterminate ? 'indeterminate' as const : 'failed' as const,
    completedAt: command.completedAt, failureCategory: indeterminate ? 'external_outcome_indeterminate' as const :
      result.status === 'retryable_failure' ? 'transient_infrastructure' as const : 'execution_defect' as const,
    failureClassification: indeterminate ? 'external_outcome_indeterminate' as const :
      result.status === 'retryable_failure' ? 'transient' as const : 'permanent' as const,
    failureCode: result.failure.code, failureSummary: result.failure.summary,
    completionEventId: command.completionEventId };
  return persistence.completeResearchProviderExecution(completed, undefined, [executionCompletionEvent(command,
    execution.id, indeterminate ? 'research.provider-execution-indeterminate' : 'research.provider-execution-failed',
    { code: result.failure.code })]);
}

function executionCompletionEvent(command: ExecuteResearchRequestCommand, executionId: string,
  eventType: string, payload: JsonObject): AuditEventInput {
  return { id: command.completionEventId, aggregateType: 'research_provider_execution', aggregateId: executionId,
    eventType, eventVersion: 1, actor: command.actor, occurredAt: command.completedAt, payload };
}

function researchEvent(id: AuditEventInput['id'], aggregateId: string, eventType: string, actor: string,
  occurredAt: string, payload: JsonObject): AuditEventInput {
  return { id, aggregateType: 'research_request', aggregateId, eventType, eventVersion: 1, actor, occurredAt, payload };
}

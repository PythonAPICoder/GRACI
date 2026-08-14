declare const identifierBrand: unique symbol;

export type Identifier<Kind extends string> = string & {
  readonly [identifierBrand]: Kind;
};

export type GoalId = Identifier<'Goal'>;
export type GoalCriterionId = Identifier<'GoalCriterion'>;
export type TaskGraphRevisionId = Identifier<'TaskGraphRevision'>;
export type TaskId = Identifier<'Task'>;
export type AttemptId = Identifier<'Attempt'>;
export type VerificationId = Identifier<'Verification'>;
export type FailureId = Identifier<'Failure'>;
export type ApprovalId = Identifier<'Approval'>;
export type ArtifactId = Identifier<'Artifact'>;
export type EventId = Identifier<'Event'>;
export type ProviderId = Identifier<'Provider'>;
export type CapabilityId = Identifier<'Capability'>;
export type ProviderOfferingId = Identifier<'ProviderOffering'>;
export type QualificationId = Identifier<'Qualification'>;
export type HealthObservationId = Identifier<'HealthObservation'>;
export type ResolutionDecisionId = Identifier<'ResolutionDecision'>;
export type NodeId = Identifier<'Node'>;
export type OfferingLocationId = Identifier<'OfferingLocation'>;
export type NodeHealthObservationId = Identifier<'NodeHealthObservation'>;
export type ResourceSchedulingDecisionId = Identifier<'ResourceSchedulingDecision'>;
export type ResourceLeaseId = Identifier<'ResourceLease'>;
export type NodeInspectionId = Identifier<'NodeInspection'>;
export type WorkstationWorkloadEvaluationId = Identifier<'WorkstationWorkloadEvaluation'>;
export type WorkstationAvailabilityPolicyApplicationId = Identifier<'WorkstationAvailabilityPolicyApplication'>;
export type FailureDiagnosisId = Identifier<'FailureDiagnosis'>;
export type ChangedConditionEvidenceId = Identifier<'ChangedConditionEvidence'>;
export type AlternativeRecoveryDecisionId = Identifier<'AlternativeRecoveryDecision'>;
export type ReconciliationDecisionId = Identifier<'ReconciliationDecision'>;
export type CircuitId = Identifier<'Circuit'>;
export type CircuitTransitionId = Identifier<'CircuitTransition'>;
export type CircuitEvidenceId = Identifier<'CircuitEvidence'>;
export type CircuitProbeId = Identifier<'CircuitProbe'>;
export type InputRevisionId = Identifier<'InputRevision'>;
export type ReplanningDecisionId = Identifier<'ReplanningDecision'>;
export type ResearchRequestId = Identifier<'ResearchRequest'>;
export type ResearchEvidenceId = Identifier<'ResearchEvidence'>;
export type ResearchDecisionId = Identifier<'ResearchDecision'>;

const IDENTIFIER_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;

export function asIdentifier<Kind extends string>(value: string): Identifier<Kind> {
  if (!IDENTIFIER_PATTERN.test(value)) {
    throw new Error(`Invalid identifier: ${JSON.stringify(value)}`);
  }
  return value as Identifier<Kind>;
}

export function assertIdentifier(value: string, label: string): void {
  if (!IDENTIFIER_PATTERN.test(value)) {
    throw new Error(`Invalid ${label}: ${JSON.stringify(value)}`);
  }
}

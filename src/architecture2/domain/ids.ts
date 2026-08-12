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

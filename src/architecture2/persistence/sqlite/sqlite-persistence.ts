import { createHash } from 'node:crypto';
import { dirname, resolve } from 'node:path';
import { mkdirSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';
import type {
  Approval,
  ArtifactMetadata,
  Attempt,
  AuditEvent,
  AuditEventInput,
  Failure,
  Goal,
  GoalBundle,
  GoalId,
  GoalSuccessCriterion,
  JsonObject,
  Task,
  TaskDependency,
  TaskGraphRevision,
  TaskGraphRevisionId,
  TaskId,
  Verification,
  Provider, Capability, ProviderOffering, ProviderRegistration, Qualification, ProviderHealthObservation,
  ProviderResolutionDecision,
  Node, OfferingLocation, NodeHealthObservation, NodeInspectionObservation, ResourceSchedulingDecision, ResourceLease,
  WorkstationWorkloadEvaluation, WorkstationAvailabilityPolicyApplication,
  WorkstationAvailabilityPolicyApplicationRequest,
  FailureDiagnosis, FailureDiagnosisId, FailureId, ChangedConditionEvidence,
  AlternativeRecoveryDecision, AlternativeRecoveryDecisionId,
  ReconciliationDecision, ReconciliationDecisionId,
  CircuitRecord, CircuitTransition, CircuitEvidence, CircuitProbe, CircuitBreakerPolicy, CircuitTargetType,
} from '../../domain/index.js';
import { assertIdentifier } from '../../domain/index.js';
import type {
  Architecture2Persistence,
  LegacyHistoryRecord,
  LegacyImportOperation,
  LegacyImportResult,
  LegacyImportWrite,
} from '../contract.js';
import { validateTaskGraph } from '../../workflow/task-graph-validator.js';
import { migrate } from './migrations.js';

type Row = Record<string, unknown>;

const TASK_STATUSES = new Set<Task['status']>([
  'planned', 'blocked', 'ready', 'waiting_for_approval', 'scheduled', 'running', 'verifying',
  'retry_pending', 'succeeded', 'failed', 'cancelled', 'superseded',
]);
const TASK_PRIORITIES = new Set<Task['priority']>(['critical', 'interactive', 'normal', 'background', 'idle']);
const PRIVACY_CLASSES = new Set<Task['privacyClass']>(['public', 'internal', 'personal', 'confidential', 'secret']);
const ATTEMPT_STATUSES = new Set<Attempt['status']>(['created', 'running', 'succeeded', 'failed', 'cancelled', 'indeterminate']);
const FAILURE_CATEGORIES = new Set<Failure['category']>(['transient_infrastructure', 'resource_unavailable',
  'provider_or_capability_mismatch', 'invalid_input_or_precondition', 'policy_or_approval', 'execution_defect',
  'verification_failure', 'external_outcome_indeterminate', 'cancelled_or_preempted', 'unknown']);
const FAILURE_CLASSIFICATIONS = new Set<Failure['classification']>(['transient', 'permanent', 'verification_failed',
  'approval_required', 'external_outcome_indeterminate']);
const OUTCOME_CERTAINTIES = new Set<FailureDiagnosis['outcomeCertainty']>(['proven_completed', 'proven_unsuccessful',
  'indeterminate_external_outcome', 'insufficient_or_malformed_evidence']);
const RECOVERY_DISPOSITIONS = new Set<FailureDiagnosis['disposition']>(['terminal_failure', 'retry_same_path',
  'alternative_offering_recommended', 'alternative_node_recommended', 'reconciliation_required', 'approval_required',
  'input_revision_required', 'replanning_recommended', 'research_recommended']);

export interface SqlitePersistenceOptions {
  databasePath: string;
}

function canonicalize(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(',')}]`;
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${canonicalize(object[key])}`).join(',')}}`;
}

function json(value: unknown): string {
  return canonicalize(value);
}

function parseObject(value: unknown): JsonObject {
  let parsed: unknown;
  try {
    parsed = JSON.parse(String(value));
  } catch {
    throw new Error('Corrupt persisted JSON object');
  }
  if (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error('Corrupt persisted JSON: expected an object');
  }
  return parsed as JsonObject;
}

function parseArray(value: unknown): string[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(String(value));
  } catch {
    throw new Error('Corrupt persisted JSON array');
  }
  if (!Array.isArray(parsed) || parsed.some((entry) => typeof entry !== 'string')) {
    throw new Error('Corrupt persisted JSON: expected a string array');
  }
  return parsed;
}

function optionalString(value: unknown): string | undefined {
  return value === null || value === undefined ? undefined : String(value);
}

function bool(value: unknown): boolean {
  return Number(value) === 1;
}

function validateTimestamp(value: string, label: string): void {
  if (!value || Number.isNaN(Date.parse(value))) throw new Error(`Invalid ${label}: ${JSON.stringify(value)}`);
}

function validateEvent(event: AuditEventInput): void {
  assertIdentifier(event.id, 'event id');
  assertIdentifier(event.aggregateId, 'event aggregate id');
  if (!event.aggregateType.trim() || !event.eventType.trim() || !event.actor.trim()) {
    throw new Error('Event aggregate type, event type, and actor are required');
  }
  if (event.eventVersion < 1 || !Number.isInteger(event.eventVersion)) throw new Error('Event version must be a positive integer');
  validateTimestamp(event.occurredAt, 'event timestamp');
}

export class SqliteArchitecture2Persistence implements Architecture2Persistence {
  private database?: DatabaseSync;
  private readonly databasePath: string;

  constructor(options: SqlitePersistenceOptions) {
    if (!options.databasePath.trim()) throw new Error('A database path is required');
    this.databasePath = options.databasePath === ':memory:' ? ':memory:' : resolve(options.databasePath);
  }

  initialize(): void {
    if (this.database) return;
    if (this.databasePath !== ':memory:') mkdirSync(dirname(this.databasePath), { recursive: true });
    const database = new DatabaseSync(this.databasePath, { enableForeignKeyConstraints: true });
    try {
      database.exec('PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL; PRAGMA synchronous = FULL; PRAGMA busy_timeout = 5000;');
      migrate(database);
      this.database = database;
    } catch (error) {
      database.close();
      throw error;
    }
  }

  close(): void {
    this.database?.close();
    this.database = undefined;
  }

  [Symbol.dispose](): void {
    this.close();
  }

  getSchemaVersion(): number {
    return Number((this.db().prepare('SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations').get() as Row).version);
  }

  registerProvider(value: ProviderRegistration, events: readonly AuditEventInput[]): void {
    assertIdentifier(value.provider.id, 'provider id');
    if (events.length === 0) throw new Error('Provider registration requires an audit event');
    this.transaction(() => {
      const provider = value.provider;
      this.db().prepare(`INSERT INTO providers
        (id, adapter_type, adapter_version, configuration_reference, created_at) VALUES (?, ?, ?, ?, ?)`)
        .run(provider.id, provider.adapterType, provider.adapterVersion, provider.configurationReference, provider.createdAt);
      for (const capability of value.capabilities) {
        this.db().prepare(`INSERT INTO capabilities
          (id, contract_version, description, input_schema_reference, output_schema_reference, created_at)
          VALUES (?, ?, ?, ?, ?, ?)`)
          .run(capability.id, capability.contractVersion, capability.description, capability.inputSchemaReference,
            capability.outputSchemaReference, capability.createdAt);
      }
      for (const offering of value.offerings) {
        this.db().prepare(`INSERT INTO provider_offerings
          (id, provider_id, capability_id, contract_version, model_identity, privacy_destinations_json,
           permissions_json, features_json, supported_formats_json, input_schema_reference, output_schema_reference,
           qualification_fingerprint, quality_level, expected_latency_ms, maximum_cost, side_effect_class, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
          .run(offering.id, offering.providerId, offering.capabilityId, offering.contractVersion,
            offering.modelIdentity ?? null, json(offering.privacyDestinations), json(offering.permissions),
            json(offering.features), json(offering.supportedFormats), offering.inputSchemaReference,
            offering.outputSchemaReference, offering.qualificationFingerprint, offering.qualityLevel,
            offering.expectedLatencyMs, offering.maximumCost, offering.sideEffectClass, offering.createdAt);
      }
      this.insertEvents(events);
    });
  }

  getProvider(id: Provider['id']): Provider | undefined {
    const row = this.db().prepare('SELECT * FROM providers WHERE id = ?').get(id) as Row | undefined;
    return row ? { id: String(row.id) as Provider['id'], adapterType: String(row.adapter_type),
      adapterVersion: String(row.adapter_version), configurationReference: String(row.configuration_reference),
      createdAt: this.validatedTimestamp(row.created_at, 'provider timestamp') } : undefined;
  }

  getCapabilities(): Capability[] {
    return (this.db().prepare('SELECT * FROM capabilities ORDER BY id').all() as Row[]).map((row) => ({
      id: String(row.id) as Capability['id'], contractVersion: Number(row.contract_version),
      description: String(row.description), inputSchemaReference: String(row.input_schema_reference),
      outputSchemaReference: String(row.output_schema_reference), createdAt: this.validatedTimestamp(row.created_at, 'capability timestamp'),
    }));
  }

  getProviderOfferings(capabilityId?: Capability['id']): ProviderOffering[] {
    const rows = capabilityId
      ? this.db().prepare('SELECT * FROM provider_offerings WHERE capability_id = ? ORDER BY id').all(capabilityId) as Row[]
      : this.db().prepare('SELECT * FROM provider_offerings ORDER BY capability_id, id').all() as Row[];
    return rows.map((row) => ({ id: String(row.id) as ProviderOffering['id'], providerId: String(row.provider_id) as Provider['id'],
      capabilityId: String(row.capability_id) as Capability['id'], contractVersion: Number(row.contract_version),
      modelIdentity: optionalString(row.model_identity), privacyDestinations: parseArray(row.privacy_destinations_json) as ProviderOffering['privacyDestinations'],
       permissions: parseArray(row.permissions_json), features: parseArray(row.features_json),
       supportedFormats: parseArray(row.supported_formats_json), inputSchemaReference: String(row.input_schema_reference),
       outputSchemaReference: String(row.output_schema_reference), qualificationFingerprint: String(row.qualification_fingerprint),
       qualityLevel: Number(row.quality_level), expectedLatencyMs: Number(row.expected_latency_ms), maximumCost: Number(row.maximum_cost),
      sideEffectClass: String(row.side_effect_class) as ProviderOffering['sideEffectClass'],
      createdAt: this.validatedTimestamp(row.created_at, 'offering timestamp') }));
  }

  recordQualification(value: Qualification, event: AuditEventInput): void {
    this.transaction(() => { this.db().prepare(`INSERT INTO qualifications
      (id, offering_id, status, level, evidence_json, qualified_at, expires_at, trigger_fingerprint)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)`).run(value.id, value.offeringId, value.status, value.level, json(value.evidence),
      value.qualifiedAt, value.expiresAt ?? null, value.triggerFingerprint); this.insertEvent(event); });
  }

  getQualifications(offeringId: ProviderOffering['id']): Qualification[] {
    return (this.db().prepare('SELECT * FROM qualifications WHERE offering_id = ? ORDER BY qualified_at, id').all(offeringId) as Row[])
      .map((row) => ({ id: String(row.id) as Qualification['id'], offeringId: String(row.offering_id) as ProviderOffering['id'],
        status: String(row.status) as Qualification['status'], level: Number(row.level), evidence: parseObject(row.evidence_json),
        qualifiedAt: this.validatedTimestamp(row.qualified_at, 'qualification timestamp'),
        expiresAt: optionalString(row.expires_at), triggerFingerprint: String(row.trigger_fingerprint) }));
  }

  recordProviderHealth(value: ProviderHealthObservation, event: AuditEventInput): void {
    this.transaction(() => { this.db().prepare(`INSERT INTO provider_health_observations
      (id, offering_id, status, evidence_json, observed_at) VALUES (?, ?, ?, ?, ?)`)
      .run(value.id, value.offeringId, value.status, json(value.evidence), value.observedAt); this.insertEvent(event); });
  }

  getProviderHealth(offeringId: ProviderOffering['id']): ProviderHealthObservation[] {
    return (this.db().prepare('SELECT * FROM provider_health_observations WHERE offering_id = ? ORDER BY observed_at, id').all(offeringId) as Row[])
      .map((row) => ({ id: String(row.id) as ProviderHealthObservation['id'], offeringId: String(row.offering_id) as ProviderOffering['id'],
        status: String(row.status) as ProviderHealthObservation['status'], evidence: parseObject(row.evidence_json),
        observedAt: this.validatedTimestamp(row.observed_at, 'health observation timestamp') }));
  }

  recordProviderResolution(value: ProviderResolutionDecision, event: AuditEventInput): void {
    this.transaction(() => {
      this.db().prepare(`INSERT INTO provider_resolution_decisions
        (id, capability_id, request_json, candidates_json, selected_offering_id, explanation, decided_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)`).run(value.request.id, value.request.capabilityId, json(value.request),
        json(value.candidates), value.selectedOfferingId ?? null, value.explanation, value.decidedAt);
      this.insertEvent(event);
    });
  }

  getProviderResolution(id: ProviderResolutionDecision['request']['id']): ProviderResolutionDecision | undefined {
    const row = this.db().prepare('SELECT * FROM provider_resolution_decisions WHERE id = ?').get(id) as Row | undefined;
    if (!row) return undefined;
    const request = parseObject(row.request_json) as unknown as ProviderResolutionDecision['request'];
    const candidates = JSON.parse(String(row.candidates_json)) as ProviderResolutionDecision['candidates'];
    if (!Array.isArray(candidates)) throw new Error('Corrupt persisted resolution candidates');
    return { request, candidates, selectedOfferingId: optionalString(row.selected_offering_id) as ProviderOffering['id'] | undefined,
      explanation: String(row.explanation), decidedAt: this.validatedTimestamp(row.decided_at, 'resolution timestamp') };
  }

  registerNode(node: Node, locations: readonly OfferingLocation[], events: readonly AuditEventInput[]): void {
    assertIdentifier(node.id, 'node id');
    if (events.length === 0) throw new Error('Node registration requires an audit event');
    this.transaction(() => {
      this.db().prepare(`INSERT INTO nodes (id, name, administrative_state, configuration_reference, created_at)
        VALUES (?, ?, ?, ?, ?)`).run(node.id, node.name, node.administrativeState, node.configurationReference, node.createdAt);
      for (const location of locations) {
        if (location.nodeId !== node.id) throw new Error(`Offering location does not belong to node: ${location.id}`);
        this.db().prepare(`INSERT INTO offering_locations
          (id, node_id, offering_id, enabled, capacity, privacy_classes_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)`)
          .run(location.id, location.nodeId, location.offeringId, location.enabled ? 1 : 0, location.capacity,
            json(location.privacyClasses), location.createdAt);
      }
      this.insertEvents(events);
    });
  }

  getNodes(): Array<Node & { version: number }> {
    return (this.db().prepare('SELECT * FROM nodes ORDER BY id').all() as Row[]).map((row) => this.mapNode(row));
  }

  getOfferingLocations(offeringId?: ProviderOffering['id']): OfferingLocation[] {
    const rows = offeringId
      ? this.db().prepare('SELECT * FROM offering_locations WHERE offering_id = ? ORDER BY node_id, id').all(offeringId) as Row[]
      : this.db().prepare('SELECT * FROM offering_locations ORDER BY offering_id, node_id, id').all() as Row[];
    return rows.map((row) => this.mapOfferingLocation(row));
  }

  recordNodeHealth(value: NodeHealthObservation, event: AuditEventInput): void {
    this.transaction(() => {
      this.db().prepare(`INSERT INTO node_health_observations (id, node_id, status, observed_at) VALUES (?, ?, ?, ?)`)
        .run(value.id, value.nodeId, value.status, value.observedAt);
      this.insertEvent(event);
    });
  }

  getNodeHealth(nodeId: Node['id']): NodeHealthObservation[] {
    return (this.db().prepare(`SELECT * FROM node_health_observations WHERE node_id = ? ORDER BY observed_at, id`)
      .all(nodeId) as Row[]).map((row) => this.mapNodeHealth(row));
  }

  recordNodeInspection(value: NodeInspectionObservation, event: AuditEventInput): void {
    assertIdentifier(value.id, 'node inspection id');
    assertIdentifier(value.nodeId, 'node inspection node id');
    if (!value.adapterId.trim() || !Number.isInteger(value.adapterVersion) || value.adapterVersion < 1) {
      throw new Error('Node inspection adapter identity and positive version are required');
    }
    validateTimestamp(value.inspectedAt, 'node inspection timestamp');
    this.transaction(() => {
      this.db().prepare(`INSERT INTO node_inspection_observations
        (id, node_id, adapter_id, adapter_version, health_json, inventory_json, inspected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)`).run(value.id, value.nodeId, value.adapterId, value.adapterVersion,
        json(value.health), json(value.inventory), value.inspectedAt);
      this.insertEvent(event);
    });
  }

  getNodeInspections(nodeId: Node['id']): NodeInspectionObservation[] {
    return (this.db().prepare(`SELECT * FROM node_inspection_observations WHERE node_id = ? ORDER BY inspected_at, id`)
      .all(nodeId) as Row[]).map((row) => ({ id: String(row.id) as NodeInspectionObservation['id'],
        nodeId: String(row.node_id) as Node['id'], adapterId: String(row.adapter_id),
        adapterVersion: Number(row.adapter_version),
        health: parseObject(row.health_json) as unknown as NodeInspectionObservation['health'],
        inventory: parseObject(row.inventory_json) as unknown as NodeInspectionObservation['inventory'],
        inspectedAt: this.validatedTimestamp(row.inspected_at, 'node inspection timestamp') }));
  }

  recordWorkstationWorkloadEvaluation(value: WorkstationWorkloadEvaluation, event: AuditEventInput): void {
    assertIdentifier(value.id, 'workstation workload evaluation id');
    assertIdentifier(value.nodeId, 'workstation workload evaluation node id');
    if (!value.ruleFingerprint.trim()) throw new Error('Workstation workload evaluation rule fingerprint is required');
    if (!['recommend_draining', 'recommend_active', 'inconclusive'].includes(value.recommendation)) {
      throw new Error('Invalid workstation workload evaluation recommendation');
    }
    if (value.processBasenames.some((entry) => typeof entry !== 'string') ||
        value.matchedRuleIds.some((entry) => typeof entry !== 'string')) {
      throw new Error('Workstation workload evaluation evidence must contain string arrays');
    }
    validateTimestamp(value.evaluatedAt, 'workstation workload evaluation timestamp');
    this.transaction(() => {
      this.db().prepare(`INSERT INTO workstation_availability_evaluations
        (id, node_id, rule_fingerprint, process_basenames_json, matched_rule_ids_json, recommendation, evaluated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)`).run(value.id, value.nodeId, value.ruleFingerprint,
        json(value.processBasenames), json(value.matchedRuleIds), value.recommendation, value.evaluatedAt);
      this.insertEvent(event);
    });
  }

  getWorkstationWorkloadEvaluations(nodeId: Node['id']): WorkstationWorkloadEvaluation[] {
    return (this.db().prepare(`SELECT * FROM workstation_availability_evaluations
      WHERE node_id = ? ORDER BY evaluated_at, id`).all(nodeId) as Row[])
      .map((row) => this.mapWorkstationWorkloadEvaluation(row));
  }

  applyWorkstationAvailabilityPolicy(request: WorkstationAvailabilityPolicyApplicationRequest,
    event: AuditEventInput): WorkstationAvailabilityPolicyApplication {
    assertIdentifier(request.id, 'workstation availability policy application id');
    assertIdentifier(request.evaluationId, 'workstation workload evaluation id');
    assertIdentifier(request.nodeId, 'workstation availability policy node id');
    if (!request.policyId.trim() || !Number.isInteger(request.policyVersion) || request.policyVersion < 1) {
      throw new Error('Workstation availability policy identity and positive version are required');
    }
    if (!request.expectedRuleFingerprint.trim()) throw new Error('Expected rule fingerprint is required');
    if (!Number.isInteger(request.expectedNodeVersion) || request.expectedNodeVersion < 1) {
      throw new Error('Expected node version must be positive');
    }
    if (!Number.isFinite(request.maximumEvidenceAgeMs) || request.maximumEvidenceAgeMs < 0) {
      throw new Error('Maximum evidence age must be non-negative');
    }
    if (!request.actor.trim() || !request.reason.trim()) throw new Error('Policy application actor and reason are required');
    validateTimestamp(request.appliedAt, 'workstation availability policy application timestamp');
    if (event.aggregateId !== request.nodeId || event.actor !== request.actor || event.occurredAt !== request.appliedAt) {
      throw new Error('Workstation availability policy event does not match the command');
    }

    const existing = this.db().prepare('SELECT * FROM workstation_availability_policy_applications WHERE id = ?')
      .get(request.id) as Row | undefined;
    if (existing) {
      const application = this.mapWorkstationAvailabilityPolicyApplication(existing);
      if (application.evaluationId !== request.evaluationId || application.nodeId !== request.nodeId ||
          application.policyId !== request.policyId || application.policyVersion !== request.policyVersion ||
          application.expectedNodeState !== request.expectedNodeState ||
          application.expectedNodeVersion !== request.expectedNodeVersion || application.actor !== request.actor ||
          application.reason !== request.reason.trim() || application.appliedAt !== request.appliedAt) {
        throw new Error(`Policy application idempotency conflict: ${request.id}`);
      }
      return application;
    }

    return this.transaction(() => {
      const evaluationRow = this.db().prepare('SELECT * FROM workstation_availability_evaluations WHERE id = ?')
        .get(request.evaluationId) as Row | undefined;
      if (!evaluationRow) throw new Error(`Workstation workload evaluation not found: ${request.evaluationId}`);
      const evaluation = this.mapWorkstationWorkloadEvaluation(evaluationRow);
      const nodeRow = this.db().prepare('SELECT * FROM nodes WHERE id = ?').get(request.nodeId) as Row | undefined;
      if (!nodeRow) throw new Error(`Node not found: ${request.nodeId}`);
      const node = this.mapNode(nodeRow);
      const appliedAt = Date.parse(request.appliedAt);
      const evaluatedAt = Date.parse(evaluation.evaluatedAt);
      const latest = this.db().prepare(`SELECT id FROM workstation_availability_evaluations
        WHERE node_id = ? AND (evaluated_at > ? OR (evaluated_at = ? AND id > ?)) ORDER BY evaluated_at DESC, id DESC LIMIT 1`)
        .get(evaluation.nodeId, evaluation.evaluatedAt, evaluation.evaluatedAt, evaluation.id) as Row | undefined;
      const structurallyValid = /^[a-f0-9]{64}$/.test(evaluation.ruleFingerprint) &&
        evaluation.processBasenames.every((value, index, values) => Boolean(value) && value === value.trim() &&
          !/[\\/\x00-\x1f]/.test(value) && (index === 0 || values[index - 1] < value)) &&
        evaluation.matchedRuleIds.every((value, index, values) => Boolean(value) && value === value.trim() &&
          (index === 0 || values[index - 1] < value));

      let disposition: WorkstationAvailabilityPolicyApplication['disposition'];
      let targetState: Node['administrativeState'] | undefined;
      if (evaluation.nodeId !== request.nodeId) disposition = 'node_mismatch';
      else if (!structurallyValid) disposition = 'invalid_evidence';
      else if (evaluation.ruleFingerprint !== request.expectedRuleFingerprint) disposition = 'rule_fingerprint_mismatch';
      else if (evaluatedAt > appliedAt || appliedAt - evaluatedAt > request.maximumEvidenceAgeMs) disposition = 'stale_evidence';
      else if (latest) disposition = 'superseded_evidence';
      else if (node.administrativeState !== request.expectedNodeState || node.version !== request.expectedNodeVersion) {
        disposition = 'state_version_mismatch';
      } else if (node.administrativeState === 'disabled') disposition = 'disabled_node';
      else if (evaluation.recommendation === 'inconclusive') disposition = 'inconclusive';
      else if (evaluation.recommendation === 'recommend_draining') {
        if (node.administrativeState === 'active') targetState = 'draining';
        disposition = targetState ? 'applied_transition' : 'already_satisfied';
      } else if (node.administrativeState === 'active') disposition = 'already_satisfied';
      else {
        const owner = this.db().prepare(`SELECT policy_application_id FROM node_administrative_transitions
          WHERE node_id = ? AND node_version = ? AND to_state = 'draining'`).get(node.id, node.version) as Row | undefined;
        const owned = owner?.policy_application_id && this.db().prepare(`SELECT id FROM workstation_availability_policy_applications
          WHERE id = ? AND node_id = ? AND policy_id = ? AND policy_version = ? AND disposition = 'applied_transition'`)
          .get(String(owner.policy_application_id), node.id, request.policyId, request.policyVersion);
        if (owned) targetState = 'active';
        disposition = targetState ? 'applied_transition' : 'policy_ownership_mismatch';
      }

      const resultingState = targetState ?? node.administrativeState;
      const resultingVersion = targetState ? node.version + 1 : node.version;
      const application: WorkstationAvailabilityPolicyApplication = {
        id: request.id, evaluationId: evaluation.id, nodeId: request.nodeId, policyId: request.policyId,
        policyVersion: request.policyVersion, ruleFingerprint: evaluation.ruleFingerprint, actor: request.actor,
        reason: request.reason.trim(), expectedNodeState: request.expectedNodeState,
        expectedNodeVersion: request.expectedNodeVersion, observedNodeState: node.administrativeState,
        observedNodeVersion: node.version, recommendation: evaluation.recommendation, disposition,
        transitionOccurred: Boolean(targetState), resultingNodeState: resultingState,
        resultingNodeVersion: resultingVersion, appliedAt: request.appliedAt,
      };
      this.insertEvent(event);
      this.db().prepare(`INSERT INTO workstation_availability_policy_applications
        (id, evaluation_id, node_id, policy_id, policy_version, rule_fingerprint, actor, reason,
         expected_node_state, expected_node_version, observed_node_state, observed_node_version, recommendation,
         disposition, transition_occurred, resulting_node_state, resulting_node_version, applied_at, event_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
        .run(application.id, application.evaluationId, application.nodeId, application.policyId, application.policyVersion,
          application.ruleFingerprint, application.actor, application.reason, application.expectedNodeState,
          application.expectedNodeVersion, application.observedNodeState, application.observedNodeVersion,
          application.recommendation, application.disposition, application.transitionOccurred ? 1 : 0,
          application.resultingNodeState, application.resultingNodeVersion, application.appliedAt, event.id);
      if (targetState) {
        const update = this.db().prepare(`UPDATE nodes SET administrative_state = ?, version = version + 1
          WHERE id = ? AND version = ? AND administrative_state = ?`)
          .run(targetState, node.id, node.version, node.administrativeState);
        if (Number(update.changes) !== 1) throw new Error(`Node concurrency conflict: ${node.id}`);
      }
      if (targetState) {
        this.db().prepare(`INSERT INTO node_administrative_transitions
          (node_id, from_state, to_state, actor, reason, occurred_at, node_version, event_id, policy_application_id)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`).run(node.id, node.administrativeState, targetState, request.actor,
          request.reason.trim(), request.appliedAt, node.version + 1, event.id, request.id);
      }
      return application;
    });
  }

  getWorkstationAvailabilityPolicyApplications(nodeId: Node['id']): WorkstationAvailabilityPolicyApplication[] {
    return (this.db().prepare(`SELECT * FROM workstation_availability_policy_applications
      WHERE node_id = ? ORDER BY applied_at, id`).all(nodeId) as Row[])
      .map((row) => this.mapWorkstationAvailabilityPolicyApplication(row));
  }

  transitionNodeAdministrativeState(nodeId: Node['id'], expectedVersion: number,
    currentState: Node['administrativeState'], targetState: Node['administrativeState'], actor: string,
    reason: string, occurredAt: string, event: AuditEventInput): Node & { version: number } {
    assertIdentifier(nodeId, 'node id');
    const states: readonly Node['administrativeState'][] = ['active', 'draining', 'disabled'];
    if (!states.includes(currentState) || !states.includes(targetState)) throw new Error('Invalid node administrative state');
    if (currentState === targetState) throw new Error('Node administrative transition cannot be a no-op');
    if (!Number.isInteger(expectedVersion) || expectedVersion < 1) throw new Error('Expected node version must be positive');
    if (!actor.trim()) throw new Error('Node administrative transition actor is required');
    if (!reason.trim()) throw new Error('Node administrative transition reason is required');
    validateTimestamp(occurredAt, 'node administrative transition timestamp');
    if (event.aggregateId !== nodeId || event.actor !== actor || event.occurredAt !== occurredAt) {
      throw new Error('Node administrative transition event does not match the command');
    }
    return this.transaction(() => {
      const result = this.db().prepare(`UPDATE nodes SET administrative_state = ?, version = version + 1
        WHERE id = ? AND version = ? AND administrative_state = ?`)
        .run(targetState, nodeId, expectedVersion, currentState);
      if (Number(result.changes) !== 1) throw new Error(`Node concurrency conflict: ${nodeId}`);
      this.insertEvent(event);
      this.db().prepare(`INSERT INTO node_administrative_transitions
        (node_id, from_state, to_state, actor, reason, occurred_at, node_version, event_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)`).run(nodeId, currentState, targetState, actor, reason.trim(), occurredAt,
        expectedVersion + 1, event.id);
      return this.mapNode(this.db().prepare('SELECT * FROM nodes WHERE id = ?').get(nodeId) as Row);
    });
  }

  recordResourceSchedulingDecision(value: ResourceSchedulingDecision, lease: ResourceLease,
    events: readonly AuditEventInput[]): void {
    if (events.length === 0) throw new Error('Resource scheduling requires an audit event');
    if (value.request.id !== lease.decisionId || value.request.offeringId !== lease.offeringId ||
        value.selectedLocationId !== lease.locationId || value.selectedNodeId !== lease.nodeId || lease.status !== 'active') {
      throw new Error('Resource lease does not match its scheduling decision');
    }
    this.transaction(() => {
      const location = this.db().prepare('SELECT node_id, offering_id, capacity FROM offering_locations WHERE id = ?')
        .get(lease.locationId) as Row | undefined;
      if (!location || String(location.node_id) !== lease.nodeId || String(location.offering_id) !== lease.offeringId) {
        throw new Error('Resource lease binding does not match its offering location');
      }
      const used = Number((this.db().prepare(`SELECT COALESCE(SUM(capacity), 0) AS capacity FROM resource_leases
        WHERE location_id = ? AND status = 'active' AND expires_at > ?`).get(lease.locationId, lease.acquiredAt) as Row).capacity);
      if (used + lease.capacity > Number(location.capacity)) {
        throw new Error(`Active resource lease capacity conflict: ${lease.locationId}`);
      }
      this.db().prepare(`INSERT INTO resource_scheduling_decisions
        (id, offering_id, request_json, candidates_json, selected_location_id, selected_node_id, explanation, decided_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)`).run(value.request.id, value.request.offeringId, json(value.request),
        json(value.candidates), value.selectedLocationId ?? null, value.selectedNodeId ?? null, value.explanation, value.decidedAt);
      this.db().prepare(`INSERT INTO resource_leases
        (id, decision_id, offering_id, location_id, node_id, capacity, status, acquired_at, expires_at, released_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`).run(lease.id, lease.decisionId, lease.offeringId, lease.locationId,
        lease.nodeId, lease.capacity, lease.status, lease.acquiredAt, lease.expiresAt, lease.releasedAt ?? null);
      this.insertEvents(events);
    });
  }

  scheduleTaskWithResource(task: Task, expectedVersion: number, value: ResourceSchedulingDecision,
    lease: ResourceLease, events: readonly AuditEventInput[]): boolean {
    if (events.length === 0) throw new Error('Resource scheduling requires an audit event');
    if (task.status !== 'scheduled' || value.request.id !== lease.decisionId ||
        value.request.offeringId !== lease.offeringId || value.selectedLocationId !== lease.locationId ||
        value.selectedNodeId !== lease.nodeId || lease.status !== 'active') {
      throw new Error('Resource lease does not match its workflow scheduling decision');
    }
    return this.transaction(() => {
      const location = this.db().prepare('SELECT node_id, offering_id, capacity FROM offering_locations WHERE id = ?')
        .get(lease.locationId) as Row | undefined;
      if (!location || String(location.node_id) !== lease.nodeId || String(location.offering_id) !== lease.offeringId) {
        throw new Error('Resource lease binding does not match its offering location');
      }
      const used = Number((this.db().prepare(`SELECT COALESCE(SUM(capacity), 0) AS capacity FROM resource_leases
        WHERE location_id = ? AND status = 'active' AND expires_at > ?`).get(lease.locationId, lease.acquiredAt) as Row).capacity);
      if (used + lease.capacity > Number(location.capacity)) return false;
      this.updateTaskRow(task, expectedVersion);
      this.db().prepare(`INSERT INTO resource_scheduling_decisions
        (id, offering_id, request_json, candidates_json, selected_location_id, selected_node_id, explanation, decided_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)`).run(value.request.id, value.request.offeringId, json(value.request),
        json(value.candidates), value.selectedLocationId ?? null, value.selectedNodeId ?? null, value.explanation, value.decidedAt);
      this.db().prepare(`INSERT INTO resource_leases
        (id, decision_id, offering_id, location_id, node_id, capacity, status, acquired_at, expires_at, released_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`).run(lease.id, lease.decisionId, lease.offeringId, lease.locationId,
        lease.nodeId, lease.capacity, lease.status, lease.acquiredAt, lease.expiresAt, lease.releasedAt ?? null);
      this.insertEvents(events);
      return true;
    });
  }

  getResourceSchedulingDecision(id: ResourceSchedulingDecision['request']['id']): ResourceSchedulingDecision | undefined {
    const row = this.db().prepare('SELECT * FROM resource_scheduling_decisions WHERE id = ?').get(id) as Row | undefined;
    return row ? this.mapResourceSchedulingDecision(row) : undefined;
  }

  getResourceLeases(locationId?: OfferingLocation['id']): ResourceLease[] {
    const rows = locationId
      ? this.db().prepare('SELECT * FROM resource_leases WHERE location_id = ? ORDER BY acquired_at, id').all(locationId) as Row[]
      : this.db().prepare('SELECT * FROM resource_leases ORDER BY acquired_at, id').all() as Row[];
    return rows.map((row) => this.mapResourceLease(row));
  }

  releaseResourceLease(value: ResourceLease, event: AuditEventInput): void {
    if (value.status === 'active' || !value.releasedAt) throw new Error('Released resource lease requires a terminal status and releasedAt');
    this.transaction(() => {
      const result = this.db().prepare(`UPDATE resource_leases SET status = ?, released_at = ? WHERE id = ? AND status = 'active'`)
        .run(value.status, value.releasedAt, value.id);
      if (Number(result.changes) !== 1) throw new Error(`Resource lease is not active: ${value.id}`);
      this.insertEvent(event);
    });
  }

  importLegacyHistory(value: LegacyImportWrite): LegacyImportResult {
    this.validateLegacyImport(value);
    const existing = this.getLegacyImport(value.operation.sourceDigest);
    if (existing) return { operation: existing, created: false, insertedRecordCount: 0 };
    return this.transaction(() => {
      const operation = value.operation;
      this.db().prepare(`INSERT INTO legacy_import_operations
        (id, source_digest, source_reference, assessment_version, imported_record_count, imported_at)
        VALUES (?, ?, ?, ?, ?, ?)`).run(operation.id, operation.sourceDigest, operation.sourceReference,
        operation.assessmentVersion, operation.importedRecordCount, operation.importedAt);
      for (const record of value.records) {
        this.db().prepare(`INSERT INTO legacy_history_records
          (import_operation_id, source_digest, source_reference, source_section, source_key, legacy_status,
           payload_json, assessment_version, imported_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`)
          .run(record.importOperationId, record.sourceDigest, record.sourceReference, record.sourceSection,
            record.sourceKey, record.legacyStatus, json(record.payload), record.assessmentVersion, record.importedAt);
      }
      return { operation, created: true, insertedRecordCount: value.records.length };
    });
  }

  getLegacyImport(sourceDigest: string): LegacyImportOperation | undefined {
    const row = this.db().prepare('SELECT * FROM legacy_import_operations WHERE source_digest = ?').get(sourceDigest) as Row | undefined;
    return row ? this.mapLegacyImport(row) : undefined;
  }

  getLegacyHistory(sourceDigest?: string): LegacyHistoryRecord[] {
    const rows = sourceDigest
      ? this.db().prepare(`SELECT * FROM legacy_history_records WHERE source_digest = ?
          ORDER BY source_section, source_key`).all(sourceDigest) as Row[]
      : this.db().prepare('SELECT * FROM legacy_history_records ORDER BY source_digest, source_section, source_key').all() as Row[];
    return rows.map((row) => ({ importOperationId: String(row.import_operation_id), sourceDigest: String(row.source_digest),
      sourceReference: String(row.source_reference), sourceSection: String(row.source_section), sourceKey: String(row.source_key),
      legacyStatus: String(row.legacy_status), payload: parseObject(row.payload_json), assessmentVersion: Number(row.assessment_version),
      importedAt: this.validatedTimestamp(row.imported_at, 'legacy history import timestamp') }));
  }

  createGoal(bundle: GoalBundle, event: AuditEventInput): void {
    const { goal, criteria } = bundle;
    this.validateGoal(goal);
    this.transaction(() => {
      this.db().prepare(`INSERT INTO goals
        (id, objective, constraints_json, priority, privacy_class, status, active_graph_revision_id, terminal_reason, version, created_at, updated_at, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
        .run(goal.id, goal.objective, json(goal.constraints), goal.priority, goal.privacyClass, goal.status,
          goal.activeGraphRevisionId ?? null, goal.terminalReason ?? null, goal.version, goal.createdAt, goal.updatedAt, goal.completedAt ?? null);
      for (const criterion of criteria) this.insertCriterion(criterion);
      this.insertEvent(event);
    });
  }

  getGoal(id: GoalId): GoalBundle | undefined {
    const row = this.db().prepare('SELECT * FROM goals WHERE id = ?').get(id) as Row | undefined;
    if (!row) return undefined;
    const criteria = this.db().prepare('SELECT * FROM goal_success_criteria WHERE goal_id = ? ORDER BY position, id').all(id) as Row[];
    return { goal: this.mapGoal(row), criteria: criteria.map(this.mapCriterion) };
  }

  updateGoal(goal: Goal, expectedVersion: number, event: AuditEventInput): void {
    this.validateGoal(goal);
    if (goal.version !== expectedVersion + 1) throw new Error('Goal version must increment exactly once');
    this.transaction(() => {
      const result = this.db().prepare(`UPDATE goals SET
        objective = ?, constraints_json = ?, priority = ?, privacy_class = ?, status = ?,
        active_graph_revision_id = ?, terminal_reason = ?, version = ?, updated_at = ?, completed_at = ?
        WHERE id = ? AND version = ?`)
        .run(goal.objective, json(goal.constraints), goal.priority, goal.privacyClass, goal.status,
          goal.activeGraphRevisionId ?? null, goal.terminalReason ?? null, goal.version, goal.updatedAt,
          goal.completedAt ?? null, goal.id, expectedVersion);
      if (Number(result.changes) !== 1) throw new Error(`Goal concurrency conflict: ${goal.id}`);
      this.insertEvent(event);
    });
  }

  createTaskGraphRevision(revision: TaskGraphRevision, event: AuditEventInput): void {
    this.validateTaskGraphRevision(revision);
    this.transaction(() => {
      this.insertTaskGraphRevision(revision);
      this.insertEvent(event);
    });
  }

  admitTaskGraph(revision: TaskGraphRevision, tasks: readonly Task[], dependencies: readonly TaskDependency[],
    events: readonly AuditEventInput[]): void {
    this.validateTaskGraphRevision(revision);
    for (const task of tasks) this.validateTask(task);
    for (const dependency of dependencies) validateTimestamp(dependency.createdAt, 'task dependency timestamp');
    validateTaskGraph(revision, tasks, dependencies);
    const expectedEvents = 1 + tasks.length + dependencies.length;
    if (events.length !== expectedEvents) {
      throw new Error(`Graph admission requires exactly ${expectedEvents} structural events`);
    }
    this.transaction(() => {
      this.insertTaskGraphRevision(revision);
      for (const task of tasks) this.insertTask(task);
      for (const dependency of dependencies) this.insertTaskDependency(dependency);
      this.insertEvents(events);
    });
  }

  getTaskGraphRevision(id: TaskGraphRevisionId): TaskGraphRevision | undefined {
    const row = this.db().prepare('SELECT * FROM task_graph_revisions WHERE id = ?').get(id) as Row | undefined;
    return row ? this.mapTaskGraphRevision(row) : undefined;
  }

  getTaskGraphRevisions(goalId: GoalId): TaskGraphRevision[] {
    return (this.db().prepare('SELECT * FROM task_graph_revisions WHERE goal_id = ? ORDER BY revision, id').all(goalId) as Row[])
      .map((row) => this.mapTaskGraphRevision(row));
  }

  createTask(task: Task, event: AuditEventInput): void {
    this.validateTask(task);
    this.transaction(() => {
      this.insertTask(task);
      this.insertEvent(event);
    });
  }

  getTask(id: TaskId): Task | undefined {
    const row = this.db().prepare('SELECT * FROM tasks WHERE id = ?').get(id) as Row | undefined;
    return row ? this.mapTask(row) : undefined;
  }

  getTasks(revisionId: TaskGraphRevisionId): Task[] {
    return (this.db().prepare(`SELECT * FROM tasks WHERE graph_revision_id = ?
      ORDER BY created_at, id`).all(revisionId) as Row[]).map((row) => this.mapTask(row));
  }

  updateTask(task: Task, expectedVersion: number, event: AuditEventInput): void {
    assertIdentifier(task.id, 'task id');
    if (task.version !== expectedVersion + 1) throw new Error('Task version must increment exactly once');
    validateTimestamp(task.updatedAt, 'task update timestamp');
    this.transaction(() => {
      const result = this.db().prepare(`UPDATE tasks SET
        status = ?, terminal_reason = ?, version = ?, updated_at = ?, completed_at = ?
        WHERE id = ? AND version = ?`)
        .run(task.status, task.terminalReason ?? null, task.version, task.updatedAt,
          task.completedAt ?? null, task.id, expectedVersion);
      if (Number(result.changes) !== 1) throw new Error(`Task concurrency conflict: ${task.id}`);
      this.insertEvent(event);
    });
  }

  createTaskDependency(dependency: TaskDependency, event: AuditEventInput): void {
    if (dependency.condition === 'predicate' && !dependency.predicate) throw new Error('Predicate dependency requires a predicate');
    validateTimestamp(dependency.createdAt, 'task dependency timestamp');
    this.transaction(() => {
      this.insertTaskDependency(dependency);
      this.insertEvent(event);
    });
  }

  getTaskDependencies(revisionId: TaskGraphRevisionId): TaskDependency[] {
    return (this.db().prepare(`SELECT * FROM task_dependencies WHERE graph_revision_id = ?
      ORDER BY predecessor_task_id, successor_task_id`).all(revisionId) as Row[]).map((row) => ({
      graphRevisionId: String(row.graph_revision_id) as TaskGraphRevisionId,
      predecessorTaskId: String(row.predecessor_task_id) as TaskId,
      successorTaskId: String(row.successor_task_id) as TaskId,
      condition: String(row.condition) as TaskDependency['condition'],
      predicate: row.predicate_json === null ? undefined : parseObject(row.predicate_json),
      createdAt: this.validatedTimestamp(row.created_at, 'persisted task dependency timestamp'),
    }));
  }

  createAttempt(attempt: Attempt, event: AuditEventInput): void {
    assertIdentifier(attempt.id, 'attempt id');
    validateTimestamp(attempt.createdAt, 'attempt creation timestamp');
    this.transaction(() => {
      this.db().prepare(`INSERT INTO attempts
        (id, task_id, attempt_number, status, provider_offering_id, compute_node_id, input_snapshot_json,
         result_json, idempotency_key, started_at, completed_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
        .run(attempt.id, attempt.taskId, attempt.attemptNumber, attempt.status, attempt.providerOfferingId ?? null,
          attempt.computeNodeId ?? null, json(attempt.inputSnapshot), attempt.result ? json(attempt.result) : null,
          attempt.idempotencyKey ?? null, attempt.startedAt ?? null, attempt.completedAt ?? null, attempt.createdAt);
      this.insertEvent(event);
    });
  }

  getAttempts(taskId: TaskId): Attempt[] {
    return (this.db().prepare('SELECT * FROM attempts WHERE task_id = ? ORDER BY attempt_number, id').all(taskId) as Row[])
      .map((row) => this.mapAttempt(row));
  }

  startAttempt(task: Task, expectedVersion: number, attempt: Attempt, events: readonly AuditEventInput[],
    recoveryDecisionId?: AlternativeRecoveryDecisionId, reconciliationDecisionId?: ReconciliationDecisionId,
    circuitProbeId?: CircuitProbe['id']): void {
    this.transaction(() => {
      this.updateTaskRow(task, expectedVersion);
      this.insertAttempt(attempt);
      if (recoveryDecisionId) this.insertAlternativeRecoveryConsumption(recoveryDecisionId, attempt, attempt.startedAt ?? attempt.createdAt);
      if (reconciliationDecisionId) this.insertReconciliationAttemptConsumption(reconciliationDecisionId, attempt,
        attempt.startedAt ?? attempt.createdAt);
      if (circuitProbeId) this.validateClaimedCircuitProbe(circuitProbeId, attempt);
      this.insertEvents(events);
    });
  }

  recordAttemptOutcome(
    task: Task,
    expectedVersion: number,
    attempt: Attempt,
    failure: Failure | undefined,
    events: readonly AuditEventInput[],
    diagnosis?: FailureDiagnosis,
  ): void {
    this.transaction(() => {
      this.updateAttemptRow(attempt);
      if (failure) this.insertFailure(failure);
      this.validateFailureDiagnosisPair(failure, diagnosis);
      this.insertEvents(events);
      if (diagnosis) this.insertFailureDiagnosis(diagnosis);
      this.updateTaskRow(task, expectedVersion);
    });
  }

  recordVerificationOutcome(
    task: Task,
    expectedVersion: number,
    verification: Verification,
    failure: Failure | undefined,
    events: readonly AuditEventInput[],
    diagnosis?: FailureDiagnosis,
  ): void {
    this.transaction(() => {
      this.insertVerification(verification);
      if (failure) this.insertFailure(failure);
      this.validateFailureDiagnosisPair(failure, diagnosis);
      this.insertEvents(events);
      if (diagnosis) this.insertFailureDiagnosis(diagnosis);
      this.updateTaskRow(task, expectedVersion);
    });
  }

  recordTaskFailure(task: Task, expectedVersion: number, failure: Failure, events: readonly AuditEventInput[],
    diagnosis?: FailureDiagnosis): void {
    this.transaction(() => {
      this.insertFailure(failure);
      this.validateFailureDiagnosisPair(failure, diagnosis);
      this.insertEvents(events);
      if (diagnosis) this.insertFailureDiagnosis(diagnosis);
      this.updateTaskRow(task, expectedVersion);
    });
  }

  createVerification(value: Verification, event: AuditEventInput): void {
    this.transaction(() => {
      this.insertVerification(value);
      this.insertEvent(event);
    });
  }

  getVerifications(taskId: TaskId): Verification[] {
    return (this.db().prepare('SELECT * FROM verifications WHERE task_id = ? ORDER BY created_at, id').all(taskId) as Row[])
      .map((row) => ({ id: String(row.id) as Verification['id'], taskId: String(row.task_id) as TaskId,
        attemptId: optionalString(row.attempt_id) as Verification['attemptId'], verdict: String(row.verdict) as Verification['verdict'],
        planVersion: Number(row.plan_version), verifier: String(row.verifier), criterionResults: parseObject(row.criterion_results_json),
        evidence: parseObject(row.evidence_json), createdAt: String(row.created_at) }));
  }

  createFailure(value: Failure, event: AuditEventInput): void {
    this.transaction(() => {
      this.insertFailure(value);
      this.insertEvent(event);
    });
  }

  getFailure(id: FailureId): Failure | undefined {
    const row = this.db().prepare('SELECT * FROM failures WHERE id = ?').get(id) as Row | undefined;
    return row ? this.mapFailure(row) : undefined;
  }

  getFailures(taskId: TaskId): Failure[] {
    return (this.db().prepare('SELECT * FROM failures WHERE task_id = ? ORDER BY created_at, id').all(taskId) as Row[])
      .map((row) => this.mapFailure(row));
  }

  recordFailureDiagnosis(diagnosis: FailureDiagnosis, event: AuditEventInput): FailureDiagnosis {
    const existing = this.getFailureDiagnosis(diagnosis.failureId, diagnosis.policyId, diagnosis.policyVersion);
    if (existing) {
      if (existing.evidenceFingerprint !== diagnosis.evidenceFingerprint || existing.id !== diagnosis.id) {
        throw new Error(`Failure diagnosis authority conflict: ${diagnosis.failureId}`);
      }
      return existing;
    }
    if (event.id !== diagnosis.eventId || event.aggregateId !== diagnosis.taskId || event.eventType !== 'failure.diagnosed') {
      throw new Error('Failure diagnosis Event does not match the diagnosis');
    }
    return this.transaction(() => {
      this.insertEvent(event);
      this.insertFailureDiagnosis(diagnosis);
      return diagnosis;
    });
  }

  getFailureDiagnosis(failureId: FailureId, policyId: string, policyVersion: number): FailureDiagnosis | undefined {
    const row = this.db().prepare(`SELECT * FROM failure_diagnoses
      WHERE failure_id = ? AND policy_id = ? AND policy_version = ?`).get(failureId, policyId, policyVersion) as Row | undefined;
    return row ? this.mapFailureDiagnosis(row) : undefined;
  }

  getFailureDiagnosisById(id: FailureDiagnosisId): FailureDiagnosis | undefined {
    const row = this.db().prepare('SELECT * FROM failure_diagnoses WHERE id = ?').get(id) as Row | undefined;
    return row ? this.mapFailureDiagnosis(row) : undefined;
  }

  getFailureDiagnoses(taskId: TaskId): FailureDiagnosis[] {
    return (this.db().prepare(`SELECT d.* FROM failure_diagnoses d
      LEFT JOIN attempts a ON a.id = d.attempt_id WHERE d.task_id = ?
      ORDER BY COALESCE(a.attempt_number, 0), d.diagnosed_at, d.id`).all(taskId) as Row[])
      .map((row) => this.mapFailureDiagnosis(row));
  }

  recordChangedConditionEvidence(value: ChangedConditionEvidence, event: AuditEventInput): void {
    this.validateChangedConditionEvidence(value);
    const diagnosis = this.db().prepare('SELECT task_id FROM failure_diagnoses WHERE id = ?').get(value.diagnosisId) as Row | undefined;
    if (!diagnosis || event.id !== value.eventId || event.aggregateType !== 'task' ||
        event.aggregateId !== String(diagnosis.task_id) || event.eventType !== 'failure.changed-condition-recorded') {
      throw new Error('Changed-condition Event does not match the evidence');
    }
    this.transaction(() => {
      this.insertEvent(event);
      this.db().prepare(`INSERT INTO changed_condition_evidence
        (id, diagnosis_id, condition_type, prior_fact_reference, changed_fact_reference, source, observed_at, event_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)`).run(value.id, value.diagnosisId, value.conditionType,
        value.priorFactReference ?? null, value.changedFactReference ?? null, value.source, value.observedAt, value.eventId);
    });
  }

  getChangedConditionEvidence(diagnosisId: FailureDiagnosisId): ChangedConditionEvidence[] {
    return (this.db().prepare(`SELECT * FROM changed_condition_evidence WHERE diagnosis_id = ?
      ORDER BY observed_at, id`).all(diagnosisId) as Row[]).map((row) => this.mapChangedConditionEvidence(row));
  }

  recordAlternativeRecoveryDecision(value: AlternativeRecoveryDecision, evidence: ChangedConditionEvidence | undefined,
    task: Task | undefined, expectedTaskVersion: number | undefined, events: readonly AuditEventInput[]): AlternativeRecoveryDecision {
    const existing = this.getAlternativeRecoveryDecision(value.diagnosisId);
    if (existing) {
      if (canonicalize(existing) !== canonicalize(value)) throw new Error(`Alternative recovery authority conflict: ${value.diagnosisId}`);
      return existing;
    }
    if (events.length === 0 || events.at(-1)?.id !== value.eventId) throw new Error('Alternative recovery decision Event mismatch');
    if ((value.disposition === 'authorized') !== Boolean(evidence && task && expectedTaskVersion !== undefined)) {
      throw new Error('Authorized alternative recovery requires evidence and Task transition');
    }
    return this.transaction(() => {
      this.insertEvents(events);
      if (evidence) {
        this.validateChangedConditionEvidence(evidence);
        this.db().prepare(`INSERT INTO changed_condition_evidence
          (id, diagnosis_id, condition_type, prior_fact_reference, changed_fact_reference, source, observed_at, event_id)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?)`).run(evidence.id, evidence.diagnosisId, evidence.conditionType,
          evidence.priorFactReference ?? null, evidence.changedFactReference ?? null, evidence.source,
          evidence.observedAt, evidence.eventId);
      }
      this.db().prepare(`INSERT INTO alternative_recovery_decisions
        (id, diagnosis_id, failure_id, task_id, failed_attempt_id, requested_disposition, disposition, reason,
         next_attempt_number, failed_offering_id, failed_node_id, failed_location_id, selected_offering_id,
         selected_node_id, selected_location_id, provider_resolution_id, resource_scheduling_decision_id,
         changed_condition_evidence_id, actor, decided_at, event_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
        .run(value.id, value.diagnosisId, value.failureId, value.taskId, value.failedAttemptId,
          value.requestedDisposition, value.disposition, value.reason, value.nextAttemptNumber ?? null,
          value.failedOfferingId ?? null, value.failedNodeId ?? null, value.failedLocationId ?? null,
          value.selectedOfferingId ?? null, value.selectedNodeId ?? null, value.selectedLocationId ?? null,
          value.providerResolutionId ?? null, value.resourceSchedulingDecisionId ?? null,
          value.changedConditionEvidenceId ?? null, value.actor, value.decidedAt, value.eventId);
      if (task && expectedTaskVersion !== undefined) this.updateTaskRow(task, expectedTaskVersion);
      return value;
    });
  }

  getAlternativeRecoveryDecision(diagnosisId: FailureDiagnosisId): AlternativeRecoveryDecision | undefined {
    const row = this.db().prepare('SELECT * FROM alternative_recovery_decisions WHERE diagnosis_id = ?')
      .get(diagnosisId) as Row | undefined;
    return row ? this.mapAlternativeRecoveryDecision(row) : undefined;
  }

  getPendingAlternativeRecovery(taskId: TaskId): AlternativeRecoveryDecision | undefined {
    const row = this.db().prepare(`SELECT d.* FROM alternative_recovery_decisions d
      LEFT JOIN alternative_recovery_consumptions c ON c.decision_id = d.id
      WHERE d.task_id = ? AND d.disposition = 'authorized' AND c.decision_id IS NULL
      ORDER BY d.decided_at DESC, d.id DESC LIMIT 1`).get(taskId) as Row | undefined;
    return row ? this.mapAlternativeRecoveryDecision(row) : undefined;
  }

  recordReconciliationDecision(value: ReconciliationDecision, task: Task | undefined,
    expectedTaskVersion: number | undefined, verification: Verification | undefined, failure: Failure | undefined,
    diagnosis: FailureDiagnosis | undefined, events: readonly AuditEventInput[]): ReconciliationDecision {
    const sameEvidence = this.db().prepare(`SELECT * FROM reconciliation_decisions WHERE attempt_id = ? AND failure_id = ?
      AND diagnosis_id = ? AND provider_id = ? AND provider_version = ? AND evidence_fingerprint = ?`)
      .get(value.attemptId, value.failureId, value.diagnosisId, value.providerId, value.providerVersion,
        value.evidenceFingerprint) as Row | undefined;
    if (sameEvidence) {
      const existing = this.mapReconciliationDecision(sameEvidence);
      if (existing.conclusion !== value.conclusion || existing.operationId !== value.operationId) {
        throw new Error(`Reconciliation authority conflict: ${value.attemptId}`);
      }
      return existing;
    }
    const conclusive = this.db().prepare(`SELECT * FROM reconciliation_decisions WHERE attempt_id = ? AND failure_id = ?
      AND diagnosis_id = ? AND conclusion <> 'remains_indeterminate'`).get(value.attemptId, value.failureId,
        value.diagnosisId) as Row | undefined;
    if (conclusive) throw new Error(`Reconciliation authority already concluded: ${value.attemptId}`);
    if (events.length === 0 || events[0]?.id !== value.eventId) throw new Error('Reconciliation decision Event mismatch');
    const hasTaskUpdate = Boolean(task && expectedTaskVersion !== undefined);
    if ((value.conclusion === 'proven_not_completed' && Boolean(value.nextAttemptNumber) !== hasTaskUpdate) ||
        (value.conclusion === 'proven_completed' && (!hasTaskUpdate || !verification)) ||
        (value.conclusion === 'remains_indeterminate' && (hasTaskUpdate || verification))) {
      throw new Error('Reconciliation lifecycle result does not match its conclusion');
    }
    return this.transaction(() => {
      this.insertEvents(events);
      if (verification) this.insertVerification(verification);
      if (failure) this.insertFailure(failure);
      this.validateFailureDiagnosisPair(failure, diagnosis);
      if (diagnosis) this.insertFailureDiagnosis(diagnosis);
      this.db().prepare(`INSERT INTO reconciliation_decisions
        (id, task_id, attempt_id, failure_id, diagnosis_id, provider_id, provider_version, operation_id,
         evidence_json, evidence_fingerprint, conclusion, reason, observation_number, next_attempt_number,
         verification_id, actor, decided_at, event_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
        .run(value.id, value.taskId, value.attemptId, value.failureId, value.diagnosisId, value.providerId,
          value.providerVersion, value.operationId, json(value.evidence), value.evidenceFingerprint, value.conclusion,
          value.reason, value.observationNumber, value.nextAttemptNumber ?? null, value.verificationId ?? null,
          value.actor, value.decidedAt, value.eventId);
      if (verification) this.db().prepare(`INSERT INTO reconciliation_verification_consumptions
        (decision_id, verification_id, consumed_at) VALUES (?, ?, ?)`).run(value.id, verification.id, value.decidedAt);
      if (task && expectedTaskVersion !== undefined) this.updateTaskRow(task, expectedTaskVersion);
      return value;
    });
  }

  getReconciliationDecision(id: ReconciliationDecisionId): ReconciliationDecision | undefined {
    const row = this.db().prepare('SELECT * FROM reconciliation_decisions WHERE id = ?').get(id) as Row | undefined;
    return row ? this.mapReconciliationDecision(row) : undefined;
  }

  getReconciliationDecisions(diagnosisId: FailureDiagnosisId): ReconciliationDecision[] {
    return (this.db().prepare(`SELECT * FROM reconciliation_decisions WHERE diagnosis_id = ?
      ORDER BY observation_number, id`).all(diagnosisId) as Row[]).map((row) => this.mapReconciliationDecision(row));
  }

  getPendingReconciliation(taskId: TaskId): ReconciliationDecision | undefined {
    const row = this.db().prepare(`SELECT d.* FROM reconciliation_decisions d
      LEFT JOIN reconciliation_attempt_consumptions c ON c.decision_id = d.id
      WHERE d.task_id = ? AND d.conclusion = 'proven_not_completed' AND d.next_attempt_number IS NOT NULL
        AND c.decision_id IS NULL
      ORDER BY d.observation_number DESC, d.id DESC LIMIT 1`).get(taskId) as Row | undefined;
    return row ? this.mapReconciliationDecision(row) : undefined;
  }

  recordCircuitEvidence(targetType: CircuitTargetType, targetId: string, diagnosis: FailureDiagnosis,
    policy: CircuitBreakerPolicy, evidence: CircuitEvidence, transition: CircuitTransition | undefined,
    event: AuditEventInput): CircuitRecord {
    const existingEvidence = this.db().prepare('SELECT circuit_id FROM circuit_evidence WHERE diagnosis_id = ? AND circuit_id = ?')
      .get(diagnosis.id, evidence.circuitId) as Row | undefined;
    if (existingEvidence) return this.getCircuitById(String(existingEvidence.circuit_id) as CircuitRecord['id']);
    return this.transaction(() => {
      let circuit = this.getCircuitByTarget(targetType, targetId);
      if (!circuit) {
        const id = evidence.circuitId;
        this.db().prepare(`INSERT INTO circuits
          (id,target_type,target_id,state,policy_id,policy_version,observation_window_ms,failure_threshold,cooldown_ms,qualifying_categories_json,
           opened_at,cooldown_until,version,updated_at)
          VALUES (?, ?, ?, 'closed', ?, ?, ?, ?, ?, ?, NULL, NULL, 1, ?)`).run(id, targetType, targetId, policy.id,
          policy.version, policy.observationWindowMs, policy.failureThreshold, policy.cooldownMs,
          json(policy.qualifyingCategories), evidence.observedAt);
        circuit = this.getCircuitById(id);
      }
      if (circuit.id !== evidence.circuitId || circuit.policyId !== policy.id || circuit.policyVersion !== policy.version ||
          circuit.observationWindowMs !== policy.observationWindowMs || circuit.failureThreshold !== policy.failureThreshold ||
          circuit.cooldownMs !== policy.cooldownMs || canonicalize(circuit.qualifyingCategories) !== canonicalize(policy.qualifyingCategories)) {
        throw new Error('Circuit policy or identity mismatch');
      }
      this.insertEvent(event);
      this.db().prepare(`INSERT INTO circuit_evidence(id,circuit_id,diagnosis_id,observed_at,event_id) VALUES (?, ?, ?, ?, ?)`)
        .run(evidence.id, circuit.id, diagnosis.id, evidence.observedAt, evidence.eventId);
      if (transition) {
        if (circuit.state !== transition.fromState || transition.toState !== 'open') throw new Error('Circuit transition state mismatch');
        const cooldownUntil = new Date(Date.parse(transition.occurredAt) + policy.cooldownMs).toISOString();
        this.db().prepare(`UPDATE circuits SET state='open', opened_at=?, cooldown_until=?, version=version+1, updated_at=? WHERE id=?`)
          .run(transition.occurredAt, cooldownUntil, transition.occurredAt, circuit.id);
        this.insertCircuitTransition(transition);
      }
      return this.getCircuitById(circuit.id);
    });
  }

  acquireCircuitProbe(circuitId: CircuitRecord['id'], probe: CircuitProbe, transition: CircuitTransition,
    events: readonly AuditEventInput[]): CircuitProbe {
    const existing = this.db().prepare('SELECT * FROM circuit_probes WHERE id = ?').get(probe.id) as Row | undefined;
    if (existing) return this.mapCircuitProbe(existing);
    return this.transaction(() => {
      const circuit = this.getCircuitById(circuitId);
      if (circuit.state !== 'open' || !circuit.cooldownUntil || Date.parse(probe.authorizedAt) < Date.parse(circuit.cooldownUntil)) {
        throw new Error('Circuit cooldown has not elapsed');
      }
      if (transition.fromState !== 'open' || transition.toState !== 'half_open' || transition.probeId !== probe.id) {
        throw new Error('Invalid half-open circuit transition');
      }
      this.insertEvents(events);
      this.db().prepare(`INSERT INTO circuit_probes
        (id,circuit_id,status,authorized_at,claimed_at,consumed_at,task_id,attempt_id,attempt_number,provider_offering_id,
         node_id,location_id,provider_resolution_id,resource_scheduling_decision_id,verification_id,failure_diagnosis_id,event_id)
        VALUES (?, ?, 'active', ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, ?)`)
        .run(probe.id, circuitId, probe.authorizedAt, probe.eventId);
      this.db().prepare(`UPDATE circuits SET state='half_open', version=version+1, updated_at=? WHERE id=?`)
        .run(probe.authorizedAt, circuitId);
      this.insertCircuitTransition(transition);
      return probe;
    });
  }

  claimCircuitProbe(probe: CircuitProbe, event: AuditEventInput): CircuitProbe {
    return this.transaction(() => {
      if (probe.status !== 'claimed' || !probe.claimedAt || !probe.taskId || !probe.attemptId || !probe.attemptNumber) {
        throw new Error('Circuit probe claim requires exact Task and Attempt identity');
      }
      const circuit = this.getCircuitById(probe.circuitId);
      if (circuit.state !== 'half_open') throw new Error('Circuit is not half-open');
      this.validateProbeTargetBinding(circuit, probe);
      this.insertEvent(event);
      const result = this.db().prepare(`UPDATE circuit_probes SET status='claimed',claimed_at=?,task_id=?,attempt_id=?,
        attempt_number=?,provider_offering_id=?,node_id=?,location_id=?,provider_resolution_id=?,resource_scheduling_decision_id=?
        WHERE id=? AND circuit_id=? AND status='active'`).run(probe.claimedAt, probe.taskId, probe.attemptId,
        probe.attemptNumber, probe.providerOfferingId ?? null, probe.nodeId ?? null, probe.locationId ?? null,
        probe.providerResolutionId ?? null, probe.resourceSchedulingDecisionId ?? null, probe.id, probe.circuitId);
      if (Number(result.changes) !== 1) throw new Error(`Circuit probe is already claimed: ${probe.id}`);
      return probe;
    });
  }

  recordCircuitProbeOutcome(probeId: CircuitProbe['id'], verification: Verification | undefined,
    diagnosis: FailureDiagnosis | undefined, transition: CircuitTransition, events: readonly AuditEventInput[]): CircuitRecord {
    return this.transaction(() => {
      const row = this.db().prepare(`SELECT * FROM circuit_probes WHERE id=? AND status='claimed'`).get(probeId) as Row | undefined;
      if (!row) throw new Error(`Circuit probe is not claimed: ${probeId}`);
      const probe = this.mapCircuitProbe(row);
      const circuit = this.getCircuitById(probe.circuitId);
      if (circuit.state !== 'half_open' || transition.fromState !== 'half_open' || transition.probeId !== probeId) {
        throw new Error('Circuit probe transition mismatch');
      }
      const closes = verification?.verdict === 'passed' && !diagnosis;
      if (closes !== (transition.toState === 'closed') || (!closes && transition.toState !== 'open')) {
        throw new Error('Circuit probe outcome does not match transition');
      }
      if (verification && !this.db().prepare('SELECT id FROM verifications WHERE id=?').get(verification.id)) {
        throw new Error('Circuit close requires a persisted normal Verification');
      }
      if (diagnosis && !this.db().prepare('SELECT id FROM failure_diagnoses WHERE id=?').get(diagnosis.id)) {
        throw new Error('Circuit reopen requires a persisted diagnosis');
      }
      if (verification && (verification.taskId !== probe.taskId || verification.attemptId !== probe.attemptId)) {
        throw new Error('Verification does not belong to the bound circuit probe Attempt');
      }
      if (diagnosis && (diagnosis.taskId !== probe.taskId || diagnosis.attemptId !== probe.attemptId)) {
        throw new Error('Failure diagnosis does not belong to the bound circuit probe Attempt');
      }
      this.validateBoundProbeAttempt(probe);
      const boundAttempt = this.db().prepare('SELECT status FROM attempts WHERE id=?').get(probe.attemptId) as Row;
      if (verification && String(boundAttempt.status) !== 'succeeded') {
        throw new Error('Circuit close requires a successful bound Attempt and passing Verification');
      }
      if (diagnosis && String(boundAttempt.status) !== 'failed') {
        throw new Error('Circuit reopen requires a failed bound Attempt');
      }
      this.insertEvents(events);
      this.db().prepare(`UPDATE circuit_probes SET status='consumed', consumed_at=?, verification_id=?, failure_diagnosis_id=?
        WHERE id=? AND status='claimed'`).run(transition.occurredAt, verification?.id ?? null, diagnosis?.id ?? null, probeId);
      if (closes) this.db().prepare(`UPDATE circuits SET state='closed',opened_at=NULL,cooldown_until=NULL,
        version=version+1,updated_at=? WHERE id=?`).run(transition.occurredAt, circuit.id);
      else this.db().prepare(`UPDATE circuits SET state='open',opened_at=?,cooldown_until=?,version=version+1,updated_at=? WHERE id=?`)
        .run(transition.occurredAt,
          new Date(Date.parse(transition.occurredAt) + circuit.cooldownMs).toISOString(), transition.occurredAt, circuit.id);
      this.insertCircuitTransition(transition);
      return this.getCircuitById(circuit.id);
    });
  }

  getCircuits(): CircuitRecord[] {
    return (this.db().prepare('SELECT * FROM circuits ORDER BY target_type,target_id').all() as Row[]).map((row) => this.mapCircuit(row));
  }

  getCircuitTransitions(circuitId: CircuitRecord['id']): CircuitTransition[] {
    return (this.db().prepare('SELECT * FROM circuit_transitions WHERE circuit_id=? ORDER BY occurred_at,id').all(circuitId) as Row[])
      .map((row) => this.mapCircuitTransition(row));
  }

  getCircuitEvidence(circuitId: CircuitRecord['id']): CircuitEvidence[] {
    return (this.db().prepare('SELECT * FROM circuit_evidence WHERE circuit_id=? ORDER BY observed_at,id').all(circuitId) as Row[])
      .map((row) => ({ id: String(row.id) as CircuitEvidence['id'], circuitId: String(row.circuit_id) as CircuitRecord['id'],
        diagnosisId: String(row.diagnosis_id) as FailureDiagnosisId, observedAt: String(row.observed_at),
        eventId: String(row.event_id) as CircuitEvidence['eventId'] }));
  }

  getCircuitProbes(circuitId: CircuitRecord['id']): CircuitProbe[] {
    return (this.db().prepare('SELECT * FROM circuit_probes WHERE circuit_id=? ORDER BY authorized_at,id').all(circuitId) as Row[])
      .map((row) => this.mapCircuitProbe(row));
  }

  private getCircuitByTarget(targetType: CircuitTargetType, targetId: string): CircuitRecord | undefined {
    const row = this.db().prepare('SELECT * FROM circuits WHERE target_type=? AND target_id=?').get(targetType, targetId) as Row | undefined;
    return row ? this.mapCircuit(row) : undefined;
  }

  private getCircuitById(id: CircuitRecord['id']): CircuitRecord {
    const row = this.db().prepare('SELECT * FROM circuits WHERE id=?').get(id) as Row | undefined;
    if (!row) throw new Error(`Circuit not found: ${id}`);
    return this.mapCircuit(row);
  }

  private insertCircuitTransition(value: CircuitTransition): void {
    this.db().prepare(`INSERT INTO circuit_transitions
      (id,circuit_id,from_state,to_state,reason,diagnosis_id,verification_id,probe_id,occurred_at,event_id)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`).run(value.id, value.circuitId, value.fromState, value.toState,
      value.reason, value.diagnosisId ?? null, value.verificationId ?? null, value.probeId ?? null,
      value.occurredAt, value.eventId);
  }

  private mapCircuit(row: Row): CircuitRecord {
    return { id: String(row.id) as CircuitRecord['id'], targetType: String(row.target_type) as CircuitTargetType,
      targetId: String(row.target_id), state: String(row.state) as CircuitRecord['state'], policyId: String(row.policy_id),
      policyVersion: Number(row.policy_version), observationWindowMs: Number(row.observation_window_ms),
      failureThreshold: Number(row.failure_threshold), cooldownMs: Number(row.cooldown_ms),
      qualifyingCategories: parseArray(row.qualifying_categories_json) as Failure['category'][], openedAt: optionalString(row.opened_at),
      cooldownUntil: optionalString(row.cooldown_until), version: Number(row.version), updatedAt: String(row.updated_at) };
  }

  private mapCircuitTransition(row: Row): CircuitTransition {
    return { id: String(row.id) as CircuitTransition['id'], circuitId: String(row.circuit_id) as CircuitRecord['id'],
      fromState: String(row.from_state) as CircuitTransition['fromState'], toState: String(row.to_state) as CircuitTransition['toState'],
      reason: String(row.reason), diagnosisId: optionalString(row.diagnosis_id) as CircuitTransition['diagnosisId'],
      verificationId: optionalString(row.verification_id) as CircuitTransition['verificationId'],
      probeId: optionalString(row.probe_id) as CircuitTransition['probeId'], occurredAt: String(row.occurred_at),
      eventId: String(row.event_id) as CircuitTransition['eventId'] };
  }

  private mapCircuitProbe(row: Row): CircuitProbe {
    return { id: String(row.id) as CircuitProbe['id'], circuitId: String(row.circuit_id) as CircuitRecord['id'],
      status: String(row.status) as CircuitProbe['status'], authorizedAt: String(row.authorized_at),
      claimedAt: optionalString(row.claimed_at), consumedAt: optionalString(row.consumed_at),
      taskId: optionalString(row.task_id) as CircuitProbe['taskId'], attemptId: optionalString(row.attempt_id) as CircuitProbe['attemptId'],
      attemptNumber: row.attempt_number === null ? undefined : Number(row.attempt_number),
      providerOfferingId: optionalString(row.provider_offering_id) as CircuitProbe['providerOfferingId'],
      nodeId: optionalString(row.node_id) as CircuitProbe['nodeId'], locationId: optionalString(row.location_id) as CircuitProbe['locationId'],
      providerResolutionId: optionalString(row.provider_resolution_id) as CircuitProbe['providerResolutionId'],
      resourceSchedulingDecisionId: optionalString(row.resource_scheduling_decision_id) as CircuitProbe['resourceSchedulingDecisionId'],
      verificationId: optionalString(row.verification_id) as CircuitProbe['verificationId'],
      failureDiagnosisId: optionalString(row.failure_diagnosis_id) as CircuitProbe['failureDiagnosisId'],
      eventId: String(row.event_id) as CircuitProbe['eventId'] };
  }

  private validateProbeTargetBinding(circuit: CircuitRecord, probe: CircuitProbe): void {
    if (circuit.targetType === 'provider_offering' && probe.providerOfferingId !== circuit.targetId) {
      throw new Error('Circuit probe offering binding does not match its target');
    }
    if (circuit.targetType === 'provider_offering' && !probe.providerResolutionId) {
      throw new Error('Provider circuit probe requires an exact provider resolution decision');
    }
    if (circuit.targetType === 'node' && probe.nodeId !== circuit.targetId) {
      throw new Error('Circuit probe Node binding does not match its target');
    }
    if (circuit.targetType === 'offering_location' && probe.locationId !== circuit.targetId) {
      throw new Error('Circuit probe location binding does not match its target');
    }
    if (probe.providerResolutionId) {
      const resolution = this.getProviderResolution(probe.providerResolutionId);
      if (!resolution || resolution.selectedOfferingId !== probe.providerOfferingId ||
          resolution.request.circuitProbeId !== probe.id) throw new Error('Circuit probe provider resolution binding is invalid');
    }
    if (probe.resourceSchedulingDecisionId) {
      const resource = this.getResourceSchedulingDecision(probe.resourceSchedulingDecisionId);
      if (!resource || resource.selectedNodeId !== probe.nodeId || resource.selectedLocationId !== probe.locationId ||
          resource.request.circuitProbeId !== probe.id) throw new Error('Circuit probe resource decision binding is invalid');
    }
    if ((circuit.targetType === 'node' || circuit.targetType === 'offering_location') && !probe.resourceSchedulingDecisionId) {
      throw new Error('Resource circuit probe requires an exact scheduling decision');
    }
  }

  private validateClaimedCircuitProbe(id: CircuitProbe['id'], attempt: Attempt): void {
    const row = this.db().prepare(`SELECT * FROM circuit_probes WHERE id=? AND status='claimed'`).get(id) as Row | undefined;
    if (!row) throw new Error(`Circuit probe is not claimed: ${id}`);
    const probe = this.mapCircuitProbe(row);
    if (probe.taskId !== attempt.taskId || probe.attemptId !== attempt.id || probe.attemptNumber !== attempt.attemptNumber ||
        probe.providerOfferingId !== attempt.providerOfferingId || (probe.nodeId && probe.nodeId !== attempt.computeNodeId)) {
      throw new Error('Attempt does not match claimed circuit probe authority');
    }
  }

  private validateBoundProbeAttempt(probe: CircuitProbe): void {
    const attempt = this.db().prepare(`SELECT task_id,attempt_number,provider_offering_id,compute_node_id
      FROM attempts WHERE id=?`).get(probe.attemptId) as Row | undefined;
    if (!attempt || String(attempt.task_id) !== probe.taskId || Number(attempt.attempt_number) !== probe.attemptNumber ||
        optionalString(attempt.provider_offering_id) !== probe.providerOfferingId ||
        (probe.nodeId !== undefined && optionalString(attempt.compute_node_id) !== probe.nodeId)) {
      throw new Error('Persisted Attempt does not match circuit probe binding');
    }
    if (probe.locationId) {
      const lease = this.db().prepare(`SELECT l.id FROM resource_leases l JOIN resource_scheduling_decisions d ON d.id=l.decision_id
        WHERE d.id=? AND l.location_id=? AND l.node_id=? AND l.offering_id=?`).get(probe.resourceSchedulingDecisionId,
        probe.locationId, probe.nodeId, probe.providerOfferingId) as Row | undefined;
      if (!lease) throw new Error('Circuit probe location lacks matching durable resource decision and lease');
    }
  }

  private insertAlternativeRecoveryConsumption(decisionId: AlternativeRecoveryDecisionId, attempt: Attempt, consumedAt: string): void {
      const decision = this.db().prepare(`SELECT * FROM alternative_recovery_decisions WHERE id = ? AND disposition = 'authorized'`)
        .get(decisionId) as Row | undefined;
      if (!decision || Number(decision.next_attempt_number) !== attempt.attemptNumber || String(decision.task_id) !== attempt.taskId ||
          optionalString(decision.selected_offering_id) !== attempt.providerOfferingId ||
          (decision.selected_node_id !== null && String(decision.selected_node_id) !== attempt.computeNodeId)) {
        throw new Error('Attempt does not match alternative recovery authorization');
      }
      this.db().prepare(`INSERT INTO alternative_recovery_consumptions (decision_id, attempt_id, consumed_at) VALUES (?, ?, ?)`)
        .run(decisionId, attempt.id, consumedAt);
  }

  private insertReconciliationAttemptConsumption(decisionId: ReconciliationDecisionId, attempt: Attempt, consumedAt: string): void {
    const decision = this.db().prepare(`SELECT * FROM reconciliation_decisions WHERE id = ?
      AND conclusion = 'proven_not_completed'`).get(decisionId) as Row | undefined;
    if (!decision || String(decision.task_id) !== attempt.taskId ||
        Number(decision.next_attempt_number) !== attempt.attemptNumber) {
      throw new Error('Attempt does not match reconciliation authorization');
    }
    this.db().prepare(`INSERT INTO reconciliation_attempt_consumptions (decision_id, attempt_id, consumed_at)
      VALUES (?, ?, ?)`).run(decisionId, attempt.id, consumedAt);
  }

  createApproval(value: Approval, event: AuditEventInput): void {
    this.transaction(() => {
      this.db().prepare(`INSERT INTO approvals
        (id, goal_id, task_id, attempt_id, action, scope_json, action_digest, decision, decided_by, requested_at, decided_at, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
        .run(value.id, value.goalId, value.taskId ?? null, value.attemptId ?? null, value.action, json(value.scope),
          value.actionDigest, value.decision, value.decidedBy ?? null, value.requestedAt, value.decidedAt ?? null, value.expiresAt ?? null);
      this.insertEvent(event);
    });
  }

  getApprovals(taskId: TaskId): Approval[] {
    return (this.db().prepare('SELECT * FROM approvals WHERE task_id = ? ORDER BY requested_at, id').all(taskId) as Row[])
      .map((row) => ({ id: String(row.id) as Approval['id'], goalId: String(row.goal_id) as GoalId,
        taskId: optionalString(row.task_id) as Approval['taskId'], attemptId: optionalString(row.attempt_id) as Approval['attemptId'],
        action: String(row.action), scope: parseObject(row.scope_json), actionDigest: String(row.action_digest),
        decision: String(row.decision) as Approval['decision'], decidedBy: optionalString(row.decided_by),
        requestedAt: String(row.requested_at), decidedAt: optionalString(row.decided_at), expiresAt: optionalString(row.expires_at) }));
  }

  recordApprovalPause(task: Task, expectedVersion: number, attempt: Attempt, failure: Failure,
    approval: Approval, events: readonly AuditEventInput[], diagnosis?: FailureDiagnosis): void {
    this.transaction(() => {
      this.updateAttemptRow(attempt);
      this.insertFailure(failure);
      this.insertApproval(approval);
      this.validateFailureDiagnosisPair(failure, diagnosis);
      this.insertEvents(events);
      if (diagnosis) this.insertFailureDiagnosis(diagnosis);
      this.updateTaskRow(task, expectedVersion);
    });
  }

  recordApprovalDecision(task: Task, expectedVersion: number, approval: Approval,
    events: readonly AuditEventInput[]): void {
    this.transaction(() => {
      const result = this.db().prepare(`UPDATE approvals SET decision = ?, decided_by = ?, decided_at = ?, scope_json = ?
        WHERE id = ? AND decision = 'requested'`).run(approval.decision, approval.decidedBy ?? null,
          approval.decidedAt ?? null, json(approval.scope), approval.id);
      if (Number(result.changes) !== 1) throw new Error(`Approval is not pending: ${approval.id}`);
      this.updateTaskRow(task, expectedVersion);
      this.insertEvents(events);
    });
  }

  createArtifact(value: ArtifactMetadata, event: AuditEventInput): void {
    this.transaction(() => {
      this.db().prepare(`INSERT INTO artifacts
        (id, logical_name, version, media_type, storage_reference, sha256, size_bytes, privacy_class, producer_attempt_id, provenance_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
        .run(value.id, value.logicalName, value.version, value.mediaType, value.storageReference, value.sha256,
          value.sizeBytes ?? null, value.privacyClass, value.producerAttemptId ?? null, json(value.provenance), value.createdAt);
      this.insertEvent(event);
    });
  }

  appendEvent(event: AuditEventInput): AuditEvent {
    return this.transaction(() => this.insertEvent(event));
  }

  getEvents(afterSequence = 0): AuditEvent[] {
    if (!Number.isInteger(afterSequence) || afterSequence < 0) throw new Error('afterSequence must be a non-negative integer');
    return (this.db().prepare('SELECT * FROM events WHERE sequence > ? ORDER BY sequence').all(afterSequence) as Row[])
      .map((row) => ({ sequence: Number(row.sequence), id: String(row.id) as AuditEvent['id'],
        aggregateType: String(row.aggregate_type), aggregateId: String(row.aggregate_id), eventType: String(row.event_type),
        eventVersion: Number(row.event_version), actor: String(row.actor), correlationId: optionalString(row.correlation_id),
        causationId: optionalString(row.causation_id) as AuditEvent['causationId'], occurredAt: String(row.occurred_at),
        payload: parseObject(row.payload_json), previousHash: optionalString(row.previous_hash), eventHash: String(row.event_hash) }));
  }

  private db(): DatabaseSync {
    if (!this.database) throw new Error('Persistence provider is not initialized');
    return this.database;
  }

  private transaction<T>(operation: () => T): T {
    const database = this.db();
    database.exec('BEGIN IMMEDIATE');
    try {
      const result = operation();
      database.exec('COMMIT');
      return result;
    } catch (error) {
      database.exec('ROLLBACK');
      throw error;
    }
  }

  private insertEvent(event: AuditEventInput): AuditEvent {
    validateEvent(event);
    const previous = this.db().prepare('SELECT event_hash FROM events ORDER BY sequence DESC LIMIT 1').get() as Row | undefined;
    const previousHash = previous ? String(previous.event_hash) : undefined;
    const eventHash = createHash('sha256').update(canonicalize({ previousHash: previousHash ?? null, ...event })).digest('hex');
    const result = this.db().prepare(`INSERT INTO events
      (id, aggregate_type, aggregate_id, event_type, event_version, actor, correlation_id, causation_id,
       occurred_at, payload_json, previous_hash, event_hash)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .run(event.id, event.aggregateType, event.aggregateId, event.eventType, event.eventVersion, event.actor,
        event.correlationId ?? null, event.causationId ?? null, event.occurredAt, json(event.payload), previousHash ?? null, eventHash);
    return { ...event, sequence: Number(result.lastInsertRowid), previousHash, eventHash };
  }

  private insertEvents(events: readonly AuditEventInput[]): void {
    if (events.length === 0) throw new Error('At least one workflow event is required');
    for (const event of events) this.insertEvent(event);
  }

  private insertTaskGraphRevision(revision: TaskGraphRevision): void {
    this.db().prepare('INSERT INTO task_graph_revisions(id, goal_id, revision, rationale, created_at) VALUES (?, ?, ?, ?, ?)')
      .run(revision.id, revision.goalId, revision.revision, revision.rationale ?? null, revision.createdAt);
  }

  private insertTask(task: Task): void {
    this.db().prepare(`INSERT INTO tasks
      (id, goal_id, graph_revision_id, parent_task_id, title, objective, inputs_json, required_capabilities_json,
       privacy_class, priority, status, required, retry_policy_json, verification_plan_json, terminal_reason,
       version, created_at, updated_at, completed_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .run(task.id, task.goalId, task.graphRevisionId, task.parentTaskId ?? null, task.title, task.objective,
        json(task.inputs), json(task.requiredCapabilities), task.privacyClass, task.priority, task.status,
        task.required ? 1 : 0, json(task.retryPolicy), json(task.verificationPlan), task.terminalReason ?? null,
        task.version, task.createdAt, task.updatedAt, task.completedAt ?? null);
  }

  private insertTaskDependency(dependency: TaskDependency): void {
    this.db().prepare(`INSERT INTO task_dependencies
      (graph_revision_id, predecessor_task_id, successor_task_id, condition, predicate_json, created_at)
      VALUES (?, ?, ?, ?, ?, ?)`)
      .run(dependency.graphRevisionId, dependency.predecessorTaskId, dependency.successorTaskId,
        dependency.condition, dependency.predicate === undefined ? null : json(dependency.predicate), dependency.createdAt);
  }

  private updateTaskRow(task: Task, expectedVersion: number): void {
    assertIdentifier(task.id, 'task id');
    if (task.version !== expectedVersion + 1) throw new Error('Task version must increment exactly once');
    validateTimestamp(task.updatedAt, 'task update timestamp');
    const result = this.db().prepare(`UPDATE tasks SET
      status = ?, terminal_reason = ?, version = ?, updated_at = ?, completed_at = ?
      WHERE id = ? AND version = ?`)
      .run(task.status, task.terminalReason ?? null, task.version, task.updatedAt,
        task.completedAt ?? null, task.id, expectedVersion);
    if (Number(result.changes) !== 1) throw new Error(`Task concurrency conflict: ${task.id}`);
  }

  private insertAttempt(attempt: Attempt): void {
    assertIdentifier(attempt.id, 'attempt id');
    validateTimestamp(attempt.createdAt, 'attempt creation timestamp');
    this.db().prepare(`INSERT INTO attempts
      (id, task_id, attempt_number, status, provider_offering_id, compute_node_id, input_snapshot_json,
       result_json, idempotency_key, started_at, completed_at, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .run(attempt.id, attempt.taskId, attempt.attemptNumber, attempt.status, attempt.providerOfferingId ?? null,
        attempt.computeNodeId ?? null, json(attempt.inputSnapshot), attempt.result ? json(attempt.result) : null,
        attempt.idempotencyKey ?? null, attempt.startedAt ?? null, attempt.completedAt ?? null, attempt.createdAt);
  }

  private updateAttemptRow(attempt: Attempt): void {
    assertIdentifier(attempt.id, 'attempt id');
    if (!attempt.completedAt || !['succeeded', 'failed', 'cancelled', 'indeterminate'].includes(attempt.status)) {
      throw new Error('Attempt outcome must be terminal and include completedAt');
    }
    const result = this.db().prepare(`UPDATE attempts SET status = ?, result_json = ?, completed_at = ?
      WHERE id = ? AND task_id = ? AND status = 'running'`)
      .run(attempt.status, attempt.result ? json(attempt.result) : null, attempt.completedAt, attempt.id, attempt.taskId);
    if (Number(result.changes) !== 1) throw new Error(`Attempt concurrency conflict: ${attempt.id}`);
  }

  private insertVerification(value: Verification): void {
    this.db().prepare(`INSERT INTO verifications
      (id, task_id, attempt_id, verdict, plan_version, verifier, criterion_results_json, evidence_json, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .run(value.id, value.taskId, value.attemptId ?? null, value.verdict, value.planVersion, value.verifier,
        json(value.criterionResults), json(value.evidence), value.createdAt);
  }

  private insertFailure(value: Failure): void {
    this.db().prepare(`INSERT INTO failures
      (id, task_id, attempt_id, category, classification, code, summary, details_json, retryable, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .run(value.id, value.taskId, value.attemptId ?? null, value.category, value.classification, value.code, value.summary,
        json(value.details), value.retryable ? 1 : 0, value.createdAt);
  }

  private validateFailureDiagnosisPair(failure: Failure | undefined, diagnosis: FailureDiagnosis | undefined): void {
    if (Boolean(failure) !== Boolean(diagnosis)) throw new Error('Failure and diagnosis must be persisted together');
    if (failure && diagnosis && (diagnosis.failureId !== failure.id || diagnosis.taskId !== failure.taskId ||
        diagnosis.attemptId !== failure.attemptId)) throw new Error('Failure diagnosis does not match its Failure');
  }

  private insertFailureDiagnosis(value: FailureDiagnosis): void {
    this.validateFailureDiagnosis(value);
    const failure = this.getFailure(value.failureId);
    if (!failure || failure.taskId !== value.taskId || failure.attemptId !== value.attemptId) {
      throw new Error('Failure diagnosis attribution does not match persisted Failure');
    }
    if (value.attemptId) {
      const attempt = this.db().prepare('SELECT task_id, provider_offering_id, compute_node_id FROM attempts WHERE id = ?')
        .get(value.attemptId) as Row | undefined;
      if (!attempt || String(attempt.task_id) !== value.taskId ||
          optionalString(attempt.provider_offering_id) !== value.providerOfferingId ||
          optionalString(attempt.compute_node_id) !== value.computeNodeId) {
        throw new Error('Failure diagnosis Attempt attribution is inconsistent');
      }
    }
    if (value.verificationId) {
      const verification = this.db().prepare('SELECT task_id, attempt_id FROM verifications WHERE id = ?')
        .get(value.verificationId) as Row | undefined;
      if (!verification || String(verification.task_id) !== value.taskId ||
          optionalString(verification.attempt_id) !== value.attemptId) throw new Error('Failure diagnosis Verification attribution is inconsistent');
    }
    if (value.approvalId) {
      const approval = this.db().prepare('SELECT task_id, attempt_id FROM approvals WHERE id = ?').get(value.approvalId) as Row | undefined;
      if (!approval || optionalString(approval.task_id) !== value.taskId ||
          optionalString(approval.attempt_id) !== value.attemptId) throw new Error('Failure diagnosis Approval attribution is inconsistent');
    }
    if (value.offeringLocationId) {
      const location = this.db().prepare('SELECT offering_id, node_id FROM offering_locations WHERE id = ?')
        .get(value.offeringLocationId) as Row | undefined;
      if (!location || String(location.offering_id) !== value.providerOfferingId ||
          String(location.node_id) !== value.computeNodeId) throw new Error('Failure diagnosis location attribution is inconsistent');
    }
    const diagnosisEvent = this.db().prepare('SELECT aggregate_id, event_type FROM events WHERE id = ?').get(value.eventId) as Row | undefined;
    if (!diagnosisEvent || String(diagnosisEvent.aggregate_id) !== value.taskId ||
        String(diagnosisEvent.event_type) !== 'failure.diagnosed') {
      throw new Error('Failure diagnosis Event is not persisted');
    }
    this.db().prepare(`INSERT INTO failure_diagnoses
      (id, failure_id, task_id, attempt_id, verification_id, approval_id, provider_offering_id, compute_node_id,
       offering_location_id, cause, outcome_certainty, retryable, retry_reason, disposition, diagnostic_reason,
       policy_id, policy_version, evidence_fingerprint, diagnosed_by, diagnosed_at, event_id)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`).run(value.id, value.failureId,
      value.taskId, value.attemptId ?? null, value.verificationId ?? null, value.approvalId ?? null,
      value.providerOfferingId ?? null, value.computeNodeId ?? null, value.offeringLocationId ?? null, value.cause,
      value.outcomeCertainty, value.retryable ? 1 : 0, value.retryReason, value.disposition, value.diagnosticReason,
      value.policyId, value.policyVersion, value.evidenceFingerprint, value.diagnosedBy, value.diagnosedAt, value.eventId);
  }

  private validateFailureDiagnosis(value: FailureDiagnosis): void {
    assertIdentifier(value.id, 'failure diagnosis id');
    assertIdentifier(value.failureId, 'failure diagnosis failure id');
    assertIdentifier(value.taskId, 'failure diagnosis task id');
    assertIdentifier(value.eventId, 'failure diagnosis event id');
    if (!FAILURE_CATEGORIES.has(value.cause) || !OUTCOME_CERTAINTIES.has(value.outcomeCertainty) ||
        !RECOVERY_DISPOSITIONS.has(value.disposition) || !value.retryReason.trim() || !value.diagnosticReason.trim() ||
        !value.policyId.trim() || !value.diagnosedBy.trim() || !Number.isInteger(value.policyVersion) ||
        value.policyVersion < 1 || !/^[a-f0-9]{64}$/.test(value.evidenceFingerprint) ||
        (!value.attemptId && (value.providerOfferingId || value.computeNodeId || value.offeringLocationId)) ||
        (value.disposition === 'retry_same_path' && !value.retryable) ||
        (value.cause === 'external_outcome_indeterminate' && (value.outcomeCertainty !== 'indeterminate_external_outcome' ||
          value.retryable || value.disposition !== 'reconciliation_required'))) {
      throw new Error('Invalid Failure Diagnosis');
    }
    validateTimestamp(value.diagnosedAt, 'failure diagnosis timestamp');
    if (!value.diagnosedAt.endsWith('Z') || new Date(value.diagnosedAt).toISOString() !== value.diagnosedAt) {
      throw new Error('Failure diagnosis timestamp must be canonical UTC');
    }
  }

  private validateChangedConditionEvidence(value: ChangedConditionEvidence): void {
    assertIdentifier(value.id, 'changed-condition evidence id');
    assertIdentifier(value.diagnosisId, 'changed-condition diagnosis id');
    assertIdentifier(value.eventId, 'changed-condition event id');
    const text = [value.conditionType, value.source, value.priorFactReference, value.changedFactReference]
      .filter((entry): entry is string => entry !== undefined);
    if (!value.conditionType.trim() || !value.source.trim() || value.conditionType.length > 128 || value.source.length > 128 ||
        (value.priorFactReference?.length ?? 0) > 512 || (value.changedFactReference?.length ?? 0) > 512 ||
        text.some((entry) => /[\x00-\x1f\x7f]/.test(entry) || /(?:password|secret|token|credential)\s*=/i.test(entry)) ||
        (value.priorFactReference === undefined && value.changedFactReference === undefined)) {
      throw new Error('Changed-condition evidence requires a type, source, and factual reference');
    }
    validateTimestamp(value.observedAt, 'changed-condition observation timestamp');
    if (!value.observedAt.endsWith('Z') || new Date(value.observedAt).toISOString() !== value.observedAt) {
      throw new Error('Changed-condition observation timestamp must be canonical UTC');
    }
  }

  private mapFailure(row: Row): Failure {
    const value: Failure = { id: String(row.id) as Failure['id'], taskId: String(row.task_id) as TaskId,
      attemptId: optionalString(row.attempt_id) as Failure['attemptId'], category: String(row.category) as Failure['category'],
      classification: String(row.classification) as Failure['classification'], code: String(row.code),
      summary: String(row.summary), details: parseObject(row.details_json), retryable: bool(row.retryable),
      createdAt: this.validatedTimestamp(row.created_at, 'failure timestamp') };
    assertIdentifier(value.id, 'persisted failure id');
    assertIdentifier(value.taskId, 'persisted failure task id');
    if (!FAILURE_CATEGORIES.has(value.category) || !FAILURE_CLASSIFICATIONS.has(value.classification) ||
        !value.code.trim() || !value.summary.trim()) throw new Error(`Corrupt persisted Failure: ${value.id}`);
    return value;
  }

  private mapFailureDiagnosis(row: Row): FailureDiagnosis {
    const id = String(row.id) as FailureDiagnosis['id'];
    try {
      const value: FailureDiagnosis = { id, failureId: String(row.failure_id) as FailureId,
        taskId: String(row.task_id) as TaskId, attemptId: optionalString(row.attempt_id) as FailureDiagnosis['attemptId'],
        verificationId: optionalString(row.verification_id) as FailureDiagnosis['verificationId'],
        approvalId: optionalString(row.approval_id) as FailureDiagnosis['approvalId'],
        providerOfferingId: optionalString(row.provider_offering_id), computeNodeId: optionalString(row.compute_node_id),
        offeringLocationId: optionalString(row.offering_location_id) as FailureDiagnosis['offeringLocationId'],
        cause: String(row.cause) as Failure['category'], outcomeCertainty: String(row.outcome_certainty) as FailureDiagnosis['outcomeCertainty'],
        retryable: bool(row.retryable), retryReason: String(row.retry_reason),
        disposition: String(row.disposition) as FailureDiagnosis['disposition'], diagnosticReason: String(row.diagnostic_reason),
        policyId: String(row.policy_id), policyVersion: Number(row.policy_version), evidenceFingerprint: String(row.evidence_fingerprint),
        diagnosedBy: String(row.diagnosed_by), diagnosedAt: String(row.diagnosed_at), eventId: String(row.event_id) as FailureDiagnosis['eventId'] };
      this.validateFailureDiagnosis(value);
      const failure = this.getFailure(value.failureId);
      if (!failure || failure.taskId !== value.taskId || failure.attemptId !== value.attemptId) throw new Error('failure mismatch');
      if (value.attemptId) {
        const attempt = this.db().prepare('SELECT task_id, provider_offering_id, compute_node_id FROM attempts WHERE id = ?')
          .get(value.attemptId) as Row | undefined;
        if (!attempt || String(attempt.task_id) !== value.taskId ||
            optionalString(attempt.provider_offering_id) !== value.providerOfferingId ||
            optionalString(attempt.compute_node_id) !== value.computeNodeId) throw new Error('attempt mismatch');
      }
      if (value.verificationId) {
        const verification = this.db().prepare('SELECT task_id, attempt_id FROM verifications WHERE id = ?')
          .get(value.verificationId) as Row | undefined;
        if (!verification || String(verification.task_id) !== value.taskId ||
            optionalString(verification.attempt_id) !== value.attemptId) throw new Error('verification mismatch');
      }
      if (value.approvalId) {
        const approval = this.db().prepare('SELECT task_id, attempt_id FROM approvals WHERE id = ?')
          .get(value.approvalId) as Row | undefined;
        if (!approval || optionalString(approval.task_id) !== value.taskId ||
            optionalString(approval.attempt_id) !== value.attemptId) throw new Error('approval mismatch');
      }
      if (value.offeringLocationId) {
        const location = this.db().prepare('SELECT offering_id, node_id FROM offering_locations WHERE id = ?')
          .get(value.offeringLocationId) as Row | undefined;
        if (!location || String(location.offering_id) !== value.providerOfferingId ||
            String(location.node_id) !== value.computeNodeId) throw new Error('location mismatch');
      }
      const diagnosisEvent = this.db().prepare('SELECT aggregate_id, event_type FROM events WHERE id = ?')
        .get(value.eventId) as Row | undefined;
      if (!diagnosisEvent || String(diagnosisEvent.aggregate_id) !== value.taskId ||
          String(diagnosisEvent.event_type) !== 'failure.diagnosed') throw new Error('event mismatch');
      return value;
    } catch (error) {
      throw new Error(`Corrupt persisted Failure Diagnosis: ${id}`, { cause: error });
    }
  }

  private mapChangedConditionEvidence(row: Row): ChangedConditionEvidence {
    const id = String(row.id) as ChangedConditionEvidence['id'];
    try {
      const value: ChangedConditionEvidence = { id, diagnosisId: String(row.diagnosis_id) as FailureDiagnosisId,
        conditionType: String(row.condition_type), priorFactReference: optionalString(row.prior_fact_reference),
        changedFactReference: optionalString(row.changed_fact_reference), source: String(row.source),
        observedAt: String(row.observed_at), eventId: String(row.event_id) as ChangedConditionEvidence['eventId'] };
      this.validateChangedConditionEvidence(value);
      const relation = this.db().prepare(`SELECT d.task_id, e.aggregate_type, e.aggregate_id, e.event_type
        FROM failure_diagnoses d JOIN events e ON e.id = ? WHERE d.id = ?`).get(value.eventId, value.diagnosisId) as Row | undefined;
      if (!relation || String(relation.aggregate_type) !== 'task' || String(relation.aggregate_id) !== String(relation.task_id) ||
          String(relation.event_type) !== 'failure.changed-condition-recorded') throw new Error('event mismatch');
      return value;
    } catch (error) {
      throw new Error(`Corrupt persisted Changed-Condition Evidence: ${id}`, { cause: error });
    }
  }

  private mapAlternativeRecoveryDecision(row: Row): AlternativeRecoveryDecision {
    const value: AlternativeRecoveryDecision = {
      id: String(row.id) as AlternativeRecoveryDecision['id'],
      diagnosisId: String(row.diagnosis_id) as FailureDiagnosisId,
      failureId: String(row.failure_id) as FailureId,
      taskId: String(row.task_id) as TaskId,
      failedAttemptId: String(row.failed_attempt_id) as AlternativeRecoveryDecision['failedAttemptId'],
      requestedDisposition: String(row.requested_disposition) as AlternativeRecoveryDecision['requestedDisposition'],
      disposition: String(row.disposition) as AlternativeRecoveryDecision['disposition'], reason: String(row.reason),
      nextAttemptNumber: row.next_attempt_number === null ? undefined : Number(row.next_attempt_number),
      failedOfferingId: optionalString(row.failed_offering_id) as AlternativeRecoveryDecision['failedOfferingId'],
      failedNodeId: optionalString(row.failed_node_id) as AlternativeRecoveryDecision['failedNodeId'],
      failedLocationId: optionalString(row.failed_location_id) as AlternativeRecoveryDecision['failedLocationId'],
      selectedOfferingId: optionalString(row.selected_offering_id) as AlternativeRecoveryDecision['selectedOfferingId'],
      selectedNodeId: optionalString(row.selected_node_id) as AlternativeRecoveryDecision['selectedNodeId'],
      selectedLocationId: optionalString(row.selected_location_id) as AlternativeRecoveryDecision['selectedLocationId'],
      providerResolutionId: optionalString(row.provider_resolution_id) as AlternativeRecoveryDecision['providerResolutionId'],
      resourceSchedulingDecisionId: optionalString(row.resource_scheduling_decision_id) as AlternativeRecoveryDecision['resourceSchedulingDecisionId'],
      changedConditionEvidenceId: optionalString(row.changed_condition_evidence_id) as AlternativeRecoveryDecision['changedConditionEvidenceId'],
      actor: String(row.actor), decidedAt: String(row.decided_at), eventId: String(row.event_id) as AlternativeRecoveryDecision['eventId'],
    };
    if (!value.reason.trim() || !value.actor.trim() || Number.isNaN(Date.parse(value.decidedAt)) ||
        (value.disposition === 'authorized' && (!value.nextAttemptNumber || !value.changedConditionEvidenceId))) {
      throw new Error(`Corrupt persisted Alternative Recovery Decision: ${value.id}`);
    }
    return value;
  }

  private mapReconciliationDecision(row: Row): ReconciliationDecision {
    const id = String(row.id) as ReconciliationDecision['id'];
    try {
      const value: ReconciliationDecision = { id, taskId: String(row.task_id) as TaskId,
        attemptId: String(row.attempt_id) as ReconciliationDecision['attemptId'],
        failureId: String(row.failure_id) as FailureId, diagnosisId: String(row.diagnosis_id) as FailureDiagnosisId,
        providerId: String(row.provider_id), providerVersion: Number(row.provider_version),
        operationId: String(row.operation_id), evidence: parseObject(row.evidence_json),
        evidenceFingerprint: String(row.evidence_fingerprint),
        conclusion: String(row.conclusion) as ReconciliationDecision['conclusion'], reason: String(row.reason),
        observationNumber: Number(row.observation_number),
        nextAttemptNumber: row.next_attempt_number === null ? undefined : Number(row.next_attempt_number),
        verificationId: optionalString(row.verification_id) as ReconciliationDecision['verificationId'],
        actor: String(row.actor), decidedAt: this.validatedTimestamp(row.decided_at, 'reconciliation timestamp'),
        eventId: String(row.event_id) as ReconciliationDecision['eventId'] };
      if (!value.providerId.trim() || value.providerVersion < 1 || !value.operationId.trim() || !value.reason.trim() ||
          !/^[a-f0-9]{64}$/.test(value.evidenceFingerprint) || value.observationNumber < 1 ||
          !['proven_completed', 'proven_not_completed', 'remains_indeterminate'].includes(value.conclusion) ||
          (value.conclusion !== 'proven_not_completed' && value.nextAttemptNumber !== undefined)) throw new Error('invalid fields');
      const source = this.db().prepare(`SELECT a.task_id, a.status, f.task_id failure_task_id, f.attempt_id failure_attempt_id,
        d.task_id diagnosis_task_id, d.failure_id diagnosis_failure_id, d.attempt_id diagnosis_attempt_id
        FROM attempts a JOIN failures f ON f.id = ? JOIN failure_diagnoses d ON d.id = ? WHERE a.id = ?`)
        .get(value.failureId, value.diagnosisId, value.attemptId) as Row | undefined;
      if (!source || String(source.task_id) !== value.taskId || String(source.failure_task_id) !== value.taskId ||
          String(source.failure_attempt_id) !== value.attemptId || String(source.diagnosis_task_id) !== value.taskId ||
          String(source.diagnosis_failure_id) !== value.failureId || String(source.diagnosis_attempt_id) !== value.attemptId) {
        throw new Error('source attribution mismatch');
      }
      return value;
    } catch (error) {
      throw new Error(`Corrupt persisted Reconciliation Decision: ${id}`, { cause: error });
    }
  }

  private insertApproval(value: Approval): void {
    this.db().prepare(`INSERT INTO approvals
      (id, goal_id, task_id, attempt_id, action, scope_json, action_digest, decision, decided_by, requested_at, decided_at, expires_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .run(value.id, value.goalId, value.taskId ?? null, value.attemptId ?? null, value.action, json(value.scope),
        value.actionDigest, value.decision, value.decidedBy ?? null, value.requestedAt, value.decidedAt ?? null, value.expiresAt ?? null);
  }

  private validateGoal(goal: Goal): void {
    assertIdentifier(goal.id, 'goal id');
    if (!goal.objective.trim()) throw new Error('Goal objective is required');
    validateTimestamp(goal.createdAt, 'goal creation timestamp');
    validateTimestamp(goal.updatedAt, 'goal update timestamp');
  }

  private validateLegacyImport(value: LegacyImportWrite): void {
    const { operation, records } = value;
    assertIdentifier(operation.id, 'legacy import operation id');
    if (!/^[a-f0-9]{64}$/.test(operation.sourceDigest)) throw new Error('Legacy source digest must be SHA-256');
    if (!operation.sourceReference.trim()) throw new Error('Legacy source reference is required');
    if (!Number.isInteger(operation.assessmentVersion) || operation.assessmentVersion < 1) {
      throw new Error('Legacy assessment version must be a positive integer');
    }
    validateTimestamp(operation.importedAt, 'legacy import timestamp');
    if (operation.importedRecordCount !== records.length) throw new Error('Legacy import record count mismatch');
    const keys = new Set<string>();
    for (const record of records) {
      if (record.importOperationId !== operation.id || record.sourceDigest !== operation.sourceDigest ||
          record.sourceReference !== operation.sourceReference || record.assessmentVersion !== operation.assessmentVersion ||
          record.importedAt !== operation.importedAt) throw new Error('Legacy record provenance does not match its import operation');
      if (!record.sourceSection.trim() || !record.sourceKey.trim() || !record.legacyStatus.trim()) {
        throw new Error('Legacy record section, key, and status are required');
      }
      const key = `${record.sourceSection}\u0000${record.sourceKey}`;
      if (keys.has(key)) throw new Error(`Duplicate legacy record: ${record.sourceSection}/${record.sourceKey}`);
      keys.add(key);
    }
  }

  private mapLegacyImport(row: Row): LegacyImportOperation {
    const operation = { id: String(row.id), sourceDigest: String(row.source_digest), sourceReference: String(row.source_reference),
      assessmentVersion: Number(row.assessment_version), importedRecordCount: Number(row.imported_record_count),
      importedAt: this.validatedTimestamp(row.imported_at, 'legacy import timestamp') };
    if (!/^[a-f0-9]{64}$/.test(operation.sourceDigest) || operation.assessmentVersion < 1 || operation.importedRecordCount < 0) {
      throw new Error(`Corrupt persisted legacy import operation: ${operation.id}`);
    }
    return operation;
  }

  private validateTaskGraphRevision(revision: TaskGraphRevision): void {
    assertIdentifier(revision.id, 'task graph revision id');
    assertIdentifier(revision.goalId, 'goal id');
    if (!Number.isInteger(revision.revision) || revision.revision < 1) {
      throw new Error('Task graph revision number must be a positive integer');
    }
    validateTimestamp(revision.createdAt, 'task graph revision timestamp');
  }

  private validateTask(task: Task): void {
    assertIdentifier(task.id, 'task id');
    assertIdentifier(task.goalId, 'goal id');
    assertIdentifier(task.graphRevisionId, 'task graph revision id');
    if (task.parentTaskId) assertIdentifier(task.parentTaskId, 'parent task id');
    if (!task.title.trim() || !task.objective.trim()) throw new Error('Task title and objective are required');
    if (!TASK_STATUSES.has(task.status)) throw new Error(`Invalid Task status: ${task.status}`);
    if (!TASK_PRIORITIES.has(task.priority)) throw new Error(`Invalid Task priority: ${task.priority}`);
    if (!PRIVACY_CLASSES.has(task.privacyClass)) throw new Error(`Invalid Task privacy class: ${task.privacyClass}`);
    if (!Number.isInteger(task.version) || task.version < 1) throw new Error('Task version must be a positive integer');
    if (!Array.isArray(task.requiredCapabilities) || task.requiredCapabilities.some((value) => typeof value !== 'string')) {
      throw new Error('Task required capabilities must be a string array');
    }
    validateTimestamp(task.createdAt, 'task creation timestamp');
    validateTimestamp(task.updatedAt, 'task update timestamp');
    if (task.completedAt) validateTimestamp(task.completedAt, 'task completion timestamp');
  }

  private validatedTimestamp(value: unknown, label: string): string {
    const timestamp = String(value);
    validateTimestamp(timestamp, label);
    return timestamp;
  }

  private insertCriterion(criterion: GoalSuccessCriterion): void {
    assertIdentifier(criterion.id, 'goal criterion id');
    validateTimestamp(criterion.createdAt, 'criterion creation timestamp');
    this.db().prepare(`INSERT INTO goal_success_criteria
      (id, goal_id, description, required, verification_method, position, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)`)
      .run(criterion.id, criterion.goalId, criterion.description, criterion.required ? 1 : 0,
        criterion.verificationMethod, criterion.position, criterion.createdAt);
  }

  private mapGoal(row: Row): Goal {
    return { id: String(row.id) as Goal['id'], objective: String(row.objective), constraints: parseObject(row.constraints_json),
      priority: String(row.priority) as Goal['priority'], privacyClass: String(row.privacy_class) as Goal['privacyClass'],
      status: String(row.status) as Goal['status'], activeGraphRevisionId: optionalString(row.active_graph_revision_id) as Goal['activeGraphRevisionId'],
      terminalReason: optionalString(row.terminal_reason), version: Number(row.version), createdAt: String(row.created_at),
      updatedAt: String(row.updated_at), completedAt: optionalString(row.completed_at) };
  }

  private mapTaskGraphRevision(row: Row): TaskGraphRevision {
    const revision: TaskGraphRevision = {
      id: String(row.id) as TaskGraphRevisionId,
      goalId: String(row.goal_id) as GoalId,
      revision: Number(row.revision),
      rationale: optionalString(row.rationale),
      createdAt: this.validatedTimestamp(row.created_at, 'persisted task graph revision timestamp'),
    };
    this.validateTaskGraphRevision(revision);
    return revision;
  }

  private mapCriterion(row: Row): GoalSuccessCriterion {
    return { id: String(row.id) as GoalSuccessCriterion['id'], goalId: String(row.goal_id) as GoalId,
      description: String(row.description), required: bool(row.required), verificationMethod: String(row.verification_method),
      position: Number(row.position), createdAt: String(row.created_at) };
  }

  private mapTask(row: Row): Task {
    const task = { id: String(row.id) as TaskId, goalId: String(row.goal_id) as GoalId,
      graphRevisionId: String(row.graph_revision_id) as TaskGraphRevisionId, parentTaskId: optionalString(row.parent_task_id) as TaskId,
      title: String(row.title), objective: String(row.objective), inputs: parseObject(row.inputs_json),
      requiredCapabilities: parseArray(row.required_capabilities_json), privacyClass: String(row.privacy_class) as Task['privacyClass'],
      priority: String(row.priority) as Task['priority'], status: String(row.status) as Task['status'], required: bool(row.required),
      retryPolicy: parseObject(row.retry_policy_json) as Task['retryPolicy'], verificationPlan: parseObject(row.verification_plan_json),
      terminalReason: optionalString(row.terminal_reason), version: Number(row.version), createdAt: String(row.created_at),
      updatedAt: String(row.updated_at), completedAt: optionalString(row.completed_at) };
    this.validateTask(task);
    const isTerminal = ['succeeded', 'failed', 'cancelled', 'superseded'].includes(task.status);
    if (isTerminal !== Boolean(task.completedAt)) throw new Error(`Corrupt persisted Task completion state: ${task.id}`);
    return task;
  }

  private mapAttempt(row: Row): Attempt {
    const attempt = { id: String(row.id) as Attempt['id'], taskId: String(row.task_id) as TaskId,
      attemptNumber: Number(row.attempt_number), status: String(row.status) as Attempt['status'],
      providerOfferingId: optionalString(row.provider_offering_id), computeNodeId: optionalString(row.compute_node_id),
      inputSnapshot: parseObject(row.input_snapshot_json), result: row.result_json === null ? undefined : parseObject(row.result_json),
      idempotencyKey: optionalString(row.idempotency_key), startedAt: optionalString(row.started_at),
      completedAt: optionalString(row.completed_at), createdAt: String(row.created_at) };
    assertIdentifier(attempt.id, 'persisted attempt id');
    assertIdentifier(attempt.taskId, 'persisted attempt task id');
    if (!Number.isInteger(attempt.attemptNumber) || attempt.attemptNumber < 1) throw new Error('Corrupt persisted Attempt number');
    if (!ATTEMPT_STATUSES.has(attempt.status)) throw new Error(`Corrupt persisted Attempt status: ${attempt.status}`);
    validateTimestamp(attempt.createdAt, 'persisted attempt creation timestamp');
    if (attempt.startedAt) validateTimestamp(attempt.startedAt, 'persisted attempt start timestamp');
    if (attempt.completedAt) validateTimestamp(attempt.completedAt, 'persisted attempt completion timestamp');
    const isTerminal = ['succeeded', 'failed', 'cancelled', 'indeterminate'].includes(attempt.status);
    if (isTerminal !== Boolean(attempt.completedAt)) throw new Error(`Corrupt persisted Attempt completion state: ${attempt.id}`);
    return attempt;
  }

  private mapNode(row: Row): Node & { version: number } {
    const node: Node & { version: number } = { id: String(row.id) as Node['id'], name: String(row.name),
      administrativeState: String(row.administrative_state) as Node['administrativeState'],
      configurationReference: String(row.configuration_reference),
      createdAt: this.validatedTimestamp(row.created_at, 'node creation timestamp'), version: Number(row.version) };
    assertIdentifier(node.id, 'persisted node id');
    if (!node.name.trim() || !node.configurationReference.trim() ||
        !['active', 'draining', 'disabled'].includes(node.administrativeState) ||
        !Number.isInteger(node.version) || node.version < 1) {
      throw new Error(`Corrupt persisted Node: ${node.id}`);
    }
    return node;
  }

  private mapWorkstationWorkloadEvaluation(row: Row): WorkstationWorkloadEvaluation {
    const id = String(row.id) as WorkstationWorkloadEvaluation['id'];
    try {
      const value: WorkstationWorkloadEvaluation = { id, nodeId: String(row.node_id) as Node['id'],
        ruleFingerprint: String(row.rule_fingerprint), processBasenames: parseArray(row.process_basenames_json),
        matchedRuleIds: parseArray(row.matched_rule_ids_json),
        recommendation: String(row.recommendation) as WorkstationWorkloadEvaluation['recommendation'],
        evaluatedAt: this.validatedTimestamp(row.evaluated_at, 'workstation workload evaluation timestamp') };
      assertIdentifier(value.id, 'persisted workstation workload evaluation id');
      assertIdentifier(value.nodeId, 'persisted workstation workload evaluation node id');
      if (!value.ruleFingerprint.trim() ||
          !['recommend_draining', 'recommend_active', 'inconclusive'].includes(value.recommendation)) {
        throw new Error('invalid fields');
      }
      return value;
    } catch (error) {
      throw new Error(`Corrupt persisted Workstation Workload Evaluation: ${id}`, { cause: error });
    }
  }

  private mapWorkstationAvailabilityPolicyApplication(row: Row): WorkstationAvailabilityPolicyApplication {
    const id = String(row.id) as WorkstationAvailabilityPolicyApplication['id'];
    try {
      const states: readonly Node['administrativeState'][] = ['active', 'draining', 'disabled'];
      const dispositions: readonly WorkstationAvailabilityPolicyApplication['disposition'][] = [
        'applied_transition', 'already_satisfied', 'inconclusive', 'stale_evidence', 'state_version_mismatch',
        'rule_fingerprint_mismatch', 'policy_ownership_mismatch', 'disabled_node', 'node_mismatch',
        'superseded_evidence', 'invalid_evidence',
      ];
      const value: WorkstationAvailabilityPolicyApplication = {
        id, evaluationId: String(row.evaluation_id) as WorkstationAvailabilityPolicyApplication['evaluationId'],
        nodeId: String(row.node_id) as Node['id'], policyId: String(row.policy_id), policyVersion: Number(row.policy_version),
        ruleFingerprint: String(row.rule_fingerprint), actor: String(row.actor), reason: String(row.reason),
        expectedNodeState: String(row.expected_node_state) as Node['administrativeState'],
        expectedNodeVersion: Number(row.expected_node_version),
        observedNodeState: String(row.observed_node_state) as Node['administrativeState'],
        observedNodeVersion: Number(row.observed_node_version),
        recommendation: String(row.recommendation) as WorkstationWorkloadEvaluation['recommendation'],
        disposition: String(row.disposition) as WorkstationAvailabilityPolicyApplication['disposition'],
        transitionOccurred: bool(row.transition_occurred),
        resultingNodeState: optionalString(row.resulting_node_state) as Node['administrativeState'] | undefined,
        resultingNodeVersion: row.resulting_node_version === null ? undefined : Number(row.resulting_node_version),
        appliedAt: this.validatedTimestamp(row.applied_at, 'workstation availability policy application timestamp'),
      };
      assertIdentifier(value.id, 'persisted workstation availability policy application id');
      assertIdentifier(value.evaluationId, 'persisted workstation availability policy evaluation id');
      assertIdentifier(value.nodeId, 'persisted workstation availability policy node id');
      if (!value.policyId.trim() || !value.ruleFingerprint.trim() || !value.actor.trim() || !value.reason.trim() ||
          !Number.isInteger(value.policyVersion) || value.policyVersion < 1 ||
          !Number.isInteger(value.expectedNodeVersion) || value.expectedNodeVersion < 1 ||
          !Number.isInteger(value.observedNodeVersion) || value.observedNodeVersion < 1 ||
          !states.includes(value.expectedNodeState) || !states.includes(value.observedNodeState) ||
          !dispositions.includes(value.disposition) || value.transitionOccurred !== (value.disposition === 'applied_transition') ||
          !value.resultingNodeState || !states.includes(value.resultingNodeState) ||
          !Number.isInteger(value.resultingNodeVersion) || value.resultingNodeVersion! < 1 ||
          value.resultingNodeVersion !== value.observedNodeVersion + (value.transitionOccurred ? 1 : 0)) {
        throw new Error('invalid fields');
      }
      return value;
    } catch (error) {
      throw new Error(`Corrupt persisted Workstation Availability Policy Application: ${id}`, { cause: error });
    }
  }

  private mapOfferingLocation(row: Row): OfferingLocation {
    const location: OfferingLocation = { id: String(row.id) as OfferingLocation['id'],
      nodeId: String(row.node_id) as Node['id'], offeringId: String(row.offering_id) as ProviderOffering['id'],
      enabled: bool(row.enabled), capacity: Number(row.capacity),
      privacyClasses: parseArray(row.privacy_classes_json) as OfferingLocation['privacyClasses'],
      createdAt: this.validatedTimestamp(row.created_at, 'offering location creation timestamp') };
    assertIdentifier(location.id, 'persisted offering location id');
    assertIdentifier(location.nodeId, 'persisted offering location node id');
    if (!Number.isInteger(location.capacity) || location.capacity <= 0 ||
        location.privacyClasses.some((value) => !PRIVACY_CLASSES.has(value))) {
      throw new Error(`Corrupt persisted Offering Location: ${location.id}`);
    }
    return location;
  }

  private mapNodeHealth(row: Row): NodeHealthObservation {
    const observation: NodeHealthObservation = { id: String(row.id) as NodeHealthObservation['id'],
      nodeId: String(row.node_id) as Node['id'], status: String(row.status) as NodeHealthObservation['status'],
      observedAt: this.validatedTimestamp(row.observed_at, 'node health observation timestamp') };
    assertIdentifier(observation.id, 'persisted node health observation id');
    if (!['healthy', 'degraded', 'unhealthy', 'unknown'].includes(observation.status)) {
      throw new Error(`Corrupt persisted Node Health Observation: ${observation.id}`);
    }
    return observation;
  }

  private mapResourceSchedulingDecision(row: Row): ResourceSchedulingDecision {
    const request = parseObject(row.request_json) as unknown as ResourceSchedulingDecision['request'];
    const candidates = JSON.parse(String(row.candidates_json)) as ResourceSchedulingDecision['candidates'];
    if (!Array.isArray(candidates) || request.id !== row.id || request.offeringId !== row.offering_id) {
      throw new Error(`Corrupt persisted Resource Scheduling Decision: ${String(row.id)}`);
    }
    validateTimestamp(request.requestedAt, 'resource scheduling request timestamp');
    const decision: ResourceSchedulingDecision = { request, candidates,
      selectedLocationId: optionalString(row.selected_location_id) as OfferingLocation['id'] | undefined,
      selectedNodeId: optionalString(row.selected_node_id) as Node['id'] | undefined,
      explanation: String(row.explanation),
      decidedAt: this.validatedTimestamp(row.decided_at, 'resource scheduling decision timestamp') };
    if (!decision.explanation.trim() || Boolean(decision.selectedLocationId) !== Boolean(decision.selectedNodeId)) {
      throw new Error(`Corrupt persisted Resource Scheduling Decision: ${request.id}`);
    }
    return decision;
  }

  private mapResourceLease(row: Row): ResourceLease {
    const lease: ResourceLease = { id: String(row.id) as ResourceLease['id'],
      decisionId: String(row.decision_id) as ResourceLease['decisionId'],
      offeringId: String(row.offering_id) as ProviderOffering['id'],
      locationId: String(row.location_id) as OfferingLocation['id'], nodeId: String(row.node_id) as Node['id'],
      capacity: Number(row.capacity), status: String(row.status) as ResourceLease['status'],
      acquiredAt: this.validatedTimestamp(row.acquired_at, 'resource lease acquisition timestamp'),
      expiresAt: this.validatedTimestamp(row.expires_at, 'resource lease expiry timestamp'),
      releasedAt: optionalString(row.released_at) };
    assertIdentifier(lease.id, 'persisted resource lease id');
    if (!Number.isInteger(lease.capacity) || lease.capacity <= 0 ||
        !['active', 'released', 'expired'].includes(lease.status) ||
        (lease.status === 'active') !== !lease.releasedAt || Date.parse(lease.expiresAt) <= Date.parse(lease.acquiredAt)) {
      throw new Error(`Corrupt persisted Resource Lease: ${lease.id}`);
    }
    if (lease.releasedAt) validateTimestamp(lease.releasedAt, 'resource lease release timestamp');
    return lease;
  }
}

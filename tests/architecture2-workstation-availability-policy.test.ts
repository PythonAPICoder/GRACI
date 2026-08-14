import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { asIdentifier, type AuditEventInput, type Node, type WorkstationAvailabilityPolicyApplicationRequest,
  type WorkstationWorkloadEvaluation } from '../src/architecture2/domain/index.js';
import { migrations } from '../src/architecture2/persistence/sqlite/migrations.js';
import { SqliteArchitecture2Persistence } from '../src/architecture2/persistence/sqlite/sqlite-persistence.js';
import { DeterministicResourceScheduler, WorkstationAvailabilityPolicy,
  WORKSTATION_AVAILABILITY_POLICY_ID, WORKSTATION_AVAILABILITY_POLICY_VERSION } from '../src/architecture2/resources/index.js';

const EVALUATED_AT = '2026-08-13T20:00:00.000Z';
const APPLIED_AT = '2026-08-13T20:01:00.000Z';
const FINGERPRINT = 'a'.repeat(64);
let eventSequence = 0;

describe('Architecture 2 workstation availability policy', () => {
  let directory: string;
  let databasePath: string;
  let persistence: SqliteArchitecture2Persistence;
  let policy: WorkstationAvailabilityPolicy;

  beforeEach(() => {
    eventSequence = 0;
    directory = mkdtempSync(join(tmpdir(), 'graci-phase1j-'));
    databasePath = join(directory, 'architecture2.sqlite');
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    policy = new WorkstationAvailabilityPolicy(persistence);
  });

  afterEach(() => {
    persistence.close();
    rmSync(directory, { recursive: true, force: true });
  });

  const node = (id = 'workstation', state: Node['administrativeState'] = 'active'): Node => ({
    id: asIdentifier<'Node'>(id), name: id, administrativeState: state,
    configurationReference: `config:${id}`, createdAt: EVALUATED_AT,
  });
  const event = (nodeId: Node['id'], id?: string): AuditEventInput => ({
    id: asIdentifier<'Event'>(id ?? `phase1j-event-${++eventSequence}`), aggregateId: nodeId, aggregateType: 'node',
    eventType: 'node.workstation-availability-policy-applied', eventVersion: 1, actor: 'administrator',
    occurredAt: APPLIED_AT, payload: {},
  });
  const evaluation = (value: Node, recommendation: WorkstationWorkloadEvaluation['recommendation'],
    id = `evaluation-${recommendation}`, evaluatedAt = EVALUATED_AT): WorkstationWorkloadEvaluation => ({
    id: asIdentifier<'WorkstationWorkloadEvaluation'>(id), nodeId: value.id, ruleFingerprint: FINGERPRINT,
    processBasenames: recommendation === 'recommend_draining' ? ['game.exe'] : [],
    matchedRuleIds: recommendation === 'recommend_draining' ? ['game'] : [], recommendation, evaluatedAt,
  });
  const request = (value: Node, evidence: WorkstationWorkloadEvaluation, version = 1,
    state: Node['administrativeState'] = value.administrativeState,
    id = `application-${evidence.id}`): WorkstationAvailabilityPolicyApplicationRequest => ({
    id: asIdentifier<'WorkstationAvailabilityPolicyApplication'>(id), evaluationId: evidence.id, nodeId: value.id,
    policyId: WORKSTATION_AVAILABILITY_POLICY_ID, policyVersion: WORKSTATION_AVAILABILITY_POLICY_VERSION,
    expectedRuleFingerprint: FINGERPRINT, expectedNodeState: state, expectedNodeVersion: version,
    maximumEvidenceAgeMs: 120_000, actor: 'administrator', reason: 'Apply durable workstation evidence', appliedAt: APPLIED_AT,
  });
  const persist = (value: Node, evidence: WorkstationWorkloadEvaluation) => {
    persistence.registerNode(value, [], [event(value.id)]);
    persistence.recordWorkstationWorkloadEvaluation(evidence, event(value.id));
  };

  it('applies draining, blocks scheduling, and preserves existing leases and attempts', () => {
    const value = node();
    const evidence = evaluation(value, 'recommend_draining');
    persist(value, evidence);
    const result = policy.apply(request(value, evidence), event(value.id));
    expect(result).toMatchObject({ disposition: 'applied_transition', transitionOccurred: true,
      resultingNodeState: 'draining', resultingNodeVersion: 2 });
    const current = persistence.getNodes()[0]!;
    const scheduler = new DeterministicResourceScheduler();
    const offeringId = asIdentifier<'ProviderOffering'>('offering');
    const decision = scheduler.schedule({ id: asIdentifier<'ResourceSchedulingDecision'>('decision'), offeringId,
      privacyClass: 'internal', requiredCapacity: 1, maximumHealthAgeMs: 60_000, requestedAt: APPLIED_AT }, {
      nodes: [current], locations: [{ id: asIdentifier<'OfferingLocation'>('location'), nodeId: value.id, offeringId,
        enabled: true, capacity: 1, privacyClasses: ['internal'], createdAt: EVALUATED_AT }],
      healthObservations: [{ id: asIdentifier<'NodeHealthObservation'>('health'), nodeId: value.id,
        status: 'healthy', observedAt: APPLIED_AT }], leases: [],
    });
    expect(decision.candidates[0]?.rejectionReasons).toContain('node_draining');
    expect(persistence.getResourceLeases()).toEqual([]);
  });

  it('reactivates only a drain owned by this policy', () => {
    const value = node();
    const drain = evaluation(value, 'recommend_draining', 'drain-evaluation');
    persist(value, drain);
    policy.apply(request(value, drain, 1, 'active', 'drain-application'), event(value.id));
    const active = evaluation(value, 'recommend_active', 'active-evaluation', '2026-08-13T20:00:30.000Z');
    persistence.recordWorkstationWorkloadEvaluation(active, event(value.id));
    const result = policy.apply(request({ ...value, administrativeState: 'draining' }, active, 2, 'draining',
      'active-application'), event(value.id));
    expect(result.disposition).toBe('applied_transition');
    expect(persistence.getNodes()[0]).toMatchObject({ administrativeState: 'active', version: 3 });
  });

  it('never reactivates a manual drain', () => {
    const value = node();
    const active = evaluation(value, 'recommend_active');
    persist(value, active);
    persistence.transitionNodeAdministrativeState(value.id, 1, 'active', 'draining', 'administrator', 'Manual drain',
      EVALUATED_AT, { ...event(value.id), occurredAt: EVALUATED_AT });
    const result = policy.apply(request({ ...value, administrativeState: 'draining' }, active, 2, 'draining'), event(value.id));
    expect(result.disposition).toBe('policy_ownership_mismatch');
    expect(persistence.getNodes()[0]).toMatchObject({ administrativeState: 'draining', version: 2 });
  });

  it.each([
    ['inconclusive', 'inconclusive'],
    ['recommend_active', 'disabled_node'],
  ] as const)('does not transition %s evidence from protected state', (recommendation, disposition) => {
    const value = node(`node-${recommendation}`, recommendation === 'recommend_active' ? 'disabled' : 'active');
    const evidence = evaluation(value, recommendation);
    persist(value, evidence);
    expect(policy.apply(request(value, evidence), event(value.id)).disposition).toBe(disposition);
    expect(persistence.getNodes()[0]).toMatchObject({ administrativeState: value.administrativeState, version: 1 });
  });

  it('records stale, fingerprint, node, superseded, and state/version rejection dispositions', () => {
    const cases: Array<[string, (value: Node, evidence: WorkstationWorkloadEvaluation) => WorkstationAvailabilityPolicyApplicationRequest,
      WorkstationAvailabilityPolicyApplication['disposition']]> = [
      ['stale', (value, evidence) => ({ ...request(value, evidence, 1, 'active', 'app-stale'), maximumEvidenceAgeMs: 1 }), 'stale_evidence'],
      ['fingerprint', (value, evidence) => ({ ...request(value, evidence, 1, 'active', 'app-fingerprint'), expectedRuleFingerprint: 'b'.repeat(64) }), 'rule_fingerprint_mismatch'],
      ['version', (value, evidence) => request(value, evidence, 2, 'active', 'app-version'), 'state_version_mismatch'],
    ];
    for (const [name, makeRequest, expected] of cases) {
      const value = node(`node-${name}`);
      const evidence = evaluation(value, 'recommend_draining', `evaluation-${name}`);
      persist(value, evidence);
      expect(policy.apply(makeRequest(value, evidence), event(value.id)).disposition).toBe(expected);
    }
    const first = node('node-mismatch-a');
    const second = node('node-mismatch-b');
    persistence.registerNode(first, [], [event(first.id)]);
    persistence.registerNode(second, [], [event(second.id)]);
    const mismatched = evaluation(first, 'recommend_draining', 'evaluation-mismatch');
    persistence.recordWorkstationWorkloadEvaluation(mismatched, event(first.id));
    expect(policy.apply(request(second, mismatched, 1, 'active', 'app-mismatch'), event(second.id)).disposition).toBe('node_mismatch');

    const supersededNode = node('node-superseded');
    const old = evaluation(supersededNode, 'recommend_draining', 'evaluation-old');
    persist(supersededNode, old);
    persistence.recordWorkstationWorkloadEvaluation(evaluation(supersededNode, 'recommend_active', 'evaluation-new',
      '2026-08-13T20:00:30.000Z'), event(supersededNode.id));
    expect(policy.apply(request(supersededNode, old, 1, 'active', 'app-superseded'), event(supersededNode.id)).disposition)
      .toBe('superseded_evidence');
  });

  it('is idempotent without duplicate transitions and records already-satisfied no-change', () => {
    const value = node();
    const evidence = evaluation(value, 'recommend_draining');
    persist(value, evidence);
    const command = request(value, evidence);
    const first = policy.apply(command, event(value.id, 'application-event'));
    const second = policy.apply(command, event(value.id, 'unused-repeat-event'));
    expect(second).toEqual(first);
    expect(persistence.getNodes()[0]?.version).toBe(2);
    expect(persistence.getWorkstationAvailabilityPolicyApplications(value.id)).toHaveLength(1);

    const alreadyDraining = evaluation(value, 'recommend_draining', 'already-evaluation', '2026-08-13T20:00:30.000Z');
    persistence.recordWorkstationWorkloadEvaluation(alreadyDraining, event(value.id));
    const noChange = policy.apply(request({ ...value, administrativeState: 'draining' }, alreadyDraining, 2, 'draining',
      'already-application'), event(value.id));
    expect(noChange).toMatchObject({ disposition: 'already_satisfied', transitionOccurred: false, resultingNodeVersion: 2 });
  });

  it('rolls back application, transition, and state when Event persistence fails', () => {
    const value = node();
    const evidence = evaluation(value, 'recommend_draining');
    persist(value, evidence);
    persistence.appendEvent(event(value.id, 'duplicate-application-event'));
    expect(() => policy.apply(request(value, evidence), event(value.id, 'duplicate-application-event'))).toThrow();
    expect(persistence.getNodes()[0]).toMatchObject({ administrativeState: 'active', version: 1 });
    expect(persistence.getWorkstationAvailabilityPolicyApplications(value.id)).toEqual([]);
  });

  it('survives reopen and rejects direct mutation or corrupt reconstruction', () => {
    const value = node();
    const evidence = evaluation(value, 'recommend_draining');
    persist(value, evidence);
    const result = policy.apply(request(value, evidence), event(value.id));
    persistence.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    expect(persistence.getWorkstationAvailabilityPolicyApplications(value.id)).toEqual([result]);
    persistence.close();
    const direct = new DatabaseSync(databasePath);
    expect(() => direct.prepare(`UPDATE workstation_availability_policy_applications SET actor = 'changed' WHERE id = ?`)
      .run(result.id)).toThrow(/immutable/);
    direct.exec('DROP TRIGGER workstation_policy_applications_no_update');
    direct.prepare(`UPDATE workstation_availability_policy_applications SET resulting_node_version = 99 WHERE id = ?`).run(result.id);
    direct.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    expect(() => persistence.getWorkstationAvailabilityPolicyApplications(value.id))
      .toThrow(/Corrupt persisted Workstation Availability Policy Application/);
  });

  it('migrates populated schema 7 while preserving nodes and evaluations', () => {
    persistence.close();
    rmSync(databasePath, { force: true });
    const prior = new DatabaseSync(databasePath);
    prior.exec('PRAGMA foreign_keys = ON; CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, applied_at TEXT NOT NULL) STRICT');
    for (const migration of migrations.slice(0, 7)) {
      migration.up(prior);
      prior.prepare('INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)')
        .run(migration.version, migration.name, EVALUATED_AT);
    }
    prior.prepare(`INSERT INTO nodes (id, name, administrative_state, configuration_reference, created_at, version)
      VALUES ('schema7-node', 'Schema 7', 'active', 'config:schema7', ?, 4)`).run(EVALUATED_AT);
    prior.prepare(`INSERT INTO workstation_availability_evaluations
      (id, node_id, rule_fingerprint, process_basenames_json, matched_rule_ids_json, recommendation, evaluated_at)
      VALUES ('schema7-evaluation', 'schema7-node', ?, '[]', '[]', 'recommend_active', ?)`)
      .run(FINGERPRINT, EVALUATED_AT);
    prior.close();
    persistence = new SqliteArchitecture2Persistence({ databasePath });
    persistence.initialize();
    expect(persistence.getSchemaVersion()).toBe(11);
    expect(persistence.getNodes()[0]).toMatchObject({ id: 'schema7-node', version: 4 });
    expect(persistence.getWorkstationWorkloadEvaluations(asIdentifier<'Node'>('schema7-node'))[0]?.id).toBe('schema7-evaluation');
  });
});

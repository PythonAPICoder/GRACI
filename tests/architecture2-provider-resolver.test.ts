import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { asIdentifier, type AuditEventInput, type ProviderOfferingId } from '../src/architecture2/domain/index.js';
import { SqliteArchitecture2Persistence } from '../src/architecture2/persistence/index.js';
import { DeterministicProviderResolver } from '../src/architecture2/providers/index.js';

const NOW = '2026-08-13T20:00:00.000Z';

describe('Architecture 2 deterministic provider resolver', () => {
  let directory: string;
  let persistence: SqliteArchitecture2Persistence;
  let eventNumber = 0;
  const capabilityId = asIdentifier<'Capability'>('model.generate-text');

  const event = (aggregateId: string, eventType: string): AuditEventInput => ({
    id: asIdentifier<'Event'>(`resolver-event-${++eventNumber}`), aggregateType: 'provider-resolution', aggregateId,
    eventType, eventVersion: 1, actor: 'resolver-test', occurredAt: NOW, payload: {},
  });

  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'graci-resolver-'));
    persistence = new SqliteArchitecture2Persistence({ databasePath: join(directory, 'resolver.sqlite') });
    persistence.initialize();
    eventNumber = 0;
  });
  afterEach(() => { persistence.close(); rmSync(directory, { recursive: true, force: true }); });

  function register(offeringId: string, level: number, health: 'healthy' | 'unhealthy' = 'healthy',
    overrides: Record<string, unknown> = {}): ProviderOfferingId {
    const providerId = asIdentifier<'Provider'>(`provider-${offeringId}`);
    const id = asIdentifier<'ProviderOffering'>(offeringId);
    if (persistence.getCapabilities().length === 0) {
      persistence.registerProvider({ provider: { id: providerId, adapterType: 'test', adapterVersion: '1',
        configurationReference: `config:${offeringId}`, createdAt: NOW }, capabilities: [{ id: capabilityId,
        contractVersion: 1, description: 'Generate text', inputSchemaReference: 'in:1', outputSchemaReference: 'out:1', createdAt: NOW }],
        offerings: [{ id, providerId, capabilityId, contractVersion: 1, privacyDestinations: ['internal'],
          permissions: [], features: ['text'], supportedFormats: ['text/plain'], inputSchemaReference: 'in:1',
          outputSchemaReference: 'out:1', qualificationFingerprint: 'frozen', qualityLevel: 2,
          expectedLatencyMs: 100, maximumCost: 0, sideEffectClass: 'none', createdAt: NOW, ...overrides }] }, [event(providerId, 'provider.registered')]);
    } else {
      persistence.registerProvider({ provider: { id: providerId, adapterType: 'test', adapterVersion: '1',
        configurationReference: `config:${offeringId}`, createdAt: NOW }, capabilities: [], offerings: [{ id, providerId,
        capabilityId, contractVersion: 1, privacyDestinations: ['internal'], permissions: [], features: ['text'],
        supportedFormats: ['text/plain'], inputSchemaReference: 'in:1', outputSchemaReference: 'out:1',
        qualificationFingerprint: 'frozen', qualityLevel: 2, expectedLatencyMs: 100, maximumCost: 0,
        sideEffectClass: 'none', createdAt: NOW, ...overrides }] }, [event(providerId, 'provider.registered')]);
    }
    persistence.recordQualification({ id: asIdentifier<'Qualification'>(`qualification-${offeringId}`), offeringId: id,
      status: 'qualified', level, evidence: {}, qualifiedAt: NOW, triggerFingerprint: 'frozen' }, event(id, 'offering.qualified'));
    persistence.recordProviderHealth({ id: asIdentifier<'HealthObservation'>(`health-${offeringId}`), offeringId: id,
      status: health, evidence: {}, observedAt: NOW }, event(id, 'offering.health-observed'));
    return id;
  }

  function resolve(id: string, overrides: Record<string, unknown> = {}) {
    const resolver = new DeterministicProviderResolver(persistence, { nextEvent: (decision) => event(decision.request.id, 'provider.resolved') });
    return resolver.resolve({ id: asIdentifier<'ResolutionDecision'>(id), capabilityId, contractVersion: 1,
      privacyClass: 'internal', requiredPermissions: [], requiredFeatures: ['text'], minimumQualificationLevel: 1,
      maximumHealthAgeMs: 60_000, requestedAt: NOW, ...overrides });
  }

  it('selects deterministically by qualification then offering ID and reconstructs its decision', () => {
    register('offering-b', 2); register('offering-a', 2); register('offering-c', 1);
    const decision = resolve('resolution-1');
    expect(decision.selectedOfferingId).toBe('offering-a');
    expect(decision.candidates.map((value) => value.offeringId)).toEqual(['offering-a', 'offering-b', 'offering-c']);
    persistence.close(); persistence = new SqliteArchitecture2Persistence({ databasePath: join(directory, 'resolver.sqlite') }); persistence.initialize();
    expect(persistence.getProviderResolution(decision.request.id)).toEqual(decision);
  });

  it('fails closed with stable reasons when health is unacceptable', () => {
    register('offering-unhealthy', 2, 'unhealthy');
    const decision = resolve('resolution-2');
    expect(decision.selectedOfferingId).toBeUndefined();
    expect(decision.candidates[0]?.rejectionReasons).toEqual(['health_unacceptable']);
  });

  it('enforces schema, format, side-effect, quality, latency, cost, and qualification fingerprint constraints', () => {
    register('offering-constrained', 2, 'healthy', {
      supportedFormats: ['text/plain'], inputSchemaReference: 'in:1', outputSchemaReference: 'out:1',
      qualificationFingerprint: 'frozen', qualityLevel: 2, expectedLatencyMs: 100, maximumCost: 0,
      sideEffectClass: 'local',
    });
    const decision = resolve('resolution-constraints', {
      requiredFormats: ['application/json'], inputSchemaReference: 'in:2', outputSchemaReference: 'out:2',
      maximumSideEffectClass: 'none', expectedQualificationFingerprint: 'changed', minimumQualityLevel: 3,
      maximumLatencyMs: 50, maximumCost: -1,
    });
    expect(decision.selectedOfferingId).toBeUndefined();
    expect(decision.candidates[0]?.rejectionReasons).toEqual([
      'format_unsupported', 'input_schema_mismatch', 'output_schema_mismatch', 'side_effect_class_mismatch',
      'quality_insufficient', 'latency_exceeded', 'cost_exceeded', 'qualification_fingerprint_mismatch',
    ]);
  });

  it('fails closed when qualification or health evidence is missing', () => {
    const providerId = asIdentifier<'Provider'>('provider-unqualified');
    const offeringId = asIdentifier<'ProviderOffering'>('offering-unqualified');
    persistence.registerProvider({ provider: { id: providerId, adapterType: 'test', adapterVersion: '1',
      configurationReference: 'config:unqualified', createdAt: NOW }, capabilities: [{ id: capabilityId,
      contractVersion: 1, description: 'Generate text', inputSchemaReference: 'in:1', outputSchemaReference: 'out:1', createdAt: NOW }],
      offerings: [{ id: offeringId, providerId, capabilityId, contractVersion: 1, privacyDestinations: ['internal'],
        permissions: [], features: ['text'], supportedFormats: ['text/plain'], inputSchemaReference: 'in:1',
        outputSchemaReference: 'out:1', qualificationFingerprint: 'frozen', qualityLevel: 2,
        expectedLatencyMs: 100, maximumCost: 0, sideEffectClass: 'none', createdAt: NOW }] },
    [event(providerId, 'provider.registered')]);
    expect(resolve('resolution-missing').candidates[0]?.rejectionReasons).toEqual(['qualification_missing', 'health_missing']);
  });

  it('explicitly excludes the failed offering while preserving deterministic alternative ranking', () => {
    register('offering-b', 2); register('offering-a', 2); register('offering-c', 1);
    const decision = resolve('resolution-alternative', {
      excludedOfferingIds: [asIdentifier<'ProviderOffering'>('offering-a')],
    });
    expect(decision.selectedOfferingId).toBe('offering-b');
    expect(decision.candidates.find((candidate) => candidate.offeringId === 'offering-a'))
      .toMatchObject({ eligible: false, rejectionReasons: ['explicitly_excluded'] });
  });
});

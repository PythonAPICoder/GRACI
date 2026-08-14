import { describe, expect, it } from 'vitest';
import { asIdentifier, type Node, type NodeHealthObservation, type OfferingLocation,
  type ResourceLease, type ResourceSchedulingRequest } from '../src/architecture2/domain/index.js';
import { DeterministicResourceScheduler, type ResourceSchedulingRecords } from '../src/architecture2/resources/index.js';

const NOW = '2026-08-13T20:00:00.000Z';
const offeringId = asIdentifier<'ProviderOffering'>('offering-1');
const request: ResourceSchedulingRequest = { id: asIdentifier<'ResourceSchedulingDecision'>('schedule-1'), offeringId,
  privacyClass: 'internal', requiredCapacity: 2, maximumHealthAgeMs: 60_000, requestedAt: NOW };
const node = (id: string, administrativeState: Node['administrativeState'] = 'active'): Node => ({
  id: asIdentifier<'Node'>(id), name: id, administrativeState, configurationReference: `config:${id}`, createdAt: NOW,
});
const location = (id: string, nodeId: string, capacity = 4, enabled = true,
  privacyClasses: OfferingLocation['privacyClasses'] = ['internal']): OfferingLocation => ({
  id: asIdentifier<'OfferingLocation'>(id), nodeId: asIdentifier<'Node'>(nodeId), offeringId, enabled, capacity,
  privacyClasses, createdAt: NOW,
});
const health = (nodeId: string, status: NodeHealthObservation['status'] = 'healthy', observedAt = NOW): NodeHealthObservation => ({
  id: asIdentifier<'NodeHealthObservation'>(`health-${nodeId}-${observedAt.replace(/\W/g, '')}`),
  nodeId: asIdentifier<'Node'>(nodeId), status, observedAt,
});
const lease = (id: string, locationId: string, nodeId: string, capacity: number, status: ResourceLease['status'] = 'active',
  expiresAt = '2026-08-13T20:01:00.000Z'): ResourceLease => ({ id: asIdentifier<'ResourceLease'>(id),
  decisionId: request.id, offeringId, locationId: asIdentifier<'OfferingLocation'>(locationId),
  nodeId: asIdentifier<'Node'>(nodeId), capacity, status, acquiredAt: '2026-08-13T19:59:00.000Z', expiresAt });
const schedule = (records: ResourceSchedulingRecords, value = request) => new DeterministicResourceScheduler().schedule(value, records);

describe('Architecture 2 deterministic resource scheduler', () => {
  it('explicitly excludes failed Nodes and locations and selects a genuinely different binding', () => {
    const records = { nodes: [node('node-a'), node('node-b'), node('node-c')],
      locations: [location('location-a', 'node-a'), location('location-b', 'node-b'), location('location-c', 'node-c')],
      healthObservations: [health('node-a'), health('node-b'), health('node-c')], leases: [] };
    const decision = schedule(records, { ...request, excludedNodeIds: [asIdentifier<'Node'>('node-a')],
      excludedLocationIds: [asIdentifier<'OfferingLocation'>('location-b')] });
    expect(decision.selectedLocationId).toBe('location-c');
    expect(decision.candidates.map(({ locationId, rejectionReasons }) => ({ locationId, rejectionReasons }))).toEqual([
      { locationId: 'location-a', rejectionReasons: ['node_explicitly_excluded'] },
      { locationId: 'location-b', rejectionReasons: ['location_explicitly_excluded'] },
      { locationId: 'location-c', rejectionReasons: [] },
    ]);
  });
  it('ranks capacity, health time, node ID, and location ID in that order', () => {
    const records = { nodes: [node('node-b'), node('node-a')], locations: [location('location-b', 'node-b', 5),
      location('location-z', 'node-a', 5), location('location-a', 'node-a', 5)],
      healthObservations: [health('node-a'), health('node-b')], leases: [] };
    expect(schedule(records).selectedLocationId).toBe('location-a');
    records.locations[2] = location('location-a', 'node-a', 6);
    expect(schedule(records).selectedLocationId).toBe('location-a');
  });

  it('subtracts only active unexpired leases from capacity', () => {
    const records = { nodes: [node('node-a')], locations: [location('location-a', 'node-a', 5)],
      healthObservations: [health('node-a')], leases: [lease('lease-active', 'location-a', 'node-a', 3),
        lease('lease-released', 'location-a', 'node-a', 5, 'released'),
        lease('lease-expired', 'location-a', 'node-a', 5, 'active', NOW)] };
    expect(schedule(records).candidates[0]).toMatchObject({ eligible: true, availableCapacity: 2 });
  });

  it('returns stable comprehensive rejection reasons and no selection', () => {
    const records = { nodes: [node('node-a', 'draining')],
      locations: [location('location-a', 'node-a', 1, false, ['public'])],
      healthObservations: [health('node-a', 'degraded', '2026-08-13T19:58:00.000Z')], leases: [] };
    const decision = schedule(records);
    expect(decision.selectedLocationId).toBeUndefined();
    expect(decision.candidates[0]?.rejectionReasons).toEqual(['node_draining', 'location_disabled', 'health_stale',
      'health_unacceptable', 'privacy_incompatible', 'capacity_insufficient']);
  });

  it('distinguishes missing health, disabled node, and missing node', () => {
    const decision = schedule({ nodes: [node('node-a', 'disabled')], locations: [location('a', 'node-a'), location('b', 'node-b')],
      healthObservations: [], leases: [] });
    expect(decision.candidates.map((candidate) => candidate.rejectionReasons)).toEqual([
      ['node_disabled', 'health_missing'], ['node_missing', 'health_missing'],
    ]);
  });

  it('is identical across insertion permutations', () => {
    const base: ResourceSchedulingRecords = { nodes: [node('node-c'), node('node-a'), node('node-b')],
      locations: [location('c', 'node-c', 3), location('a', 'node-a', 4), location('b', 'node-b', 4)],
      healthObservations: [health('node-c'), health('node-a'), health('node-b')],
      leases: [lease('lease-a', 'a', 'node-a', 1)] };
    const first = schedule(base);
    const reversed = schedule({ nodes: [...base.nodes].reverse(), locations: [...base.locations].reverse(),
      healthObservations: [...base.healthObservations].reverse(), leases: [...base.leases].reverse() });
    expect(reversed).toEqual(first);
  });

  it.each([
    [{ requiredCapacity: Number.NaN }, 'requiredCapacity'], [{ requiredCapacity: 0 }, 'requiredCapacity'],
    [{ maximumHealthAgeMs: -1 }, 'maximumHealthAgeMs'], [{ requestedAt: 'not-a-time' }, 'requestedAt'],
  ])('rejects malformed request values explicitly', (overrides, label) => {
    expect(() => schedule({ nodes: [], locations: [], healthObservations: [], leases: [] }, { ...request, ...overrides }))
      .toThrow(`Invalid ${label}`);
  });
});

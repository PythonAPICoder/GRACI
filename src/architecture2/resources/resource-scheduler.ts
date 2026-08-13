import type {
  Node,
  NodeHealthObservation,
  OfferingLocation,
  ResourceLease,
  ResourceSchedulingCandidate,
  ResourceSchedulingDecision,
  ResourceSchedulingRejectionReason,
  ResourceSchedulingRequest,
} from '../domain/index.js';

export interface ResourceSchedulingRecords {
  nodes: readonly Node[];
  locations: readonly OfferingLocation[];
  healthObservations: readonly NodeHealthObservation[];
  leases: readonly ResourceLease[];
}

function timestamp(value: string, label: string): number {
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed) || !/(?:Z|[+-]\d{2}:\d{2})$/.test(value)) {
    throw new Error(`Invalid ${label}: ${JSON.stringify(value)}`);
  }
  return parsed;
}

function nonNegative(value: number, label: string): void {
  if (!Number.isFinite(value) || value < 0) throw new Error(`Invalid ${label}: ${String(value)}`);
}

export class DeterministicResourceScheduler {
  schedule(request: ResourceSchedulingRequest, records: ResourceSchedulingRecords): ResourceSchedulingDecision {
    nonNegative(request.requiredCapacity, 'requiredCapacity');
    nonNegative(request.maximumHealthAgeMs, 'maximumHealthAgeMs');
    const requestedAt = timestamp(request.requestedAt, 'requestedAt');
    if (request.requiredCapacity === 0) throw new Error('Invalid requiredCapacity: 0');

    const nodes = new Map(records.nodes.map((node) => [node.id, node]));
    const observations = new Map<string, NodeHealthObservation>();
    for (const observation of records.healthObservations) {
      const observedAt = timestamp(observation.observedAt, 'health observedAt');
      const current = observations.get(observation.nodeId);
      if (!current || observedAt > timestamp(current.observedAt, 'health observedAt') ||
          (observedAt === timestamp(current.observedAt, 'health observedAt') && observation.id.localeCompare(current.id) < 0)) {
        observations.set(observation.nodeId, observation);
      }
    }

    const usedCapacity = new Map<string, number>();
    for (const lease of records.leases) {
      nonNegative(lease.capacity, 'lease capacity');
      const expiresAt = timestamp(lease.expiresAt, 'lease expiresAt');
      timestamp(lease.acquiredAt, 'lease acquiredAt');
      if (lease.status === 'active' && expiresAt > requestedAt) {
        usedCapacity.set(lease.locationId, (usedCapacity.get(lease.locationId) ?? 0) + lease.capacity);
      }
    }

    const candidates = records.locations
      .filter((location) => location.offeringId === request.offeringId)
      .map((location): ResourceSchedulingCandidate => {
        nonNegative(location.capacity, 'location capacity');
        const node = nodes.get(location.nodeId);
        const health = observations.get(location.nodeId);
        const reasons: ResourceSchedulingRejectionReason[] = [];
        const availableCapacity = Math.max(0, location.capacity - (usedCapacity.get(location.id) ?? 0));
        if (!node) reasons.push('node_missing');
        else if (node.administrativeState === 'draining') reasons.push('node_draining');
        else if (node.administrativeState === 'disabled') reasons.push('node_disabled');
        if (!location.enabled) reasons.push('location_disabled');
        if (!health) reasons.push('health_missing');
        else {
          const observedAt = timestamp(health.observedAt, 'health observedAt');
          if (observedAt > requestedAt || requestedAt - observedAt > request.maximumHealthAgeMs) reasons.push('health_stale');
          if (health.status !== 'healthy') reasons.push('health_unacceptable');
        }
        if (!location.privacyClasses.includes(request.privacyClass)) reasons.push('privacy_incompatible');
        if (availableCapacity < request.requiredCapacity) reasons.push('capacity_insufficient');
        return { locationId: location.id, nodeId: location.nodeId, eligible: reasons.length === 0,
          rejectionReasons: reasons, availableCapacity, healthObservedAt: health?.observedAt };
      })
      .sort((left, right) => left.nodeId.localeCompare(right.nodeId) || left.locationId.localeCompare(right.locationId));

    const selected = candidates.filter((candidate) => candidate.eligible).sort((left, right) =>
      right.availableCapacity - left.availableCapacity ||
      timestamp(right.healthObservedAt!, 'health observedAt') - timestamp(left.healthObservedAt!, 'health observedAt') ||
      left.nodeId.localeCompare(right.nodeId) || left.locationId.localeCompare(right.locationId))[0];
    return { request, candidates, selectedLocationId: selected?.locationId, selectedNodeId: selected?.nodeId,
      explanation: selected ? `Selected location ${selected.locationId} on node ${selected.nodeId}.` : 'No eligible resource location.',
      decidedAt: request.requestedAt };
  }
}

import type {
  AuditEventInput, ProviderHealthObservation, ProviderOffering, ProviderResolutionCandidate,
  ProviderResolutionDecision, ProviderResolutionRequest, Qualification, ResolutionRejectionReason,
} from '../domain/index.js';
import type { Architecture2Persistence } from '../persistence/index.js';
import { circuitRoutingState } from '../workflow/circuit-breaker.js';

export interface ProviderResolverOptions {
  nextEvent: (decision: ProviderResolutionDecision) => AuditEventInput;
}

function latestQualification(values: Qualification[]): Qualification | undefined {
  return [...values].sort((a, b) => a.qualifiedAt.localeCompare(b.qualifiedAt) || String(a.id).localeCompare(String(b.id))).at(-1);
}

function latestHealth(values: ProviderHealthObservation[]): ProviderHealthObservation | undefined {
  return [...values].sort((a, b) => a.observedAt.localeCompare(b.observedAt) || String(a.id).localeCompare(String(b.id))).at(-1);
}

const sideEffectRank: Record<ProviderOffering['sideEffectClass'], number> = {
  none: 0, local: 1, external_reversible: 2, external_consequential: 3,
};

export class DeterministicProviderResolver {
  constructor(private readonly persistence: Architecture2Persistence, private readonly options: ProviderResolverOptions) {}

  resolve(request: ProviderResolutionRequest): ProviderResolutionDecision {
    const candidates = this.persistence.getProviderOfferings(request.capabilityId)
      .sort((a, b) => String(a.id).localeCompare(String(b.id))).map((offering) => this.evaluate(offering, request));
    const eligible = candidates.filter((candidate) => candidate.eligible)
      .sort((a, b) => (b.qualificationLevel ?? 0) - (a.qualificationLevel ?? 0)
        || String(a.offeringId).localeCompare(String(b.offeringId)));
    const selectedOfferingId = eligible[0]?.offeringId;
    const decision: ProviderResolutionDecision = { request, candidates, selectedOfferingId,
      explanation: selectedOfferingId ? `Selected ${selectedOfferingId} by qualification level then offering ID` : 'No eligible provider offering',
      decidedAt: request.requestedAt };
    this.persistence.recordProviderResolution(decision, this.options.nextEvent(decision));
    return decision;
  }

  private evaluate(offering: ProviderOffering, request: ProviderResolutionRequest): ProviderResolutionCandidate {
    const reasons: ResolutionRejectionReason[] = [];
    const circuit = this.persistence.getCircuits().find((value) =>
      value.targetType === 'provider_offering' && value.targetId === offering.id);
    const circuitState = circuitRoutingState(circuit, request.requestedAt);
    if (circuitState === 'open') reasons.push('circuit_open');
    if (circuitState === 'probe_required' && (!circuit || !request.circuitProbeId ||
        !this.persistence.getCircuitProbes(circuit.id).some((probe) =>
          probe.id === request.circuitProbeId && probe.status === 'active'))) reasons.push('circuit_probe_required');
    if (request.excludedOfferingIds?.includes(offering.id)) reasons.push('explicitly_excluded');
    if (offering.contractVersion !== request.contractVersion) reasons.push('contract_version_mismatch');
    if (!offering.privacyDestinations.includes(request.privacyClass)) reasons.push('privacy_destination_disallowed');
    if (request.requiredPermissions.some((value) => !offering.permissions.includes(value))) reasons.push('permission_missing');
    if (request.requiredFeatures.some((value) => !offering.features.includes(value))) reasons.push('feature_missing');
    if (request.requiredFormats?.some((value) => !offering.supportedFormats.includes(value))) reasons.push('format_unsupported');
    if (request.inputSchemaReference && offering.inputSchemaReference !== request.inputSchemaReference) reasons.push('input_schema_mismatch');
    if (request.outputSchemaReference && offering.outputSchemaReference !== request.outputSchemaReference) reasons.push('output_schema_mismatch');
    if (request.maximumSideEffectClass && sideEffectRank[offering.sideEffectClass] > sideEffectRank[request.maximumSideEffectClass]) {
      reasons.push('side_effect_class_mismatch');
    }
    if (request.minimumQualityLevel !== undefined && offering.qualityLevel < request.minimumQualityLevel) reasons.push('quality_insufficient');
    if (request.maximumLatencyMs !== undefined && offering.expectedLatencyMs > request.maximumLatencyMs) reasons.push('latency_exceeded');
    if (request.maximumCost !== undefined && offering.maximumCost > request.maximumCost) reasons.push('cost_exceeded');
    const qualification = latestQualification(this.persistence.getQualifications(offering.id));
    if (!qualification) reasons.push('qualification_missing');
    else {
      if (qualification.status === 'rejected') reasons.push('qualification_rejected');
      if (qualification.expiresAt && Date.parse(qualification.expiresAt) <= Date.parse(request.requestedAt)) reasons.push('qualification_expired');
      if (qualification.level < request.minimumQualificationLevel) reasons.push('qualification_insufficient');
      const expectedFingerprint = request.expectedQualificationFingerprint ?? offering.qualificationFingerprint;
      if (qualification.triggerFingerprint !== expectedFingerprint) reasons.push('qualification_fingerprint_mismatch');
    }
    const health = latestHealth(this.persistence.getProviderHealth(offering.id));
    if (!health) reasons.push('health_missing');
    else {
      if (Date.parse(request.requestedAt) - Date.parse(health.observedAt) > request.maximumHealthAgeMs) reasons.push('health_stale');
      if (health.status !== 'healthy') reasons.push('health_unacceptable');
    }
    return { offeringId: offering.id, eligible: reasons.length === 0, rejectionReasons: reasons,
      ...(qualification ? { qualificationLevel: qualification.level } : {}),
      ...(health ? { healthObservedAt: health.observedAt } : {}) };
  }
}

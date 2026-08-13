import type { AuditEventInput, WorkstationAvailabilityPolicyApplication,
  WorkstationAvailabilityPolicyApplicationRequest } from '../domain/index.js';
import type { Architecture2Persistence } from '../persistence/index.js';

export const WORKSTATION_AVAILABILITY_POLICY_ID = 'workstation-availability';
export const WORKSTATION_AVAILABILITY_POLICY_VERSION = 1;

export class WorkstationAvailabilityPolicy {
  constructor(private readonly persistence: Architecture2Persistence) {}

  apply(request: WorkstationAvailabilityPolicyApplicationRequest,
    event: AuditEventInput): WorkstationAvailabilityPolicyApplication {
    return this.persistence.applyWorkstationAvailabilityPolicy(request, event);
  }
}

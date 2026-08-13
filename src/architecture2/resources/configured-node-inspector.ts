import type { Node, NodeInspectionFailure, NodeInspectionObservation } from '../domain/index.js';
import type { NodeInspectionId } from '../domain/ids.js';
import type { ModelProvider, ModelProviderResult } from '../providers/index.js';

export interface ConfiguredNodeInspectionRequest {
  id: NodeInspectionId;
  inspectedAt: string;
}

function failure<T>(result: Exclude<ModelProviderResult<T>, { status: 'success' }>): NodeInspectionFailure {
  return {
    outcome: result.status,
    code: result.failure.code,
    summary: result.failure.summary,
    ...(result.failure.httpStatus === undefined ? {} : { httpStatus: result.failure.httpStatus }),
  };
}

export class ConfiguredNodeInspector {
  constructor(private readonly provider: ModelProvider, private readonly node: Node) {}

  async inspect(request: ConfiguredNodeInspectionRequest): Promise<NodeInspectionObservation> {
    const healthResult = await this.provider.inspectHealth();
    const inventoryResult = await this.provider.inspectInventory();

    const health = healthResult.status === 'success'
      ? { outcome: 'success' as const, version: healthResult.value.version }
      : failure(healthResult);
    const inventory = inventoryResult.status === 'success'
      ? {
          outcome: 'success' as const,
          items: inventoryResult.value.map((item) => ({ ...item })).sort((left, right) =>
            left.name.localeCompare(right.name) || (left.digest ?? '').localeCompare(right.digest ?? '')),
        }
      : failure(inventoryResult);

    return {
      id: request.id,
      nodeId: this.node.id,
      adapterId: this.provider.providerId,
      adapterVersion: this.provider.contractVersion,
      health,
      inventory,
      inspectedAt: request.inspectedAt,
    };
  }
}

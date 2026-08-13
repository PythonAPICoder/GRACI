import { describe, expect, it, vi } from 'vitest';
import { asIdentifier, type Node, type NodeInspectionObservation } from '../src/architecture2/domain/index.js';
import { MODEL_PROVIDER_CONTRACT_VERSION, type ModelProvider, type ModelProviderResult } from '../src/architecture2/providers/index.js';
import { ConfiguredNodeInspector } from '../src/architecture2/resources/index.js';

const inspectedAt = '2026-08-13T12:00:00.000Z';
const node: Node = {
  id: asIdentifier<'Node'>('node-1'), name: 'Configured node', administrativeState: 'active',
  configurationReference: 'config://ollama/secret-endpoint-token', createdAt: inspectedAt,
};

function provider(
  health: ModelProviderResult<{ version: string }>,
  inventory: ModelProviderResult<readonly { name: string; digest?: string; size?: number; modifiedAt?: string }[]>,
): ModelProvider {
  return {
    contractVersion: MODEL_PROVIDER_CONTRACT_VERSION,
    providerId: 'ollama',
    inspectHealth: vi.fn(async () => health),
    inspectInventory: vi.fn(async () => inventory),
    generate: vi.fn(),
  };
}

async function inspect(modelProvider: ModelProvider): Promise<NodeInspectionObservation> {
  return new ConfiguredNodeInspector(modelProvider, node).inspect({
    id: asIdentifier<'NodeInspection'>('inspection-1'), inspectedAt,
  });
}

describe('Architecture 2 configured node inspection', () => {
  it('captures successful health and canonical inventory without mutating the node', async () => {
    const before = structuredClone(node);
    const result = await inspect(provider(
      { status: 'success', value: { version: '0.11.4' } },
      { status: 'success', value: [{ name: 'qwen', digest: 'b', size: 42 }] },
    ));
    expect(result).toEqual({ id: 'inspection-1', nodeId: 'node-1', adapterId: 'ollama', adapterVersion: 1,
      health: { outcome: 'success', version: '0.11.4' },
      inventory: { outcome: 'success', items: [{ name: 'qwen', digest: 'b', size: 42 }] }, inspectedAt });
    expect(node).toEqual(before);
  });

  it('preserves a successful empty inventory', async () => {
    const result = await inspect(provider({ status: 'success', value: { version: '1' } }, { status: 'success', value: [] }));
    expect(result.inventory).toEqual({ outcome: 'success', items: [] });
  });

  it('orders every inventory permutation by name then digest', async () => {
    const items = [{ name: 'z', digest: 'a' }, { name: 'a', digest: 'z' }, { name: 'a', digest: 'a' }];
    const permutations = [items, [items[2], items[0], items[1]], [...items].reverse()];
    const outputs = await Promise.all(permutations.map((value) => inspect(provider(
      { status: 'success', value: { version: '1' } }, { status: 'success', value },
    ))));
    expect(outputs.map((output) => output.inventory)).toEqual(Array(3).fill({ outcome: 'success', items: [items[2], items[1], items[0]] }));
  });

  it('continues inventory inspection after health failure', async () => {
    const modelProvider = provider(
      { status: 'retryable_failure', failure: { code: 'timeout', summary: 'Timed out' } },
      { status: 'success', value: [{ name: 'available' }] },
    );
    const result = await inspect(modelProvider);
    expect(result.health).toEqual({ outcome: 'retryable_failure', code: 'timeout', summary: 'Timed out' });
    expect(result.inventory).toEqual({ outcome: 'success', items: [{ name: 'available' }] });
    expect(modelProvider.inspectInventory).toHaveBeenCalledOnce();
  });

  it('preserves inventory failure alongside successful health', async () => {
    const result = await inspect(provider(
      { status: 'success', value: { version: '1' } },
      { status: 'non_retryable_failure', failure: { code: 'http_404', summary: 'Not found', httpStatus: 404 } },
    ));
    expect(result.inventory).toEqual({ outcome: 'non_retryable_failure', code: 'http_404', summary: 'Not found', httpStatus: 404 });
  });

  it('does not leak node configuration, endpoints, or secrets into evidence', async () => {
    const result = await inspect(provider({ status: 'success', value: { version: '1' } }, { status: 'success', value: [] }));
    const serialized = JSON.stringify(result);
    expect(serialized).not.toContain(node.configurationReference);
    expect(serialized).not.toMatch(/endpoint|configurationReference|secret/i);
    expect(Object.keys(result)).toEqual(['id', 'nodeId', 'adapterId', 'adapterVersion', 'health', 'inventory', 'inspectedAt']);
  });
});

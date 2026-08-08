import { PersistentState, loadState } from '../core/state/store.js';

export interface NodeInfo {
  id: string;
  host: string;
  status: 'healthy' | 'unhealthy';
}

export class NodeRegistry {
  private nodes = new Map<string, NodeInfo>();

  register(node: NodeInfo) {
    this.nodes.set(node.id, node);
  }

  get(id: string): NodeInfo | undefined {
    return this.nodes.get(id);
  }

  list(): NodeInfo[] {
    return Array.from(this.nodes.values());
  }

  loadFromState() {
    const state = loadState();
    if (state.registeredNodes) {
      Object.entries(state.registeredNodes).forEach(([id, info]) => {
        const nodeInfo = info as { host: string };
        this.register({ id, host: nodeInfo.host, status: 'healthy' });
      });
    }
  }
}

export const nodeRegistry = new NodeRegistry();
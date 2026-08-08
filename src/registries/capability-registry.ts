import { PersistentState, loadState } from '../core/state/store.js';

export interface Capability {
  id: string;
  description?: string;
}

export class CapabilityRegistry {
  private capabilities = new Map<string, Capability>();

  register(cap: Capability) {
    this.capabilities.set(cap.id, cap);
  }

  get(id: string): Capability | undefined {
    return this.capabilities.get(id);
  }

  list(): Capability[] {
    return Array.from(this.capabilities.values());
  }

  loadFromState() {
    const state = loadState();
    if (state.registeredCapabilities) {
      Object.entries(state.registeredCapabilities).forEach(([id, desc]) => {
        this.register({ id, description: desc as string });
      });
    }
  }
}

export const capabilityRegistry = new CapabilityRegistry();
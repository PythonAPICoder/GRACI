import { PersistentState, loadState } from '../core/state/store.js';

export interface Model {
  name: string;
  description?: string;
}

export class ModelRegistry {
  private models = new Map<string, Model>();

  register(model: Model) {
    this.models.set(model.name, model);
  }

  get(name: string): Model | undefined {
    return this.models.get(name);
  }

  list(): Model[] {
    return Array.from(this.models.values());
  }

  loadFromState() {
    const state = loadState();
    if (state.registeredModels) {
      Object.entries(state.registeredModels).forEach(([name, desc]) => {
        this.register({ name, description: desc as string });
      });
    }
  }
}

export const modelRegistry = new ModelRegistry();
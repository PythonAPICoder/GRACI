import { PersistentState, loadState, saveState } from '../core/state/store.js';

export interface Tool {
  name: string;
  description?: string;
  execute: (input: any) => Promise<any>;
}

export class ToolRegistry {
  private tools = new Map<string, Tool>();

  register(tool: Tool) {
    this.tools.set(tool.name, tool);
  }

  get(name: string): Tool | undefined {
    return this.tools.get(name);
  }

  list(): Tool[] {
    return Array.from(this.tools.values());
  }

  loadFromState() {
    const state = loadState();
    if (state.registeredTools) {
      Object.entries(state.registeredTools).forEach(([name, desc]) => {
        this.register({ name, description: desc as string, execute: async () => ({}) });
      });
    }
  }
}

export const toolRegistry = new ToolRegistry();
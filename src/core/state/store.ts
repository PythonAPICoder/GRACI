import { join as pathJoin } from 'node:path';
import * as fs from 'node:fs';

export interface PersistentState {
  registeredTools?: Record<string, unknown>;
  registeredCapabilities?: Record<string, unknown>;
  registeredModels?: Record<string, unknown>;
  registeredNodes?: Record<string, unknown>;
  tasks?: Record<string, unknown>;
}

const STATES_FILE = pathJoin(process.cwd(), 'data', 'graci_state.json');
let stateCache: PersistentState | null = null;

export function loadState(): PersistentState {
  if (stateCache) return { ...stateCache };
  if (!fs.existsSync(STATES_FILE)) {
    stateCache = {};
    fs.writeFileSync(STATES_FILE, JSON.stringify(stateCache, null, 2));
  }
  try {
    const raw = fs.readFileSync(STATES_FILE, 'utf-8');
    stateCache = JSON.parse(raw) as PersistentState;
  } catch {
    stateCache = {};
  }
  return { ...stateCache };
}

export function saveState(updated: Partial<PersistentState>): void {
  const current = loadState();
  const newState = { ...current, ...updated } as PersistentState;
  fs.writeFileSync(STATES_FILE, JSON.stringify(newState, null, 2));
  stateCache = { ...newState };
}

export function getState<T extends keyof PersistentState>(key: T): PersistentState[T] {
  const current = loadState();
  return (current[key] || {}) as PersistentState[T];
}
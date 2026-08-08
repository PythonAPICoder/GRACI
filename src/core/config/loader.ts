import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { AppConfig, ConfigSource } from './types.js';
import { DEFAULTS } from './defaults.js';

let loadedConfig: AppConfig | null = null;
let configSource: ConfigSource = ConfigSource.Default;

export function loadConfig(): AppConfig {
  if (loadedConfig) return { ...loadedConfig };

  const userConfigPath = resolve(process.cwd(), 'config', 'graci.config.jsonc');
  let userConfig: AppConfigPatch | undefined;

  if (existsSync(userConfigPath)) {
    try {
      const raw = readFileSync(userConfigPath, 'utf-8');
      userConfig = stripAndParseJson(raw);
      configSource = ConfigSource.UserConfig;
    } catch {
      configSource = ConfigSource.Default;
    }
  }

  loadedConfig = mergeDefaults(DEFAULTS, userConfig);
  return { ...loadedConfig };
}

export function getConfig(): AppConfig {
  if (!loadedConfig) loadConfig();
  return { ...loadedConfig! };
}

function stripAndParseJson(raw: string): Partial<AppConfig> {
  const cleaned = raw
    .replace(/\/\/.*$/gm, '')
    .replace(/,\s*([}\]])/g, '$1');
  return JSON.parse(cleaned);
}

type AppConfigPatch = {
  [K in keyof AppConfig]?: Partial<AppConfig[K]>;
};

function mergeDefaults(def: AppConfig, patch?: AppConfigPatch): AppConfig {
  if (!patch) return { ...def };

  return {
    graci: {
      ...def.graci,
      ...(patch.graci ?? {}),
    },
    runtime: {
      ...def.runtime,
      ...(patch.runtime ?? {}),
    },
    ui: {
      ...def.ui,
      ...(patch.ui ?? {}),
    },
    ollama: {
      ...def.ollama,
      ...(patch.ollama ?? {}),
    },
    logging: {
      ...def.logging,
      ...(patch.logging ?? {}),
    },
    scheduler: {
      ...def.scheduler,
      ...(patch.scheduler ?? {}),
    },
  };
}

export function getConfigSource(): ConfigSource {
  return configSource;
}
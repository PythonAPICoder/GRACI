export interface AppConfig {
  graci: GraciInfo;
  runtime: RuntimeConfig;
  ui: UiConfig;
  ollama: OllamaConfig;
  logging: LoggingConfig;
  scheduler: SchedulerConfig;
}

export interface GraciInfo {
  version: string;
  name: string;
  full_name: string;
}

export interface RuntimeConfig {
  node_env: string;
  log_level: LogLevelValue;
  persistent_state_path: string;
}

export interface UiConfig {
  min_width: number;
  min_height: number;
  initial_width: number;
  initial_height: number;
  dark_mode: boolean;
}

export interface OllamaConfig {
  default_endpoint: string;
  default_model: string;
  discovery_port_range: [number, number];
  health_check_interval_ms: number;
  request_timeout_ms: number;
}

export interface LoggingConfig {
  max_file_size_mb: number;
  max_files: number;
  include_timestamps: boolean;
  console_output: boolean;
}

export interface SchedulerConfig {
  max_concurrent_tasks: number;
  task_timeout_ms: number;
  background_priority_threshold_cpu: number;
  background_priority_threshold_ram_percent: number;
}

export type LogLevelValue = 'debug' | 'info' | 'warn' | 'error';

export const DEFAULTS: ConfigDefaults = {
  graci: { version: '0.1.0', name: 'G.R.A.C.I.', full_name: 'General Reasoning, Automation, Coordination, and Intelligence' },
  runtime: { node_env: 'development', log_level: 'info', persistent_state_path: './data/graci_state.json' },
  ui: { min_width: 960, min_height: 640, initial_width: 1280, initial_height: 800, dark_mode: true },
  ollama: { default_endpoint: 'http://192.168.0.249:11434', default_model: 'gpt-oss:20b', discovery_port_range: [11430, 11440], health_check_interval_ms: 60000, request_timeout_ms: 120000 },
  logging: { max_file_size_mb: 10, max_files: 5, include_timestamps: true, console_output: true },
  scheduler: { max_concurrent_tasks: 4, task_timeout_ms: 300000, background_priority_threshold_cpu: 70, background_priority_threshold_ram_percent: 85 },
};

export enum ConfigSource {
  Default = 'default',
  UserConfig = 'user_config',
}

type ConfigDefaults = Required<AppConfig>;

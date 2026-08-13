import type { WindowsProcessSnapshot } from '../domain/index.js';

export const WINDOWS_PROCESS_SNAPSHOT_COMMAND = 'tasklist.exe';
export const WINDOWS_PROCESS_SNAPSHOT_ARGUMENTS = ['/FO', 'CSV', '/NH'] as const;

export interface WindowsProcessExecutorOptions {
  shell: false;
  timeout: number;
  maxBuffer: number;
}

export interface WindowsProcessExecutorResult {
  stdout: string;
  exitCode: number;
  truncated?: boolean;
}

export type WindowsProcessExecutor = (
  command: string,
  arguments_: readonly string[],
  options: WindowsProcessExecutorOptions,
) => Promise<WindowsProcessExecutorResult>;

export interface WindowsProcessSnapshotAdapterOptions {
  executor: WindowsProcessExecutor;
  timeoutMs: number;
  maximumOutputBytes: number;
  platform?: NodeJS.Platform;
}

function parseCsvRow(row: string): string[] | undefined {
  const fields: string[] = [];
  let field = '';
  let quoted = false;
  for (let index = 0; index < row.length; index += 1) {
    const character = row[index];
    if (quoted) {
      if (character === '"' && row[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (character === '"') {
        quoted = false;
      } else {
        field += character;
      }
    } else if (character === '"' && field.length === 0) {
      quoted = true;
    } else if (character === ',') {
      fields.push(field);
      field = '';
    } else {
      return undefined;
    }
  }
  if (quoted) return undefined;
  fields.push(field);
  return fields;
}

function normalizedBasenames(output: string): readonly string[] | undefined {
  if (output.trim().length === 0) return [];
  const basenames = new Set<string>();
  for (const row of output.split(/\r?\n/).filter((value) => value.length > 0)) {
    const fields = parseCsvRow(row);
    if (!fields || fields.length !== 5 || !/^\d+$/.test(fields[1]) || !/^\d+$/.test(fields[3])) return undefined;
    const basename = fields[0].toLocaleLowerCase('en-US');
    if (!basename || basename !== basename.trim() || /[\\/\x00-\x1f]/.test(basename)) return undefined;
    basenames.add(basename);
  }
  return [...basenames].sort((left, right) => left.localeCompare(right, 'en-US'));
}

export class WindowsProcessSnapshotAdapter {
  constructor(private readonly options: WindowsProcessSnapshotAdapterOptions) {
    if (!Number.isInteger(options.timeoutMs) || options.timeoutMs <= 0) throw new Error('timeoutMs must be a positive integer');
    if (!Number.isInteger(options.maximumOutputBytes) || options.maximumOutputBytes <= 0) {
      throw new Error('maximumOutputBytes must be a positive integer');
    }
  }

  async capture(capturedAt: string): Promise<WindowsProcessSnapshot> {
    if ((this.options.platform ?? process.platform) !== 'win32') {
      return { completeness: 'incomplete', processBasenames: [], reason: 'unsupported_platform', capturedAt };
    }
    try {
      const result = await this.options.executor(WINDOWS_PROCESS_SNAPSHOT_COMMAND, WINDOWS_PROCESS_SNAPSHOT_ARGUMENTS, {
        shell: false,
        timeout: this.options.timeoutMs,
        maxBuffer: this.options.maximumOutputBytes,
      });
      if (result.truncated || Buffer.byteLength(result.stdout, 'utf8') > this.options.maximumOutputBytes) {
        return { completeness: 'incomplete', processBasenames: [], reason: 'truncated_output', capturedAt };
      }
      if (result.exitCode !== 0) {
        return { completeness: 'incomplete', processBasenames: [], reason: 'execution_failed', capturedAt };
      }
      const processBasenames = normalizedBasenames(result.stdout);
      return processBasenames === undefined
        ? { completeness: 'incomplete', processBasenames: [], reason: 'malformed_output', capturedAt }
        : { completeness: 'complete', processBasenames, capturedAt };
    } catch {
      return { completeness: 'incomplete', processBasenames: [], reason: 'execution_failed', capturedAt };
    }
  }
}

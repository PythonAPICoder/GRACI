import { describe, expect, it, vi } from 'vitest';
import { asIdentifier, type Node, type WorkstationWorkloadRules } from '../src/architecture2/domain/index.js';
import {
  WINDOWS_PROCESS_SNAPSHOT_ARGUMENTS,
  WINDOWS_PROCESS_SNAPSHOT_COMMAND,
  WindowsProcessSnapshotAdapter,
  evaluateWorkstationWorkload,
  type WindowsProcessExecutor,
} from '../src/architecture2/resources/index.js';

const time = '2026-08-13T12:00:00.000Z';
const node: Node = { id: asIdentifier<'Node'>('node-1'), name: 'Workstation', administrativeState: 'active',
  configurationReference: 'config://secret-token', createdAt: time };
const rules: WorkstationWorkloadRules = { version: 3, rules: [
  { id: 'mo2', executableBasenames: ['ModOrganizer.exe', 'ModOrganizer2.exe'] },
  { id: 'configured-game', executableBasenames: ['SkyrimSE.exe'] },
] };
const csv = (name: string, pid = 1) => `"${name}","${pid}","Console","1","10,000 K"`;

function adapter(result: Awaited<ReturnType<WindowsProcessExecutor>>, platform: NodeJS.Platform = 'win32', executor?: WindowsProcessExecutor) {
  const execute = executor ?? vi.fn(async () => result);
  return { capture: new WindowsProcessSnapshotAdapter({ executor: execute, timeoutMs: 2500, maximumOutputBytes: 4096, platform }), execute };
}

function evaluate(snapshot: Awaited<ReturnType<WindowsProcessSnapshotAdapter['capture']>>, suppliedRules = rules) {
  return evaluateWorkstationWorkload(node, suppliedRules, snapshot, {
    id: asIdentifier<'WorkstationWorkloadEvaluation'>('evaluation-1'), evaluatedAt: time,
  });
}

describe('Architecture 2 workstation workload evaluation', () => {
  it('uses the fixed bounded shell-free Windows invocation and parses sanitized basenames', async () => {
    const { capture, execute } = adapter({ stdout: `${csv('node.exe')}\r\n${csv('SKYRIMSE.EXE', 2)}\r\n`, exitCode: 0 });
    const snapshot = await capture.capture(time);
    expect(execute).toHaveBeenCalledWith(WINDOWS_PROCESS_SNAPSHOT_COMMAND, WINDOWS_PROCESS_SNAPSHOT_ARGUMENTS,
      { shell: false, timeout: 2500, maxBuffer: 4096 });
    expect(snapshot).toEqual({ completeness: 'complete', processBasenames: ['node.exe', 'skyrimse.exe'], capturedAt: time });
    expect(evaluate(snapshot).recommendation).toBe('recommend_draining');
  });

  it('treats a complete empty snapshot as active', async () => {
    const snapshot = await adapter({ stdout: '', exitCode: 0 }).capture.capture(time);
    expect(evaluate(snapshot).recommendation).toBe('recommend_active');
  });

  it.each([
    ['failure', { stdout: 'secret command line', exitCode: 1 }, 'execution_failed'],
    ['malformed', { stdout: 'secret --token=hunter2', exitCode: 0 }, 'malformed_output'],
    ['truncated flag', { stdout: csv('node.exe'), exitCode: 0, truncated: true }, 'truncated_output'],
    ['output bound', { stdout: 'x'.repeat(4097), exitCode: 0 }, 'truncated_output'],
  ] as const)('makes %s output incomplete and evaluation inconclusive', async (_label, result, reason) => {
    const snapshot = await adapter(result).capture.capture(time);
    expect(snapshot).toEqual({ completeness: 'incomplete', processBasenames: [], reason, capturedAt: time });
    expect(evaluate(snapshot).recommendation).toBe('inconclusive');
    expect(JSON.stringify(evaluate(snapshot))).not.toMatch(/hunter2|command line|secret-token/i);
  });

  it('makes executor exceptions and unsupported platforms incomplete', async () => {
    const rejecting = vi.fn(async () => { throw new Error('secret --password value'); });
    const failed = await adapter({ stdout: '', exitCode: 0 }, 'win32', rejecting).capture.capture(time);
    const unsupported = await adapter({ stdout: '', exitCode: 0 }, 'linux').capture.capture(time);
    expect(failed.completeness === 'incomplete' && failed.reason).toBe('execution_failed');
    expect(unsupported.completeness === 'incomplete' && unsupported.reason).toBe('unsupported_platform');
    expect(rejecting).toHaveBeenCalledOnce();
  });

  it.each(['ModOrganizer.exe', 'MODORGANIZER2.EXE'])('matches caller-supplied MO2 alias %s exactly', async (name) => {
    const snapshot = await adapter({ stdout: csv(name), exitCode: 0 }).capture.capture(time);
    expect(evaluate(snapshot).matchedRuleIds).toEqual(['mo2']);
  });

  it('matches a configured game but not a fuzzy basename', async () => {
    const exact = await adapter({ stdout: csv('skyrimse.exe'), exitCode: 0 }).capture.capture(time);
    const fuzzy = await adapter({ stdout: csv('my-skyrimse.exe'), exitCode: 0 }).capture.capture(time);
    expect(evaluate(exact).matchedRuleIds).toEqual(['configured-game']);
    expect(evaluate(fuzzy).matchedRuleIds).toEqual([]);
  });

  it('is deterministic across process, rule, alias, and duplicate permutations without mutation', async () => {
    const processRows = [csv('SkyrimSE.exe', 3), csv('node.exe', 1), csv('MODORGANIZER.EXE', 2), csv('node.exe', 4)];
    const permutedRules = { version: 3, rules: [
      { id: 'configured-game', executableBasenames: ['skyrimse.exe'] },
      { id: 'mo2', executableBasenames: ['modorganizer2.exe', 'modorganizer.exe'] },
    ] } satisfies WorkstationWorkloadRules;
    const before = structuredClone({ node, rules, permutedRules });
    const first = evaluate(await adapter({ stdout: processRows.join('\n'), exitCode: 0 }).capture.capture(time), rules);
    const second = evaluate(await adapter({ stdout: [...processRows].reverse().join('\r\n'), exitCode: 0 }).capture.capture(time), permutedRules);
    expect(second).toEqual(first);
    expect(first.processBasenames).toEqual(['modorganizer.exe', 'node.exe', 'skyrimse.exe']);
    expect(first.matchedRuleIds).toEqual(['configured-game', 'mo2']);
    expect({ node, rules, permutedRules }).toEqual(before);
    expect(Object.keys(first)).toEqual(['id', 'nodeId', 'ruleFingerprint', 'processBasenames', 'matchedRuleIds', 'recommendation', 'evaluatedAt']);
  });
});

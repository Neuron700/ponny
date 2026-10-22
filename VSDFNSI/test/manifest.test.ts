import { existsSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { createDefaultRegistry } from '../src/engine/registry';
import { groupFindings } from '../src/providers/grouping';
import type { Finding } from '../src/models/types';

const root = process.cwd();
const pkg = JSON.parse(readFileSync(`${root}/package.json`, 'utf8')) as {
  main: string;
  engines: { vscode: string };
  capabilities: { untrustedWorkspaces: { supported: boolean } };
  contributes: {
    commands: { command: string }[];
    configuration: { properties: Record<string, { default: unknown }> };
    viewsContainers: { activitybar: { id: string }[] };
    views: Record<string, { id: string }[]>;
  };
};

describe('extension manifest', () => {
  it('declares the extension entry point and VS Code engine', () => {
    expect(pkg.main).toBe('./out/extension.js');
    expect(pkg.engines.vscode).toMatch(/^\^1\./);
  });

  it('contributes every required command', () => {
    const commands = pkg.contributes.commands.map((entry) => entry.command);
    for (const required of [
      'repoguard.scanWorkspace',
      'repoguard.scanCurrentFile',
      'repoguard.refresh',
      'repoguard.clear',
      'repoguard.manageIgnored',
      'repoguard.exportReport',
    ]) {
      expect(commands).toContain(required);
    }
  });

  it('wires every contributed command to the command registration module', () => {
    const source = readFileSync(`${root}/src/commands/index.ts`, 'utf8');
    for (const { command } of pkg.contributes.commands) {
      expect(source).toContain(`'${command}'`);
    }
  });

  it('contributes the findings view in the activity bar', () => {
    expect(
      pkg.contributes.viewsContainers.activitybar.some((view) => view.id === 'repoguard'),
    ).toBe(true);
    expect(pkg.contributes.views.repoguard.some((view) => view.id === 'repoguard.findings')).toBe(
      true,
    );
    expect(existsSync(`${root}/media/shield.svg`)).toBe(true);
  });

  it('provides conservative documented settings', () => {
    const properties = pkg.contributes.configuration.properties;
    for (const key of [
      'repoguard.scanOnSave',
      'repoguard.includeExtensions',
      'repoguard.excludePatterns',
      'repoguard.maxFileSizeKb',
      'repoguard.enabledRules',
      'repoguard.disabledRules',
    ]) {
      expect(properties[key]).toBeDefined();
    }
    expect(properties['repoguard.scanOnSave'].default).toBe(false);
    expect(properties['repoguard.maxFileSizeKb'].default).toBe(512);
  });

  it('disables activation in untrusted workspaces', () => {
    expect(pkg.capabilities.untrustedWorkspaces.supported).toBe(false);
  });

  it('registers all initial rules with unique IDs', () => {
    const registry = createDefaultRegistry();
    expect(registry.all().map((rule) => rule.id)).toEqual([
      'RG001',
      'RG002',
      'RG003',
      'RG004',
      'RG005',
      'RG006',
      'RG007',
    ]);
  });
});

function finding(overrides: Partial<Finding>): Finding {
  return {
    id: 'id',
    ruleId: 'RG001',
    ruleTitle: 'Title',
    severity: 'high',
    message: 'message',
    explanation: 'explanation',
    whyRisky: 'risk',
    remediation: 'remediation',
    limitations: 'limitations',
    references: [],
    relativePath: 'src/app.js',
    absolutePath: 'C:/src/app.js',
    workspaceFolder: 'fixture',
    fileName: 'app.js',
    line: 1,
    column: 1,
    endLine: 1,
    endColumn: 2,
    fingerprint: 'fp',
    maskedSnippet: '',
    ...overrides,
  };
}

describe('findings grouping', () => {
  const findings = [
    finding({ id: '1', ruleId: 'RG001', severity: 'high', relativePath: 'src/a.js' }),
    finding({ id: '2', ruleId: 'RG004', severity: 'high', relativePath: 'src/b.py' }),
    finding({ id: '3', ruleId: 'RG006', severity: 'medium', relativePath: 'src/a.js' }),
  ];

  it('groups by severity in severity order', () => {
    const groups = groupFindings(findings, 'severity');
    expect(groups.map((group) => group.label)).toEqual(['High', 'Medium']);
    expect(groups[0].findings).toHaveLength(2);
  });

  it('groups by file in path order', () => {
    const groups = groupFindings(findings, 'file');
    expect(groups.map((group) => group.label)).toEqual(['src/a.js', 'src/b.py']);
    expect(groups[0].findings).toHaveLength(2);
  });

  it('returns no groups for empty findings', () => {
    expect(groupFindings([], 'severity')).toEqual([]);
    expect(groupFindings([], 'file')).toEqual([]);
  });
});

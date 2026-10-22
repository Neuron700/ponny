import { readFileSync } from 'node:fs';
import path from 'node:path';
import type { FileCandidate, Finding, RuleFileInfo, ScannerSettings } from '../src/models/types';
import { evaluateContent } from '../src/engine/ruleEngine';
import { createDefaultRegistry, type RuleRegistry } from '../src/engine/registry';
import { DEFAULT_EXCLUDE_PATTERNS, DEFAULT_INCLUDE_EXTENSIONS } from '../src/config/defaults';
import { extensionOf, fileNameOf } from '../src/utils/paths';

export const FIXTURES = path.resolve(process.cwd(), 'test', 'fixtures');

export function readFixture(relativePath: string): string {
  return readFileSync(path.join(FIXTURES, relativePath), 'utf8');
}

export function fixturePath(relativePath: string): string {
  return path.join(FIXTURES, relativePath);
}

export function makeSettings(overrides: Partial<ScannerSettings> = {}): ScannerSettings {
  return {
    includeExtensions: [...DEFAULT_INCLUDE_EXTENSIONS],
    excludePatterns: [...DEFAULT_EXCLUDE_PATTERNS],
    maxFileSizeBytes: 512 * 1024,
    enabledRules: [],
    disabledRules: [],
    scanOnSave: false,
    ...overrides,
  };
}

export function makeFileInfo(relativePath: string, workspaceFolder = 'fixture'): RuleFileInfo {
  const absolutePath = path.join(FIXTURES, ...relativePath.split('/'));
  return {
    absolutePath,
    relativePath,
    workspaceFolder,
    fileName: fileNameOf(relativePath),
    extension: extensionOf(fileNameOf(relativePath)),
  };
}

export interface EvaluateFixtureOptions {
  settings?: ScannerSettings;
  rootFileContents?: Record<string, string | undefined>;
  registry?: RuleRegistry;
}

export function evaluateFixture(
  relativePath: string,
  options: EvaluateFixtureOptions = {},
): Finding[] {
  const content = readFixture(relativePath);
  return evaluateContent(
    makeFileInfo(relativePath),
    content,
    options.registry ?? createDefaultRegistry(),
    {
      settings: options.settings ?? makeSettings(),
      rootFileContents: options.rootFileContents ?? {},
    },
  );
}

export function evaluateContentAs(
  relativePath: string,
  content: string,
  options: EvaluateFixtureOptions = {},
): Finding[] {
  return evaluateContent(
    makeFileInfo(relativePath),
    content,
    options.registry ?? createDefaultRegistry(),
    {
      settings: options.settings ?? makeSettings(),
      rootFileContents: options.rootFileContents ?? {},
    },
  );
}

export function byRule(findings: readonly Finding[], ruleId: string): Finding[] {
  return findings.filter((finding) => finding.ruleId === ruleId);
}

export function makeCandidate(
  relativePath: string,
  sizeBytes: number,
  workspaceFolder = 'fixture',
): FileCandidate {
  const fileName = fileNameOf(relativePath);
  return {
    absolutePath: `C:/fixture/${relativePath}`,
    relativePath,
    workspaceFolder,
    fileName,
    extension: extensionOf(fileName),
    sizeBytes,
  };
}

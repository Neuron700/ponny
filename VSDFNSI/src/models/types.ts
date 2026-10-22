import type { Severity } from './severity';

export type { Severity } from './severity';

export interface RuleFileInfo {
  absolutePath: string;
  relativePath: string;
  workspaceFolder: string;
  fileName: string;
  extension: string;
}

export interface RuleContext {
  file: RuleFileInfo;
  content: string;
  lines: readonly string[];
  rootFileContents: Readonly<Record<string, string | undefined>>;
}

export interface RuleMatch {
  line: number;
  column: number;
  endLine?: number;
  endColumn?: number;
  message: string;
  fingerprintSeed: string;
  snippet?: string;
}

export interface RuleDefinition {
  id: string;
  title: string;
  severity: Severity;
  explanation: string;
  whyRisky: string;
  remediation: string;
  limitations: string;
  references?: readonly string[];
  fileExtensions: readonly string[] | '*';
  scanEnvFiles?: boolean;
  fileNamePattern?: RegExp;
  detect: (context: RuleContext) => RuleMatch[];
}

export interface Finding {
  id: string;
  ruleId: string;
  ruleTitle: string;
  severity: Severity;
  message: string;
  explanation: string;
  whyRisky: string;
  remediation: string;
  limitations: string;
  references: readonly string[];
  relativePath: string;
  absolutePath: string;
  workspaceFolder: string;
  fileName: string;
  line: number;
  column: number;
  endLine: number;
  endColumn: number;
  fingerprint: string;
  maskedSnippet: string;
}

export interface ScannerSettings {
  includeExtensions: readonly string[];
  excludePatterns: readonly string[];
  maxFileSizeBytes: number;
  enabledRules: readonly string[];
  disabledRules: readonly string[];
  scanOnSave: boolean;
}

export interface FileCandidate {
  absolutePath: string;
  relativePath: string;
  workspaceFolder: string;
  fileName: string;
  extension: string;
  sizeBytes: number;
}

export interface ReadResult {
  ok: boolean;
  content?: string;
  reason?: 'too-large' | 'binary' | 'unreadable' | 'empty';
  detail?: string;
}

export interface ScanError {
  relativePath: string;
  reason: 'too-large' | 'binary' | 'unreadable' | 'empty';
}

export interface ScanResult {
  startedAt: string;
  finishedAt: string;
  findings: Finding[];
  filesScanned: number;
  filesSkipped: number;
  skipped: ScanError[];
  errors: number;
  cancelled: boolean;
  workspaceFolders: string[];
  settings: ScannerSettings;
}

export interface IgnoredFinding {
  ruleId: string;
  ruleTitle: string;
  severity: Severity;
  relativePath: string;
  fingerprint: string;
  maskedSnippet: string;
  ignoredAt: string;
}

export interface IgnoreRecordFile {
  version: 1;
  items: IgnoredFinding[];
}

export interface ScanGroupMeta {
  scope: 'workspace' | 'file';
  filePath?: string;
}

export interface SeverityFilter {
  severity: Severity | 'all';
}

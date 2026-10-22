import type { Finding, ScanResult, Severity } from '../models/types';
import { SEVERITY_ORDER } from '../models/severity';
import { redactSecrets } from '../utils/masking';

export interface ReportFinding {
  ruleId: string;
  ruleTitle: string;
  severity: Severity;
  message: string;
  explanation: string;
  whyRisky: string;
  remediation: string;
  limitations: string;
  references: string[];
  relativePath: string;
  workspaceFolder: string;
  line: number;
  column: number;
  endLine: number;
  endColumn: number;
  fingerprint: string;
  ignored: boolean;
}

export interface RepoGuardReport {
  schemaVersion: 1;
  tool: {
    name: 'RepoGuard';
    version: string;
  };
  generatedAt: string;
  workspace: {
    label: string;
    folders: string[];
  };
  scan: {
    startedAt: string | null;
    finishedAt: string | null;
    cancelled: boolean;
    filesScanned: number;
    filesSkipped: number;
    errors: number;
    rulesEnabled: readonly string[];
    rulesDisabled: readonly string[];
    maxFileSizeBytes: number;
  };
  summary: {
    total: number;
    active: number;
    ignored: number;
    bySeverity: Record<Severity, number>;
    byRule: Record<string, number>;
  };
  findings: ReportFinding[];
}

export interface ReportInput {
  toolVersion: string;
  workspaceLabel: string;
  workspaceFolders: readonly string[];
  findings: readonly Finding[];
  ignoredIds?: ReadonlySet<string>;
  scan?: ScanResult | null;
  generatedAt?: Date;
}

function bySeverityMap(): Record<Severity, number> {
  return { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
}

export function buildReport(input: ReportInput): RepoGuardReport {
  const generatedAt = input.generatedAt ?? new Date();
  const ignoredIds = input.ignoredIds ?? new Set<string>();
  const findings: ReportFinding[] = [];
  const bySeverity = bySeverityMap();
  const byRule: Record<string, number> = {};
  let ignoredCount = 0;

  for (const finding of input.findings) {
    const ignored = ignoredIds.has(finding.id);
    if (ignored) {
      ignoredCount += 1;
    } else {
      bySeverity[finding.severity] += 1;
    }
    byRule[finding.ruleId] = (byRule[finding.ruleId] ?? 0) + 1;

    findings.push({
      ruleId: finding.ruleId,
      ruleTitle: redactSecrets(finding.ruleTitle),
      severity: finding.severity,
      message: redactSecrets(finding.message),
      explanation: redactSecrets(finding.explanation),
      whyRisky: redactSecrets(finding.whyRisky),
      remediation: redactSecrets(finding.remediation),
      limitations: redactSecrets(finding.limitations),
      references: finding.references.map((reference) => redactSecrets(reference)),
      relativePath: finding.relativePath,
      workspaceFolder: finding.workspaceFolder,
      line: finding.line,
      column: finding.column,
      endLine: finding.endLine,
      endColumn: finding.endColumn,
      fingerprint: finding.fingerprint,
      ignored,
    });
  }

  findings.sort((a, b) => {
    const severityDelta = SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity);
    if (severityDelta !== 0) {
      return severityDelta;
    }
    const pathDelta = a.relativePath.localeCompare(b.relativePath);
    if (pathDelta !== 0) {
      return pathDelta;
    }
    return a.line - b.line;
  });

  const scan = input.scan;
  return {
    schemaVersion: 1,
    tool: {
      name: 'RepoGuard',
      version: input.toolVersion,
    },
    generatedAt: generatedAt.toISOString(),
    workspace: {
      label: input.workspaceLabel,
      folders: [...input.workspaceFolders],
    },
    scan: {
      startedAt: scan?.startedAt ?? null,
      finishedAt: scan?.finishedAt ?? null,
      cancelled: scan?.cancelled ?? false,
      filesScanned: scan?.filesScanned ?? 0,
      filesSkipped: scan?.filesSkipped ?? 0,
      errors: scan?.errors ?? 0,
      rulesEnabled: scan?.settings.enabledRules ?? [],
      rulesDisabled: scan?.settings.disabledRules ?? [],
      maxFileSizeBytes: scan?.settings.maxFileSizeBytes ?? 0,
    },
    summary: {
      total: input.findings.length,
      active: input.findings.length - ignoredCount,
      ignored: ignoredCount,
      bySeverity,
      byRule,
    },
    findings,
  };
}

export function serializeReport(report: RepoGuardReport): string {
  return `${JSON.stringify(report, null, 2)}\n`;
}

export function defaultReportFileName(date = new Date()): string {
  const stamp = date.toISOString().replace(/[:.]/g, '-').replace('T', '_').slice(0, 19);
  return `repoguard-report-${stamp}.json`;
}

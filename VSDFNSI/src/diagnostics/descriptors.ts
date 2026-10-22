import type { Finding, Severity } from '../models/types';
import { redactSecrets } from '../utils/masking';

export type DiagnosticSeverityName = 'error' | 'warning' | 'information' | 'hint';

export interface DiagnosticRange {
  startLine: number;
  startCharacter: number;
  endLine: number;
  endCharacter: number;
}

export interface DiagnosticDescriptor {
  ruleId: string;
  filePath: string;
  message: string;
  severity: DiagnosticSeverityName;
  source: string;
  code: string;
  range: DiagnosticRange;
}

export function severityToDiagnosticName(severity: Severity): DiagnosticSeverityName {
  switch (severity) {
    case 'critical':
    case 'high':
      return 'error';
    case 'medium':
      return 'warning';
    case 'low':
      return 'information';
    case 'info':
    default:
      return 'hint';
  }
}

export function findingToRange(finding: Finding): DiagnosticRange {
  const startLine = Math.max(0, finding.line - 1);
  const startCharacter = Math.max(0, finding.column - 1);
  const endLine = Math.max(startLine, finding.endLine - 1);
  const computedEnd = Math.max(0, finding.endColumn - 1);

  return {
    startLine,
    startCharacter,
    endLine,
    endCharacter: endLine === startLine ? Math.max(startCharacter + 1, computedEnd) : computedEnd,
  };
}

export function toDiagnosticDescriptor(finding: Finding): DiagnosticDescriptor {
  return {
    ruleId: finding.ruleId,
    filePath: finding.absolutePath,
    message: `${finding.ruleId}: ${redactSecrets(finding.message)}`,
    severity: severityToDiagnosticName(finding.severity),
    source: 'RepoGuard',
    code: finding.ruleId,
    range: findingToRange(finding),
  };
}

export function buildDiagnosticDescriptors(findings: readonly Finding[]): DiagnosticDescriptor[] {
  return findings.map(toDiagnosticDescriptor);
}

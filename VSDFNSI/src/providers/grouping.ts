import type { Finding, Severity } from '../models/types';
import { SEVERITY_LABELS, SEVERITY_ORDER } from '../models/severity';
import type { GroupBy } from '../state/findingsStore';

export interface FindingGroup {
  key: string;
  label: string;
  severity?: Severity;
  relativePath?: string;
  findings: Finding[];
}

export function groupFindings(findings: readonly Finding[], groupBy: GroupBy): FindingGroup[] {
  if (groupBy === 'file') {
    const byPath = new Map<string, Finding[]>();
    for (const finding of findings) {
      const existing = byPath.get(finding.relativePath) ?? [];
      existing.push(finding);
      byPath.set(finding.relativePath, existing);
    }
    return [...byPath.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([relativePath, groupFindingsList]) => ({
        key: `file:${relativePath}`,
        label: relativePath,
        relativePath,
        findings: groupFindingsList,
      }));
  }

  const bySeverity = new Map<Severity, Finding[]>();
  for (const finding of findings) {
    const existing = bySeverity.get(finding.severity) ?? [];
    existing.push(finding);
    bySeverity.set(finding.severity, existing);
  }

  return SEVERITY_ORDER.filter((severity) => (bySeverity.get(severity)?.length ?? 0) > 0).map(
    (severity) => ({
      key: `severity:${severity}`,
      label: SEVERITY_LABELS[severity],
      severity,
      findings: bySeverity.get(severity) ?? [],
    }),
  );
}

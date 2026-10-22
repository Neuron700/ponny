import * as vscode from 'vscode';
import type { Finding, IgnoredFinding, ScanResult, Severity } from '../models/types';
import type { IgnoreStore } from '../storage/ignoreStore';
import { compareSeverity } from '../models/severity';

export type ScanScope = { scope: 'workspace' } | { scope: 'file'; absolutePath: string };
export type GroupBy = 'severity' | 'file';

export interface FindingsViewFilters {
  severity: Severity | 'all';
  query: string;
  groupBy: GroupBy;
  showIgnored: boolean;
}

export interface FindingsSummary {
  total: number;
  active: number;
  ignored: number;
  bySeverity: Record<Severity, number>;
}

function emptySeverityCounts(): Record<Severity, number> {
  return { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
}

export function matchesFindingQuery(finding: Finding, query: string): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return [
    finding.ruleId,
    finding.ruleTitle,
    finding.relativePath,
    finding.fileName,
    finding.message,
  ].some((value) => value.toLowerCase().includes(normalized));
}

export class FindingsStore {
  private findings: Finding[] = [];
  private lastScan: ScanResult | undefined;
  private lastScope: ScanScope = { scope: 'workspace' };
  private scanning = false;
  private errorMessage: string | undefined;
  private filters: FindingsViewFilters = {
    severity: 'all',
    query: '',
    groupBy: 'severity',
    showIgnored: false,
  };

  private readonly emitter = new vscode.EventEmitter<void>();
  readonly onDidChange = this.emitter.event;

  constructor(private readonly ignoreStore: IgnoreStore) {}

  private changed(): void {
    this.emitter.fire();
  }

  setScanning(scanning: boolean): void {
    this.scanning = scanning;
    if (scanning) {
      this.errorMessage = undefined;
    }
    this.changed();
  }

  isScanning(): boolean {
    return this.scanning;
  }

  setError(message: string): void {
    this.errorMessage = message;
    this.scanning = false;
    this.changed();
  }

  getError(): string | undefined {
    return this.errorMessage;
  }

  setScanResult(result: ScanResult, scope: ScanScope): void {
    this.findings = [...result.findings];
    this.lastScan = result;
    this.lastScope = scope;
    this.errorMessage = undefined;
    this.changed();
  }

  replaceFileFindings(absolutePath: string, result: ScanResult, scope: ScanScope): void {
    const key = absolutePath.toLowerCase();
    this.findings = this.findings.filter((finding) => finding.absolutePath.toLowerCase() !== key);
    this.findings.push(...result.findings);
    this.lastScan = result;
    this.lastScope = scope;
    this.errorMessage = undefined;
    this.changed();
  }

  clear(): void {
    this.findings = [];
    this.lastScan = undefined;
    this.lastScope = { scope: 'workspace' };
    this.errorMessage = undefined;
    this.changed();
  }

  getAllFindings(): Finding[] {
    return [...this.findings];
  }

  getActiveFindings(): Finding[] {
    return this.findings.filter((finding) => !this.ignoreStore.isFindingIgnored(finding));
  }

  getVisibleFindings(): Finding[] {
    const { severity, query } = this.filters;
    return this.getActiveFindings()
      .filter((finding) => severity === 'all' || finding.severity === severity)
      .filter((finding) => matchesFindingQuery(finding, query))
      .sort((a, b) => {
        const severityDelta = compareSeverity(a.severity, b.severity);
        if (severityDelta !== 0) {
          return severityDelta;
        }
        const pathDelta = a.relativePath.localeCompare(b.relativePath);
        if (pathDelta !== 0) {
          return pathDelta;
        }
        return a.line - b.line;
      });
  }

  getIgnoredItems(): IgnoredFinding[] {
    return this.ignoreStore.list();
  }

  getIgnoredFindingsForCurrentScan(): IgnoredFinding[] {
    return this.findings
      .filter((finding) => this.ignoreStore.isFindingIgnored(finding))
      .map((finding): IgnoredFinding => {
        const stored = this.ignoreStore
          .list()
          .find(
            (item) =>
              item.ruleId === finding.ruleId &&
              item.relativePath === finding.relativePath &&
              item.fingerprint === finding.fingerprint,
          );
        return (
          stored ?? {
            ruleId: finding.ruleId,
            ruleTitle: finding.ruleTitle,
            severity: finding.severity,
            relativePath: finding.relativePath,
            fingerprint: finding.fingerprint,
            maskedSnippet: finding.maskedSnippet,
            ignoredAt: finding.id,
          }
        );
      });
  }

  getSummary(): FindingsSummary {
    const bySeverity = emptySeverityCounts();
    let active = 0;
    let ignored = 0;
    for (const finding of this.findings) {
      if (this.ignoreStore.isFindingIgnored(finding)) {
        ignored += 1;
      } else {
        active += 1;
        bySeverity[finding.severity] += 1;
      }
    }
    return { total: this.findings.length, active, ignored, bySeverity };
  }

  findById(id: string): Finding | undefined {
    return this.findings.find((finding) => finding.id === id);
  }

  findAt(absolutePath: string, ruleId: string, line: number): Finding | undefined {
    const key = absolutePath.toLowerCase();
    return this.findings.find(
      (finding) =>
        finding.absolutePath.toLowerCase() === key &&
        finding.ruleId === ruleId &&
        finding.line === line,
    );
  }

  async ignore(finding: Finding): Promise<void> {
    await this.ignoreStore.add(finding);
    this.changed();
  }

  async restore(item: IgnoredFinding): Promise<void> {
    await this.ignoreStore.remove(item);
    this.changed();
  }

  getFilters(): FindingsViewFilters {
    return { ...this.filters };
  }

  setSeverityFilter(severity: Severity | 'all'): void {
    this.filters.severity = severity;
    this.changed();
  }

  setQuery(query: string): void {
    this.filters.query = query;
    this.changed();
  }

  setGroupBy(groupBy: GroupBy): void {
    this.filters.groupBy = groupBy;
    this.changed();
  }

  toggleShowIgnored(): void {
    this.filters.showIgnored = !this.filters.showIgnored;
    this.changed();
  }

  getLastScan(): ScanResult | undefined {
    return this.lastScan;
  }

  getLastScope(): ScanScope {
    return this.lastScope;
  }

  getViewDescription(): string {
    const summary = this.getSummary();
    const parts: string[] = [];
    if (summary.total > 0) {
      parts.push(`${summary.active} active`);
    }
    if (this.filters.severity !== 'all') {
      parts.push(`severity: ${this.filters.severity}`);
    }
    if (this.filters.query.trim()) {
      parts.push(`search: ${this.filters.query.trim()}`);
    }
    if (this.filters.groupBy === 'file') {
      parts.push('grouped by file');
    }
    if (this.filters.showIgnored) {
      parts.push('ignored shown');
    }
    return parts.join(' · ');
  }

  dispose(): void {
    this.emitter.dispose();
  }
}

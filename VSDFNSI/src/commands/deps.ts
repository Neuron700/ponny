import * as vscode from 'vscode';
import type { ScanResult } from '../models/types';
import type { DiagnosticManager } from '../diagnostics/diagnosticManager';
import type { ScanService } from '../scanner/scanService';
import type { FindingsProvider } from '../providers/findingsProvider';
import type { FindingDetailsPanel } from '../providers/findingDetailsPanel';
import type { FindingsStore } from '../state/findingsStore';
import type { IgnoreStore } from '../storage/ignoreStore';

export interface CommandDeps {
  context: vscode.ExtensionContext;
  store: FindingsStore;
  ignoreStore: IgnoreStore;
  diagnostics: DiagnosticManager;
  details: FindingDetailsPanel;
  provider: FindingsProvider;
  scanService: ScanService;
  output: vscode.OutputChannel;
}

export function ensureTrusted(): boolean {
  if (!vscode.workspace.isTrusted) {
    void vscode.window.showWarningMessage(
      'RepoGuard does not scan untrusted workspaces. Trust this folder to run a scan.',
    );
    return false;
  }
  return true;
}

export function resultSummary(result: ScanResult): string {
  const findings = `${result.findings.length} finding${result.findings.length === 1 ? '' : 's'}`;
  const files = `${result.filesScanned} file${result.filesScanned === 1 ? '' : 's'} scanned`;
  const skipped = result.filesSkipped > 0 ? `, ${result.filesSkipped} skipped` : '';
  return `${findings} in ${files}${skipped}`;
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return typeof error === 'string' ? error : 'Unknown error';
}

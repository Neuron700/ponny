import * as vscode from 'vscode';
import type { ScanResult } from '../models/types';
import type { ScanProgress } from '../scanner/scanRunner';
import { readScannerSettings } from '../config/settings';
import { ensureTrusted, errorMessage, resultSummary, type CommandDeps } from './deps';

function refreshDiagnostics(deps: CommandDeps): void {
  deps.diagnostics.setFindings(deps.store.getActiveFindings());
}

async function withScanProgress(
  title: string,
  work: (
    signal: AbortSignal,
    progress: vscode.Progress<{ message?: string; increment?: number }>,
  ) => Promise<ScanResult>,
): Promise<ScanResult> {
  return vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title,
      cancellable: true,
    },
    async (progress, token) => {
      const controller = new AbortController();
      const subscription = token.onCancellationRequested(() => controller.abort());
      try {
        return await work(controller.signal, progress);
      } finally {
        subscription.dispose();
      }
    },
  );
}

function progressReporter(
  progress: vscode.Progress<{ message?: string; increment?: number }>,
): (update: ScanProgress) => void {
  return (update) => {
    const increment = update.total > 0 ? 100 / update.total : 0;
    progress.report({
      increment,
      message:
        update.total > 0
          ? `${update.processed}/${update.total}${update.currentFile ? ` · ${update.currentFile}` : ''}`
          : 'No matching files',
    });
  };
}

export async function scanWorkspace(deps: CommandDeps): Promise<void> {
  if (!ensureTrusted()) {
    return;
  }
  if (deps.store.isScanning()) {
    void vscode.window.showInformationMessage('A RepoGuard scan is already running.');
    return;
  }

  const settings = readScannerSettings();
  deps.store.setScanning(true);
  deps.output.appendLine(`[scan] workspace started (max ${settings.maxFileSizeBytes} bytes/file)`);

  try {
    const result = await withScanProgress('RepoGuard: scanning workspace', (signal, progress) =>
      deps.scanService.scanWorkspace(settings, signal, progressReporter(progress)),
    );

    deps.output.appendLine(
      `[scan] workspace finished: files=${result.filesScanned} findings=${result.findings.length} skipped=${result.filesSkipped} cancelled=${result.cancelled}`,
    );

    if (result.cancelled) {
      void vscode.window.showWarningMessage(
        `RepoGuard scan cancelled. Previous results were kept. ${resultSummary(result)} before cancellation.`,
      );
      return;
    }

    deps.store.setScanResult(result, { scope: 'workspace' });
    refreshDiagnostics(deps);
    void vscode.window.showInformationMessage(`RepoGuard: ${resultSummary(result)}.`);
  } catch (error) {
    const message = errorMessage(error);
    deps.store.setError(message);
    deps.output.appendLine(`[scan] workspace failed: ${message}`);
    void vscode.window.showErrorMessage(`RepoGuard scan failed: ${message}`);
  } finally {
    deps.store.setScanning(false);
  }
}

export async function scanCurrentFile(deps: CommandDeps): Promise<void> {
  if (!ensureTrusted()) {
    return;
  }
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    void vscode.window.showWarningMessage('Open a file before running Scan Current File.');
    return;
  }
  if (deps.store.isScanning()) {
    void vscode.window.showInformationMessage('A RepoGuard scan is already running.');
    return;
  }

  const document = editor.document;
  const settings = readScannerSettings();
  deps.store.setScanning(true);
  deps.output.appendLine(`[scan] file started: ${document.fileName}`);

  try {
    const result = await withScanProgress('RepoGuard: scanning current file', (signal) =>
      deps.scanService.scanDocument(document, settings, signal),
    );

    if (result.cancelled) {
      void vscode.window.showWarningMessage('RepoGuard file scan cancelled.');
      return;
    }

    deps.store.replaceFileFindings(document.uri.fsPath, result, {
      scope: 'file',
      absolutePath: document.uri.fsPath,
    });
    refreshDiagnostics(deps);
    deps.output.appendLine(
      `[scan] file finished: findings=${result.findings.length} skipped=${result.filesSkipped}`,
    );
    void vscode.window.showInformationMessage(`RepoGuard: ${resultSummary(result)}.`);
  } catch (error) {
    const message = errorMessage(error);
    deps.store.setError(message);
    deps.output.appendLine(`[scan] file failed: ${message}`);
    void vscode.window.showErrorMessage(`RepoGuard file scan failed: ${message}`);
  } finally {
    deps.store.setScanning(false);
  }
}

export async function refreshFindings(deps: CommandDeps): Promise<void> {
  if (!ensureTrusted()) {
    return;
  }
  if (deps.store.isScanning()) {
    void vscode.window.showInformationMessage('A RepoGuard scan is already running.');
    return;
  }

  const scope = deps.store.getLastScope();
  if (scope.scope === 'file') {
    try {
      const document = await vscode.workspace.openTextDocument(vscode.Uri.file(scope.absolutePath));
      const settings = readScannerSettings();
      deps.store.setScanning(true);
      try {
        const result = await deps.scanService.scanDocument(document, settings);
        if (!result.cancelled) {
          deps.store.replaceFileFindings(document.uri.fsPath, result, scope);
          refreshDiagnostics(deps);
          void vscode.window.showInformationMessage(`RepoGuard: ${resultSummary(result)}.`);
        }
      } finally {
        deps.store.setScanning(false);
      }
      return;
    } catch {
      deps.output.appendLine('[scan] previous file unavailable; falling back to workspace scan');
    }
  }

  await scanWorkspace(deps);
}

export function clearFindings(deps: CommandDeps): void {
  deps.store.clear();
  deps.diagnostics.clear();
  deps.output.appendLine('[findings] cleared');
}

export async function scanDocumentOnSave(
  deps: CommandDeps,
  document: vscode.TextDocument,
): Promise<void> {
  if (!ensureTrusted() || deps.store.isScanning()) {
    return;
  }
  if (document.uri.scheme !== 'file' || !vscode.workspace.getWorkspaceFolder(document.uri)) {
    return;
  }

  const settings = readScannerSettings();
  if (!settings.scanOnSave) {
    return;
  }

  vscode.window.setStatusBarMessage('RepoGuard: checking saved file…', 3000);
  try {
    const result = await deps.scanService.scanDocument(document, settings);
    if (!result.cancelled) {
      deps.store.replaceFileFindings(document.uri.fsPath, result, {
        scope: 'file',
        absolutePath: document.uri.fsPath,
      });
      refreshDiagnostics(deps);
      if (result.findings.length > 0) {
        vscode.window.setStatusBarMessage(
          `RepoGuard: ${result.findings.length} finding(s) in saved file`,
          4000,
        );
      }
    }
  } catch (error) {
    const message = errorMessage(error);
    deps.output.appendLine(`[scan-on-save] failed: ${message}`);
    void vscode.window.showWarningMessage(`RepoGuard scan on save failed: ${message}`);
  }
}

export function registerSaveListener(deps: CommandDeps): vscode.Disposable {
  let timer: ReturnType<typeof setTimeout> | undefined;
  return vscode.workspace.onDidSaveTextDocument((document) => {
    if (timer) {
      clearTimeout(timer);
    }
    timer = setTimeout(() => {
      timer = undefined;
      void scanDocumentOnSave(deps, document);
    }, 400);
  });
}

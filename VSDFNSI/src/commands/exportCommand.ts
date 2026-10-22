import * as vscode from 'vscode';
import { buildReport, defaultReportFileName, serializeReport } from '../report/reportBuilder';
import { errorMessage, type CommandDeps } from './deps';

export async function exportReport(deps: CommandDeps): Promise<void> {
  const scan = deps.store.getLastScan();
  if (!scan) {
    void vscode.window.showWarningMessage(
      'Run a RepoGuard scan before exporting a report. Reports reflect the most recent scan.',
    );
    return;
  }

  const findings = deps.store.getAllFindings();
  const ignoredIds = new Set(
    findings
      .filter((finding) => deps.ignoreStore.isFindingIgnored(finding))
      .map((finding) => finding.id),
  );

  const report = buildReport({
    toolVersion: String(deps.context.extension.packageJSON.version ?? '0.0.0'),
    workspaceLabel: vscode.workspace.name ?? 'workspace',
    workspaceFolders: (vscode.workspace.workspaceFolders ?? []).map((folder) => folder.name),
    findings,
    ignoredIds,
    scan,
  });

  const defaultName = defaultReportFileName();
  const defaultUri = vscode.workspace.workspaceFolders?.[0]
    ? vscode.Uri.joinPath(vscode.workspace.workspaceFolders[0].uri, defaultName)
    : undefined;

  const destination = await vscode.window.showSaveDialog({
    title: 'RepoGuard: Export JSON Report',
    saveLabel: 'Export Report',
    defaultUri,
    filters: { 'JSON report': ['json'] },
  });

  if (!destination) {
    return;
  }

  try {
    const content = Buffer.from(serializeReport(report), 'utf8');
    await vscode.workspace.fs.writeFile(destination, content);
    deps.output.appendLine(
      `[report] exported ${report.summary.total} finding(s), ${report.summary.ignored} ignored`,
    );
    const choice = await vscode.window.showInformationMessage(
      `RepoGuard report saved (${report.summary.total} finding(s)). Sensitive values are redacted.`,
      'Open Report',
    );
    if (choice === 'Open Report') {
      const document = await vscode.workspace.openTextDocument(destination);
      await vscode.window.showTextDocument(document, { preview: false });
    }
  } catch (error) {
    const message = errorMessage(error);
    deps.output.appendLine(`[report] export failed: ${message}`);
    void vscode.window.showErrorMessage(`Could not write the RepoGuard report: ${message}`);
  }
}

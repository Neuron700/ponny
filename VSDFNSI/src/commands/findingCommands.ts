import * as vscode from 'vscode';
import type { Finding, IgnoredFinding } from '../models/types';
import type { FindingsStore } from '../state/findingsStore';
import { findingToRange } from '../diagnostics/descriptors';
import { errorMessage, type CommandDeps } from './deps';
import { SEVERITY_LABELS } from '../models/severity';

function clamp(value: number, max: number): number {
  return Math.max(0, Math.min(value, max));
}

function findingFromArg(store: FindingsStore, arg: unknown): Finding | undefined {
  if (typeof arg === 'string') {
    return store.findById(arg);
  }
  if (!arg || typeof arg !== 'object') {
    return undefined;
  }
  const candidate = arg as {
    finding?: Finding;
    id?: string;
  };
  if (candidate.finding?.id) {
    return store.findById(candidate.finding.id) ?? candidate.finding;
  }
  if (typeof candidate.id === 'string') {
    return store.findById(candidate.id);
  }
  return undefined;
}

function ignoredFromArg(arg: unknown, store: FindingsStore): IgnoredFinding | undefined {
  if (!arg || typeof arg !== 'object') {
    return undefined;
  }
  const candidate = arg as {
    item?: IgnoredFinding;
    ruleId?: string;
    fingerprint?: string;
    relativePath?: string;
  };
  if (candidate.item?.fingerprint) {
    return candidate.item;
  }
  if (candidate.ruleId && candidate.fingerprint && candidate.relativePath) {
    return store
      .getIgnoredItems()
      .find(
        (item) =>
          item.ruleId === candidate.ruleId &&
          item.relativePath === candidate.relativePath &&
          item.fingerprint === candidate.fingerprint,
      );
  }
  return undefined;
}

export async function openFinding(deps: CommandDeps, arg: unknown): Promise<void> {
  const finding = findingFromArg(deps.store, arg);
  if (!finding) {
    void vscode.window.showWarningMessage(
      'This RepoGuard finding is no longer in the current results. Run a scan again.',
    );
    return;
  }

  try {
    const document = await vscode.workspace.openTextDocument(vscode.Uri.file(finding.absolutePath));
    const descriptorRange = findingToRange(finding);
    const startLine = clamp(descriptorRange.startLine, document.lineCount - 1);
    const endLine = clamp(descriptorRange.endLine, document.lineCount - 1);
    const startCharacter = clamp(
      descriptorRange.startCharacter,
      document.lineAt(startLine).text.length,
    );
    const endCharacter = clamp(descriptorRange.endCharacter, document.lineAt(endLine).text.length);
    const selection = new vscode.Range(
      startLine,
      startCharacter,
      endLine,
      Math.max(startCharacter, endCharacter),
    );
    await vscode.window.showTextDocument(document, {
      preview: false,
      selection,
    });
  } catch (error) {
    void vscode.window.showWarningMessage(
      `Could not open the finding location: ${errorMessage(error)}`,
    );
  }

  deps.details.show(finding);
}

export async function showFindingDetails(deps: CommandDeps, arg: unknown): Promise<void> {
  const finding = findingFromArg(deps.store, arg);
  if (!finding) {
    void vscode.window.showWarningMessage(
      'This RepoGuard finding is no longer in the current results. Run a scan again.',
    );
    return;
  }
  deps.details.show(finding);
}

export async function ignoreFinding(deps: CommandDeps, arg: unknown): Promise<void> {
  const finding = findingFromArg(deps.store, arg);
  if (!finding) {
    void vscode.window.showWarningMessage(
      'This RepoGuard finding is no longer in the current results. Run a scan again.',
    );
    return;
  }
  if (deps.ignoreStore.isFindingIgnored(finding)) {
    void vscode.window.showInformationMessage(
      `${finding.ruleId} is already ignored at this location.`,
    );
    return;
  }

  await deps.store.ignore(finding);
  deps.diagnostics.setFindings(deps.store.getActiveFindings());
  deps.output.appendLine(`[ignore] added ${finding.ruleId} (${finding.relativePath})`);
  void vscode.window.showInformationMessage(
    `Ignored ${finding.ruleId} at ${finding.relativePath}:${finding.line}. Use RepoGuard: Manage Ignored Findings to restore it.`,
  );
}

export async function restoreFinding(deps: CommandDeps, arg: unknown): Promise<void> {
  const item = ignoredFromArg(arg, deps.store);
  if (!item) {
    void vscode.window.showWarningMessage(
      'This ignored finding could not be resolved. Open RepoGuard: Manage Ignored Findings.',
    );
    return;
  }

  await deps.store.restore(item);
  deps.diagnostics.setFindings(deps.store.getActiveFindings());
  deps.output.appendLine(`[ignore] restored ${item.ruleId} (${item.relativePath})`);
  void vscode.window.showInformationMessage(
    `Restored ${item.ruleId} at ${item.relativePath}. Run a scan if it is not visible yet.`,
  );
}

interface IgnoredQuickPickItem extends vscode.QuickPickItem {
  item: IgnoredFinding;
}

export async function manageIgnoredFindings(deps: CommandDeps): Promise<void> {
  const items = deps.store.getIgnoredItems().sort((a, b) => b.ignoredAt.localeCompare(a.ignoredAt));

  if (items.length === 0) {
    void vscode.window.showInformationMessage(
      'RepoGuard has no ignored findings. Ignore a finding from the sidebar or a quick fix first.',
    );
    return;
  }

  const choices = items.map((item): IgnoredQuickPickItem => ({
    label: `${item.ruleId} · ${item.ruleTitle}`,
    description: `${item.relativePath} · ${SEVERITY_LABELS[item.severity]}`,
    detail: `Ignored ${item.ignoredAt}${item.maskedSnippet ? ` · ${item.maskedSnippet}` : ''}`,
    picked: false,
    item,
  }));

  const selected = await vscode.window.showQuickPick<IgnoredQuickPickItem>(choices, {
    canPickMany: true,
    title: 'RepoGuard: Restore Ignored Findings',
    placeHolder: 'Select the ignored findings to restore',
    matchOnDescription: true,
    matchOnDetail: true,
  });

  if (!selected || selected.length === 0) {
    return;
  }

  for (const choice of selected) {
    await deps.store.restore(choice.item);
  }
  deps.diagnostics.setFindings(deps.store.getActiveFindings());
  deps.output.appendLine(`[ignore] restored ${selected.length} finding(s)`);
  void vscode.window.showInformationMessage(
    `Restored ${selected.length} ignored finding${selected.length === 1 ? '' : 's'}. Run a scan to refresh locations.`,
  );
}

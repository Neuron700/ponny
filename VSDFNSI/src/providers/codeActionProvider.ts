import * as vscode from 'vscode';
import type { Finding } from '../models/types';
import type { FindingsStore } from '../state/findingsStore';

export class RepoGuardCodeActionProvider implements vscode.CodeActionProvider {
  static readonly providedCodeActionKinds = [vscode.CodeActionKind.QuickFix];

  constructor(private readonly store: FindingsStore) {}

  provideCodeActions(
    document: vscode.TextDocument,
    range: vscode.Range | vscode.Selection,
    context: vscode.CodeActionContext,
  ): vscode.CodeAction[] {
    const actions: vscode.CodeAction[] = [];
    const seen = new Set<string>();

    for (const diagnostic of context.diagnostics) {
      if (diagnostic.source !== 'RepoGuard' || !diagnostic.code) {
        continue;
      }
      const line = range.start.line + 1;
      const ruleId = String(diagnostic.code);
      const finding = this.store.findAt(document.uri.fsPath, ruleId, line);
      if (!finding || seen.has(finding.id)) {
        continue;
      }
      seen.add(finding.id);
      actions.push(this.ignoreAction(finding, diagnostic));
      actions.push(this.detailsAction(finding, diagnostic));
    }

    return actions;
  }

  private ignoreAction(finding: Finding, diagnostic: vscode.Diagnostic): vscode.CodeAction {
    const action = new vscode.CodeAction(
      `RepoGuard: Ignore ${finding.ruleId} finding in this location`,
      vscode.CodeActionKind.QuickFix,
    );
    action.command = {
      command: 'repoguard.ignoreFinding',
      title: 'Ignore Finding',
      arguments: [finding.id],
    };
    action.diagnostics = [diagnostic];
    return action;
  }

  private detailsAction(finding: Finding, diagnostic: vscode.Diagnostic): vscode.CodeAction {
    const action = new vscode.CodeAction(
      `RepoGuard: Show details for ${finding.ruleId}`,
      vscode.CodeActionKind.QuickFix,
    );
    action.command = {
      command: 'repoguard.showFindingDetails',
      title: 'Show Finding Details',
      arguments: [finding.id],
    };
    action.diagnostics = [diagnostic];
    return action;
  }
}

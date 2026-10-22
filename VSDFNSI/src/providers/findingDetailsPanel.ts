import * as vscode from 'vscode';
import { randomBytes } from 'node:crypto';
import type { Finding } from '../models/types';
import { renderFindingDetailsHtml } from '../report/detailsHtml';

export class FindingDetailsPanel {
  private panel: vscode.WebviewPanel | undefined;

  show(finding: Finding): void {
    if (!this.panel) {
      this.panel = vscode.window.createWebviewPanel(
        'repoguard.findingDetails',
        `RepoGuard: ${finding.ruleId}`,
        { viewColumn: vscode.ViewColumn.Beside, preserveFocus: true },
        {
          enableScripts: false,
          retainContextWhenHidden: true,
          localResourceRoots: [],
        },
      );
      this.panel.onDidDispose(() => {
        this.panel = undefined;
      });
    }

    const nonce = randomBytes(16).toString('hex');
    this.panel.title = `RepoGuard: ${finding.ruleId} · ${finding.ruleTitle}`;
    this.panel.webview.html = renderFindingDetailsHtml(finding, nonce);
    this.panel.reveal(vscode.ViewColumn.Beside, true);
  }

  dispose(): void {
    this.panel?.dispose();
    this.panel = undefined;
  }
}

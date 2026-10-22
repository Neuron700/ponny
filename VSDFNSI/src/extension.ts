import * as vscode from 'vscode';
import { createDefaultRegistry } from './rules';
import { ScanService } from './scanner/scanService';
import { FindingsStore } from './state/findingsStore';
import { IgnoreStore } from './storage/ignoreStore';
import { DiagnosticManager } from './diagnostics/diagnosticManager';
import { FindingsProvider } from './providers/findingsProvider';
import { FindingDetailsPanel } from './providers/findingDetailsPanel';
import { RepoGuardCodeActionProvider } from './providers/codeActionProvider';
import { registerCommands } from './commands';
import type { CommandDeps } from './commands/deps';

export function activate(context: vscode.ExtensionContext): void {
  const output = vscode.window.createOutputChannel('RepoGuard');
  const registry = createDefaultRegistry();
  const ignoreStore = new IgnoreStore(context.workspaceState);
  const store = new FindingsStore(ignoreStore);
  const diagnostics = new DiagnosticManager();
  const details = new FindingDetailsPanel();
  const provider = new FindingsProvider(store);
  const treeView = vscode.window.createTreeView('repoguard.findings', {
    treeDataProvider: provider,
    showCollapseAll: true,
  });
  const scanService = new ScanService(registry);

  const deps: CommandDeps = {
    context,
    store,
    ignoreStore,
    diagnostics,
    details,
    provider,
    scanService,
    output,
  };

  context.subscriptions.push(
    output,
    store,
    diagnostics,
    details,
    treeView,
    ...registerCommands(deps),
    vscode.languages.registerCodeActionsProvider(
      { scheme: 'file' },
      new RepoGuardCodeActionProvider(store),
      {
        providedCodeActionKinds: RepoGuardCodeActionProvider.providedCodeActionKinds,
      },
    ),
  );

  context.subscriptions.push(
    store.onDidChange(() => {
      provider.refresh();
      treeView.description = store.getViewDescription();
    }),
  );

  output.appendLine(
    `RepoGuard activated with ${registry.size()} rule(s). Local analysis only; no telemetry.`,
  );
}

export function deactivate(): void {
  // Resources are disposed through the extension context subscriptions.
}

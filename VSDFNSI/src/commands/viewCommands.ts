import * as vscode from 'vscode';
import type { Severity } from '../models/types';
import { SEVERITY_LABELS, SEVERITY_ORDER, isSeverity } from '../models/severity';
import type { CommandDeps } from './deps';

interface SeverityQuickPickItem extends vscode.QuickPickItem {
  value: Severity | 'all';
}

export async function searchFindings(deps: CommandDeps): Promise<void> {
  const current = deps.store.getFilters().query;
  const query = await vscode.window.showInputBox({
    title: 'RepoGuard: Search Findings',
    prompt: 'Match file path, rule ID, title, or message. Leave empty to clear the search.',
    value: current,
    placeHolder: 'For example: RG001 or src/auth',
    ignoreFocusOut: true,
  });

  if (query === undefined) {
    return;
  }
  deps.store.setQuery(query);
}

export async function setSeverityFilter(deps: CommandDeps): Promise<void> {
  const current = deps.store.getFilters().severity;
  const items: SeverityQuickPickItem[] = [
    { label: 'All severities', value: 'all', picked: current === 'all' },
    ...SEVERITY_ORDER.map((severity): SeverityQuickPickItem => ({
      label: SEVERITY_LABELS[severity],
      description: severity,
      value: severity,
      picked: current === severity,
    })),
  ];

  const selected = await vscode.window.showQuickPick(items, {
    title: 'RepoGuard: Filter by Severity',
    placeHolder: 'Choose which findings the sidebar shows',
  });
  if (!selected) {
    return;
  }
  if (selected.value !== 'all' && !isSeverity(selected.value)) {
    return;
  }
  deps.store.setSeverityFilter(selected.value);
}

export function toggleGroupBy(deps: CommandDeps): void {
  const current = deps.store.getFilters().groupBy;
  deps.store.setGroupBy(current === 'severity' ? 'file' : 'severity');
}

export function toggleIgnored(deps: CommandDeps): void {
  deps.store.toggleShowIgnored();
}

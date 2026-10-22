import * as vscode from 'vscode';
import type { Finding, IgnoredFinding, Severity } from '../models/types';
import { SEVERITY_LABELS } from '../models/severity';
import type { FindingsStore } from '../state/findingsStore';
import { groupFindings, type FindingGroup } from './grouping';
import { redactSecrets } from '../utils/masking';

type FindingsNode =
  | { kind: 'summary' }
  | { kind: 'group'; group: FindingGroup }
  | { kind: 'finding'; finding: Finding }
  | { kind: 'ignoredGroup'; count: number }
  | { kind: 'ignored'; item: IgnoredFinding; finding?: Finding }
  | {
      kind: 'message';
      label: string;
      description: string;
      icon: string;
      iconColor?: string;
      tooltip?: string;
      command?: vscode.Command;
    };

function severityIcon(severity: Severity): vscode.ThemeIcon {
  switch (severity) {
    case 'critical':
      return new vscode.ThemeIcon('shield', new vscode.ThemeColor('errorForeground'));
    case 'high':
      return new vscode.ThemeIcon('error', new vscode.ThemeColor('errorForeground'));
    case 'medium':
      return new vscode.ThemeIcon('warning', new vscode.ThemeColor('editorWarning.foreground'));
    case 'low':
      return new vscode.ThemeIcon('info', new vscode.ThemeColor('editorInfo.foreground'));
    case 'info':
    default:
      return new vscode.ThemeIcon('lightbulb', new vscode.ThemeColor('foreground'));
  }
}

function findingTooltip(finding: Finding): vscode.MarkdownString {
  const tooltip = new vscode.MarkdownString();
  tooltip.appendMarkdown(`**${finding.ruleId} · ${finding.ruleTitle}**\n\n`);
  tooltip.appendText(`${finding.message}\n\n`);
  tooltip.appendMarkdown('**Location:** ');
  tooltip.appendText(`${finding.relativePath}:${finding.line}:${finding.column}\n\n`);
  if (finding.maskedSnippet) {
    tooltip.appendMarkdown('**Masked line:**\n\n');
    tooltip.appendCodeblock(redactSecrets(finding.maskedSnippet), 'text');
    tooltip.appendMarkdown('\n');
  }
  tooltip.appendMarkdown('**Remediation:** ');
  tooltip.appendText(`${finding.remediation}\n\n`);
  tooltip.appendMarkdown('**Limitations:** ');
  tooltip.appendText(finding.limitations);
  return tooltip;
}

export class FindingsProvider implements vscode.TreeDataProvider<FindingsNode> {
  private readonly emitter = new vscode.EventEmitter<FindingsNode | undefined>();
  readonly onDidChangeTreeData = this.emitter.event;

  constructor(private readonly store: FindingsStore) {}

  refresh(): void {
    this.emitter.fire(undefined);
  }

  getTreeItem(element: FindingsNode): vscode.TreeItem {
    switch (element.kind) {
      case 'summary':
        return this.summaryItem();
      case 'group':
        return this.groupItem(element.group);
      case 'finding':
        return this.findingItem(element.finding);
      case 'ignoredGroup':
        return this.ignoredGroupItem(element.count);
      case 'ignored':
        return this.ignoredItem(element.item, element.finding);
      case 'message':
        return this.messageItem(element);
    }
  }

  getChildren(element?: FindingsNode): vscode.ProviderResult<FindingsNode[]> {
    if (!element) {
      return this.rootNodes();
    }
    if (element.kind === 'group') {
      return element.group.findings.map((finding) => ({ kind: 'finding' as const, finding }));
    }
    if (element.kind === 'ignoredGroup') {
      return this.ignoredNodes();
    }
    return [];
  }

  private rootNodes(): FindingsNode[] {
    if (this.store.isScanning()) {
      return [
        {
          kind: 'message',
          label: 'Scanning…',
          description: 'RepoGuard is checking files locally.',
          icon: 'loading~spin',
          tooltip: 'Scan in progress. Use the progress notification to cancel.',
        },
      ];
    }

    const error = this.store.getError();
    if (error) {
      return [
        {
          kind: 'message',
          label: 'Scan failed',
          description: error,
          icon: 'error',
          iconColor: 'errorForeground',
          tooltip: error,
          command: {
            command: 'repoguard.scanWorkspace',
            title: 'Try Scan Again',
          },
        },
      ];
    }

    const summary = this.store.getSummary();
    if (summary.total === 0) {
      const lastScan = this.store.getLastScan();
      if (!lastScan) {
        return [
          {
            kind: 'message',
            label: 'No scan yet',
            description: 'Run a scan to look for security hygiene issues.',
            icon: 'shield',
            command: {
              command: 'repoguard.scanWorkspace',
              title: 'Scan Workspace',
            },
          },
        ];
      }
      return [
        {
          kind: 'message',
          label: 'No findings',
          description: `Checked ${lastScan.filesScanned} file(s). Nothing matched the enabled rules.`,
          icon: 'pass',
          iconColor: 'testing.iconPassed',
          tooltip:
            'A clean result means no configured rule matched. It does not prove the project is secure.',
          command: {
            command: 'repoguard.refresh',
            title: 'Scan Again',
          },
        },
      ];
    }

    const visible = this.store.getVisibleFindings();
    if (visible.length === 0 && !this.store.getFilters().showIgnored) {
      return [
        {
          kind: 'message',
          label: 'No findings match the filters',
          description: 'Adjust the severity filter or search query.',
          icon: 'filter',
          command: {
            command: 'repoguard.setSeverityFilter',
            title: 'Change Severity Filter',
          },
        },
      ];
    }

    const filters = this.store.getFilters();
    const nodes: FindingsNode[] = [{ kind: 'summary' }];
    for (const group of groupFindings(visible, filters.groupBy)) {
      nodes.push({ kind: 'group', group });
    }

    if (filters.showIgnored) {
      const ignored = this.ignoredNodes();
      if (ignored.length > 0) {
        nodes.push({ kind: 'ignoredGroup', count: ignored.length });
      }
    }

    return nodes;
  }

  private ignoredNodes(): FindingsNode[] {
    const filters = this.store.getFilters();
    const items = this.store.getIgnoredFindingsForCurrentScan().filter((item) => {
      if (filters.severity !== 'all' && item.severity !== filters.severity) {
        return false;
      }
      if (!filters.query.trim()) {
        return true;
      }
      const query = filters.query.trim().toLowerCase();
      return (
        item.ruleId.toLowerCase().includes(query) ||
        item.ruleTitle.toLowerCase().includes(query) ||
        item.relativePath.toLowerCase().includes(query)
      );
    });

    return items.map((item) => {
      const finding = this.store
        .getAllFindings()
        .find(
          (candidate) =>
            candidate.ruleId === item.ruleId &&
            candidate.relativePath === item.relativePath &&
            candidate.fingerprint === item.fingerprint,
        );
      return { kind: 'ignored' as const, item, finding };
    });
  }

  private summaryItem(): vscode.TreeItem {
    const summary = this.store.getSummary();
    const item = new vscode.TreeItem(
      `${summary.total} finding${summary.total === 1 ? '' : 's'}`,
      vscode.TreeItemCollapsibleState.None,
    );
    item.id = 'repoguard.summary';
    item.iconPath = new vscode.ThemeIcon('shield');
    item.description = `${summary.active} active · ${summary.ignored} ignored`;
    item.tooltip = [
      `Critical: ${summary.bySeverity.critical}`,
      `High: ${summary.bySeverity.high}`,
      `Medium: ${summary.bySeverity.medium}`,
      `Low: ${summary.bySeverity.low}`,
      `Info: ${summary.bySeverity.info}`,
    ].join('\n');
    item.contextValue = 'repoguard.summary';
    return item;
  }

  private groupItem(group: FindingGroup): vscode.TreeItem {
    const label =
      group.relativePath ?? (group.severity ? SEVERITY_LABELS[group.severity] : group.label);
    const item = new vscode.TreeItem(label, vscode.TreeItemCollapsibleState.Expanded);
    item.id = `group:${group.key}`;
    item.description = `${group.findings.length}`;
    item.iconPath = group.severity
      ? severityIcon(group.severity)
      : new vscode.ThemeIcon('file-code');
    item.tooltip = `${label} — ${group.findings.length} finding(s)`;
    item.contextValue = 'repoguard.group';
    return item;
  }

  private findingItem(finding: Finding): vscode.TreeItem {
    const item = new vscode.TreeItem(
      `${finding.ruleId} · ${finding.ruleTitle}`,
      vscode.TreeItemCollapsibleState.None,
    );
    item.id = finding.id;
    item.description = `${finding.relativePath}:${finding.line}`;
    item.tooltip = findingTooltip(finding);
    item.iconPath = severityIcon(finding.severity);
    item.contextValue = 'repoguard.finding.active';
    item.command = {
      command: 'repoguard.openFinding',
      title: 'Open Finding',
      arguments: [finding.id],
    };
    item.accessibilityInformation = {
      label: `${SEVERITY_LABELS[finding.severity]} finding ${finding.ruleId} in ${finding.relativePath} line ${finding.line}`,
    };
    return item;
  }

  private ignoredGroupItem(count: number): vscode.TreeItem {
    const item = new vscode.TreeItem(
      `Ignored (${count})`,
      vscode.TreeItemCollapsibleState.Collapsed,
    );
    item.id = 'repoguard.ignored-group';
    item.iconPath = new vscode.ThemeIcon('eye-closed');
    item.description = 'Not shown in Problems';
    item.tooltip = 'Ignored findings are stored locally. Restore them from the context menu.';
    item.contextValue = 'repoguard.ignoredGroup';
    return item;
  }

  private ignoredItem(item: IgnoredFinding, finding?: Finding): vscode.TreeItem {
    const treeItem = new vscode.TreeItem(
      `${item.ruleId} · ${item.ruleTitle}`,
      vscode.TreeItemCollapsibleState.None,
    );
    treeItem.id = `ignored:${item.ruleId}:${item.relativePath}:${item.fingerprint}`;
    treeItem.description = item.relativePath;
    treeItem.iconPath = new vscode.ThemeIcon('circle-slash');
    treeItem.contextValue = 'repoguard.finding.ignored';
    const tooltip = new vscode.MarkdownString();
    tooltip.appendMarkdown(`**${item.ruleId} · ${item.ruleTitle}** (ignored)\n\n`);
    tooltip.appendText(`File: ${item.relativePath}\n\n`);
    tooltip.appendMarkdown(`Ignored at: ${item.ignoredAt}`);
    treeItem.tooltip = tooltip;
    if (finding) {
      treeItem.command = {
        command: 'repoguard.openFinding',
        title: 'Open Finding',
        arguments: [finding.id],
      };
    }
    return treeItem;
  }

  private messageItem(element: Extract<FindingsNode, { kind: 'message' }>): vscode.TreeItem {
    const item = new vscode.TreeItem(element.label, vscode.TreeItemCollapsibleState.None);
    item.description = element.description;
    item.iconPath = new vscode.ThemeIcon(
      element.icon,
      element.iconColor ? new vscode.ThemeColor(element.iconColor) : undefined,
    );
    if (element.tooltip) {
      item.tooltip = element.tooltip;
    }
    if (element.command) {
      item.command = element.command;
    }
    return item;
  }
}

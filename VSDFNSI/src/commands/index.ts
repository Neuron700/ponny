import * as vscode from 'vscode';
import type { CommandDeps } from './deps';
import {
  clearFindings,
  refreshFindings,
  registerSaveListener,
  scanCurrentFile,
  scanWorkspace,
} from './scanCommands';
import {
  ignoreFinding,
  manageIgnoredFindings,
  openFinding,
  restoreFinding,
  showFindingDetails,
} from './findingCommands';
import { searchFindings, setSeverityFilter, toggleGroupBy, toggleIgnored } from './viewCommands';
import { exportReport } from './exportCommand';

export function registerCommands(deps: CommandDeps): vscode.Disposable[] {
  return [
    vscode.commands.registerCommand('repoguard.scanWorkspace', () => scanWorkspace(deps)),
    vscode.commands.registerCommand('repoguard.scanCurrentFile', () => scanCurrentFile(deps)),
    vscode.commands.registerCommand('repoguard.refresh', () => refreshFindings(deps)),
    vscode.commands.registerCommand('repoguard.clear', () => clearFindings(deps)),
    vscode.commands.registerCommand('repoguard.manageIgnored', () => manageIgnoredFindings(deps)),
    vscode.commands.registerCommand('repoguard.exportReport', () => exportReport(deps)),
    vscode.commands.registerCommand('repoguard.searchFindings', () => searchFindings(deps)),
    vscode.commands.registerCommand('repoguard.setSeverityFilter', () => setSeverityFilter(deps)),
    vscode.commands.registerCommand('repoguard.toggleGroupBy', () => toggleGroupBy(deps)),
    vscode.commands.registerCommand('repoguard.toggleIgnored', () => toggleIgnored(deps)),
    vscode.commands.registerCommand('repoguard.openFinding', (arg: unknown) =>
      openFinding(deps, arg),
    ),
    vscode.commands.registerCommand('repoguard.showFindingDetails', (arg: unknown) =>
      showFindingDetails(deps, arg),
    ),
    vscode.commands.registerCommand('repoguard.ignoreFinding', (arg: unknown) =>
      ignoreFinding(deps, arg),
    ),
    vscode.commands.registerCommand('repoguard.restoreFinding', (arg: unknown) =>
      restoreFinding(deps, arg),
    ),
    registerSaveListener(deps),
  ];
}

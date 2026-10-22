import * as vscode from 'vscode';
import * as path from 'node:path';
import type { FileCandidate, ScanResult, ScannerSettings } from '../models/types';
import type { RuleRegistry } from '../engine/registry';
import { runScan, runSingleFileScan, type ScanProgress } from './scanRunner';
import { WorkspaceScanPort } from './workspacePort';
import { extensionOf, fileNameOf } from '../utils/paths';

export class ScanService {
  constructor(private readonly registry: RuleRegistry) {}

  private workspaceFolders(): readonly vscode.WorkspaceFolder[] {
    return vscode.workspace.workspaceFolders ?? [];
  }

  private portFor(folders: readonly vscode.WorkspaceFolder[]): WorkspaceScanPort {
    return new WorkspaceScanPort(folders, folders.length > 1);
  }

  async scanWorkspace(
    settings: ScannerSettings,
    signal?: AbortSignal,
    onProgress?: (progress: ScanProgress) => void,
  ): Promise<ScanResult> {
    const folders = this.workspaceFolders();
    if (folders.length === 0) {
      throw new Error('Open a folder or workspace before running a RepoGuard scan.');
    }

    return runScan({
      folders: folders.map((folder) => folder.name),
      settings,
      registry: this.registry,
      port: this.portFor(folders),
      signal,
      onProgress,
    });
  }

  async scanDocument(
    document: vscode.TextDocument,
    settings: ScannerSettings,
    signal?: AbortSignal,
  ): Promise<ScanResult> {
    if (document.uri.scheme !== 'file') {
      throw new Error('RepoGuard can only scan files stored on the local filesystem.');
    }

    const folder = vscode.workspace.getWorkspaceFolder(document.uri);
    if (!folder) {
      throw new Error('The current file is not inside an open workspace folder.');
    }

    const folders = this.workspaceFolders();
    const port = this.portFor(folders);
    const content = document.getText();
    const candidate: FileCandidate = {
      absolutePath: document.uri.fsPath,
      relativePath: port.relativePathFor(document.uri),
      workspaceFolder: folder.name,
      fileName: fileNameOf(document.uri.fsPath) || path.basename(document.uri.fsPath),
      extension: extensionOf(document.uri.fsPath),
      sizeBytes: Buffer.byteLength(content, 'utf8'),
    };

    return runSingleFileScan({
      candidate,
      settings,
      registry: this.registry,
      signal,
      port: {
        readFile: async () => ({ ok: true, content }),
        readRootFile: (folderName, name) => port.readRootFile(folderName, name),
      },
    });
  }
}

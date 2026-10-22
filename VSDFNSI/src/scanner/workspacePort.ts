import * as vscode from 'vscode';
import * as path from 'node:path';
import type { FileCandidate, ScannerSettings } from '../models/types';
import type { ScanPort } from './scanRunner';
import { readFileContent, readTextFileIfPresent } from './readFile';
import { buildExcludeGlob, buildIncludeGlobs, isExcludedPath, isSupportedFile } from './filters';
import { extensionOf, normalizeSlashes } from '../utils/paths';

export class WorkspaceScanPort implements ScanPort {
  private readonly foldersByName = new Map<string, vscode.WorkspaceFolder>();

  constructor(
    private readonly folders: readonly vscode.WorkspaceFolder[],
    private readonly includeFolderPrefix: boolean,
  ) {
    for (const folder of folders) {
      this.foldersByName.set(folder.name, folder);
    }
  }

  relativePathFor(uri: vscode.Uri): string {
    return normalizeSlashes(vscode.workspace.asRelativePath(uri, this.includeFolderPrefix));
  }

  async listFiles(settings: ScannerSettings): Promise<FileCandidate[]> {
    const includeGlobs = buildIncludeGlobs(settings.includeExtensions);
    const excludeGlob = buildExcludeGlob(settings.excludePatterns);
    const seen = new Set<string>();
    const candidates: FileCandidate[] = [];

    for (const folder of this.folders) {
      for (const glob of includeGlobs) {
        let uris: vscode.Uri[] = [];
        try {
          uris = await vscode.workspace.findFiles(
            new vscode.RelativePattern(folder, glob),
            excludeGlob,
            20000,
          );
        } catch {
          continue;
        }

        for (const uri of uris) {
          const key = uri.fsPath.toLowerCase();
          if (seen.has(key)) {
            continue;
          }
          seen.add(key);

          const relativePath = this.relativePathFor(uri);
          const fileName = path.basename(uri.fsPath);
          if (
            isExcludedPath(relativePath, settings.excludePatterns) ||
            !isSupportedFile(fileName, settings.includeExtensions)
          ) {
            continue;
          }

          let stats: vscode.FileStat;
          try {
            stats = await vscode.workspace.fs.stat(uri);
          } catch {
            continue;
          }
          if ((stats.type & vscode.FileType.File) === 0) {
            continue;
          }

          candidates.push({
            absolutePath: uri.fsPath,
            relativePath,
            workspaceFolder: folder.name,
            fileName,
            extension: extensionOf(fileName),
            sizeBytes: stats.size,
          });
        }
      }
    }

    return candidates;
  }

  async readFile(candidate: FileCandidate, maxBytes: number) {
    return readFileContent(candidate.absolutePath, maxBytes);
  }

  async readRootFile(folderName: string, fileName: string): Promise<string | undefined> {
    const folder = this.foldersByName.get(folderName);
    if (!folder) {
      return undefined;
    }
    return readTextFileIfPresent(path.join(folder.uri.fsPath, fileName));
  }
}

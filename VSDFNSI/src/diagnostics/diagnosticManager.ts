import * as vscode from 'vscode';
import type { Finding } from '../models/types';
import { buildDiagnosticDescriptors, type DiagnosticSeverityName } from './descriptors';

function mapSeverity(name: DiagnosticSeverityName): vscode.DiagnosticSeverity {
  switch (name) {
    case 'error':
      return vscode.DiagnosticSeverity.Error;
    case 'warning':
      return vscode.DiagnosticSeverity.Warning;
    case 'information':
      return vscode.DiagnosticSeverity.Information;
    case 'hint':
    default:
      return vscode.DiagnosticSeverity.Hint;
  }
}

export class DiagnosticManager {
  private readonly collection: vscode.DiagnosticCollection;

  constructor() {
    this.collection = vscode.languages.createDiagnosticCollection('repoguard');
  }

  setFindings(findings: readonly Finding[]): void {
    this.collection.clear();
    const byFile = new Map<string, { uri: vscode.Uri; diagnostics: vscode.Diagnostic[] }>();

    for (const descriptor of buildDiagnosticDescriptors(findings)) {
      const key = descriptor.filePath.toLowerCase();
      let entry = byFile.get(key);
      if (!entry) {
        entry = { uri: vscode.Uri.file(descriptor.filePath), diagnostics: [] };
        byFile.set(key, entry);
      }

      const range = new vscode.Range(
        descriptor.range.startLine,
        descriptor.range.startCharacter,
        descriptor.range.endLine,
        descriptor.range.endCharacter,
      );
      const diagnostic = new vscode.Diagnostic(
        range,
        descriptor.message,
        mapSeverity(descriptor.severity),
      );
      diagnostic.source = descriptor.source;
      diagnostic.code = descriptor.code;
      entry.diagnostics.push(diagnostic);
    }

    for (const entry of byFile.values()) {
      this.collection.set(entry.uri, entry.diagnostics);
    }
  }

  clear(): void {
    this.collection.clear();
  }

  dispose(): void {
    this.collection.dispose();
  }
}

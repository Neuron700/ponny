import type { RuleFileInfo } from '../models/types';
import { isEnvFileName } from '../utils/paths';

export interface LineHit {
  line: number;
  column: number;
  endColumn: number;
  text: string;
  lineText: string;
}

export function findLineHits(lines: readonly string[], pattern: RegExp): LineHit[] {
  const flags = pattern.flags.includes('g') ? pattern.flags : `${pattern.flags}g`;
  const regex = new RegExp(pattern.source, flags);
  const hits: LineHit[] = [];

  for (let index = 0; index < lines.length; index += 1) {
    const lineText = lines[index];
    regex.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = regex.exec(lineText)) !== null) {
      const text = match[0];
      const column = match.index + 1;
      hits.push({
        line: index + 1,
        column,
        endColumn: column + Math.max(text.length, 1),
        text,
        lineText,
      });
      if (text.length === 0) {
        regex.lastIndex += 1;
      }
    }
  }

  return hits;
}

export function ruleAppliesToFile(
  rule: {
    fileExtensions: readonly string[] | '*';
    scanEnvFiles?: boolean;
    fileNamePattern?: RegExp;
  },
  file: RuleFileInfo,
): boolean {
  if (rule.fileNamePattern) {
    return rule.fileNamePattern.test(file.fileName);
  }
  if (rule.fileExtensions === '*') {
    return true;
  }
  if (rule.fileExtensions.includes(file.extension)) {
    return true;
  }
  return Boolean(rule.scanEnvFiles && isEnvFileName(file.fileName));
}

export function trimSnippet(line: string, maxLength = 160): string {
  const trimmed = line.trim();
  if (trimmed.length <= maxLength) {
    return trimmed;
  }
  return `${trimmed.slice(0, maxLength - 1)}…`;
}

export const SOURCE_EXTENSIONS = [
  'js',
  'jsx',
  'ts',
  'tsx',
  'mjs',
  'cjs',
  'py',
  'json',
  'jsonc',
  'yaml',
  'yml',
  'toml',
  'ini',
  'cfg',
  'conf',
  'properties',
  'sh',
  'bash',
  'ps1',
  'go',
  'rb',
  'java',
  'php',
  'cs',
  'rs',
] as const;

export const JS_TS_EXTENSIONS = ['js', 'jsx', 'ts', 'tsx', 'mjs', 'cjs'] as const;

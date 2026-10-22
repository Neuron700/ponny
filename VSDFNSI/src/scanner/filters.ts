import { minimatch } from 'minimatch';
import type { ScannerSettings } from '../models/types';
import { isEnvFileName, normalizeExtension, normalizeSlashes } from '../utils/paths';

export const ALWAYS_EXCLUDED_SEGMENTS = ['.git', 'node_modules'] as const;

export function isExcludedPath(relativePath: string, patterns: readonly string[]): boolean {
  const normalized = normalizeSlashes(relativePath).replace(/^\/+/, '');
  if (!normalized) {
    return true;
  }

  const segments = normalized.split('/');
  for (const segment of segments) {
    if ((ALWAYS_EXCLUDED_SEGMENTS as readonly string[]).includes(segment)) {
      return true;
    }
  }

  const options = { dot: true, nocase: process.platform === 'win32' };
  for (const pattern of patterns) {
    const cleaned = normalizeSlashes(pattern.trim());
    if (!cleaned) {
      continue;
    }
    if (minimatch(normalized, cleaned, options)) {
      return true;
    }
    if (!cleaned.startsWith('**/') && minimatch(normalized, `**/${cleaned}`, options)) {
      return true;
    }
  }

  return false;
}

export function isSupportedFile(fileName: string, includeExtensions: readonly string[]): boolean {
  if (isEnvFileName(fileName)) {
    return true;
  }
  const extension = normalizeExtension(fileName.split('.').pop() ?? '');
  if (!extension) {
    return false;
  }
  return includeExtensions.map(normalizeExtension).includes(extension);
}

export function filterCandidatePaths(
  relativePaths: readonly string[],
  settings: Pick<ScannerSettings, 'includeExtensions' | 'excludePatterns'>,
): string[] {
  return relativePaths.filter((relativePath) => {
    const fileName = relativePath.split('/').pop() ?? relativePath;
    return (
      !isExcludedPath(relativePath, settings.excludePatterns) &&
      isSupportedFile(fileName, settings.includeExtensions)
    );
  });
}

export function buildIncludeGlobs(includeExtensions: readonly string[]): string[] {
  const extensions = Array.from(new Set(includeExtensions.map(normalizeExtension))).filter(
    (extension) => /^[a-z0-9_+-]+$/i.test(extension),
  );
  const globs: string[] = [];
  if (extensions.length > 0) {
    globs.push(`**/*.{${extensions.join(',')}}`);
  }
  globs.push('**/.env', '**/.env.*', '**/*.env');
  return globs;
}

export function buildExcludeGlob(patterns: readonly string[]): string {
  const cleaned = patterns.map((pattern) => pattern.trim()).filter(Boolean);
  if (cleaned.length === 0) {
    return '**/{.git,node_modules}/**';
  }
  return `{${cleaned.join(',')}}`;
}

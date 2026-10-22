import * as vscode from 'vscode';
import type { ScannerSettings } from '../models/types';
import { normalizeExtension } from '../utils/paths';
import { clamp } from '../utils/text';
import {
  DEFAULT_EXCLUDE_PATTERNS,
  DEFAULT_INCLUDE_EXTENSIONS,
  DEFAULT_MAX_FILE_SIZE_KB,
} from './defaults';

export {
  DEFAULT_EXCLUDE_PATTERNS,
  DEFAULT_INCLUDE_EXTENSIONS,
  DEFAULT_MAX_FILE_SIZE_KB,
} from './defaults';

export function readScannerSettings(): ScannerSettings {
  const configuration = vscode.workspace.getConfiguration('repoguard');
  const includeRaw = configuration.get<string[]>('includeExtensions', [
    ...DEFAULT_INCLUDE_EXTENSIONS,
  ]);
  const excludeRaw = configuration.get<string[]>('excludePatterns', [...DEFAULT_EXCLUDE_PATTERNS]);
  const configuredSize = Number(
    configuration.get<number>('maxFileSizeKb', DEFAULT_MAX_FILE_SIZE_KB),
  );
  const maxFileSizeKb = Number.isFinite(configuredSize) ? configuredSize : DEFAULT_MAX_FILE_SIZE_KB;
  const enabledRules = configuration.get<string[]>('enabledRules', []);
  const disabledRules = configuration.get<string[]>('disabledRules', []);
  const scanOnSave = configuration.get<boolean>('scanOnSave', false);

  const includeExtensions = Array.from(
    new Set(
      includeRaw
        .map(normalizeExtension)
        .filter((extension) => extension.length > 0 && /^[a-z0-9_+-]+$/i.test(extension)),
    ),
  );

  return {
    includeExtensions,
    excludePatterns: excludeRaw.filter((pattern) => pattern.trim().length > 0),
    maxFileSizeBytes: Math.floor(clamp(maxFileSizeKb, 1, 10240) * 1024),
    enabledRules: enabledRules.map((id) => id.trim()).filter(Boolean),
    disabledRules: disabledRules.map((id) => id.trim()).filter(Boolean),
    scanOnSave,
  };
}

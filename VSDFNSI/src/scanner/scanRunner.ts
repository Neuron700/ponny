import type {
  FileCandidate,
  Finding,
  ReadResult,
  ScanError,
  ScanResult,
  ScannerSettings,
} from '../models/types';
import type { RuleRegistry } from '../engine/registry';
import { evaluateContent } from '../engine/ruleEngine';
import { yieldToEventLoop } from '../utils/text';
import { isExcludedPath, isSupportedFile } from './filters';

export interface ScanPort {
  listFiles(settings: ScannerSettings): Promise<FileCandidate[]>;
  readFile(candidate: FileCandidate, maxBytes: number): Promise<ReadResult>;
  readRootFile(folderName: string, fileName: string): Promise<string | undefined>;
}

export interface ScanProgress {
  processed: number;
  total: number;
  currentFile?: string;
}

export interface ScanRunnerOptions {
  folders: readonly string[];
  settings: ScannerSettings;
  registry: RuleRegistry;
  port: ScanPort;
  signal?: AbortSignal;
  onProgress?: (progress: ScanProgress) => void;
  now?: () => Date;
  yieldEvery?: number;
}

const DEFAULT_YIELD_EVERY = 25;

function nowIso(now: () => Date): string {
  return now().toISOString();
}

async function loadRootFiles(
  options: ScanRunnerOptions,
): Promise<Map<string, Record<string, string | undefined>>> {
  const rootFiles = new Map<string, Record<string, string | undefined>>();
  for (const folderName of options.folders) {
    try {
      const gitignore = await options.port.readRootFile(folderName, '.gitignore');
      rootFiles.set(folderName, { '.gitignore': gitignore });
    } catch {
      rootFiles.set(folderName, {});
    }
  }
  return rootFiles;
}

function dedupeCandidates(candidates: readonly FileCandidate[]): FileCandidate[] {
  const seen = new Set<string>();
  const unique: FileCandidate[] = [];
  for (const candidate of candidates) {
    const key = candidate.absolutePath.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    unique.push(candidate);
  }
  return unique.sort((a, b) => a.relativePath.localeCompare(b.relativePath));
}

export async function runScan(options: ScanRunnerOptions): Promise<ScanResult> {
  const now = options.now ?? (() => new Date());
  const startedAt = nowIso(now);
  const findings: Finding[] = [];
  const skipped: ScanError[] = [];
  let filesScanned = 0;
  let cancelled = false;

  const emptyResult = (): ScanResult => ({
    startedAt,
    finishedAt: nowIso(now),
    findings,
    filesScanned,
    filesSkipped: skipped.length,
    skipped,
    errors: skipped.filter((entry) => entry.reason === 'unreadable').length,
    cancelled,
    workspaceFolders: [...options.folders],
    settings: options.settings,
  });

  if (options.signal?.aborted) {
    cancelled = true;
    return emptyResult();
  }

  const listed = await options.port.listFiles(options.settings);
  const candidates = dedupeCandidates(
    listed.filter(
      (candidate) =>
        isSupportedFile(candidate.fileName, options.settings.includeExtensions) &&
        !isExcludedPath(candidate.relativePath, options.settings.excludePatterns),
    ),
  );

  const rootFiles = await loadRootFiles(options);
  const total = candidates.length;
  const yieldEvery = options.yieldEvery ?? DEFAULT_YIELD_EVERY;

  for (let index = 0; index < candidates.length; index += 1) {
    if (options.signal?.aborted) {
      cancelled = true;
      break;
    }

    const candidate = candidates[index];
    if (candidate.sizeBytes > options.settings.maxFileSizeBytes) {
      skipped.push({ relativePath: candidate.relativePath, reason: 'too-large' });
      options.onProgress?.({ processed: index + 1, total, currentFile: candidate.relativePath });
      continue;
    }

    let read: ReadResult;
    try {
      read = await options.port.readFile(candidate, options.settings.maxFileSizeBytes);
    } catch {
      read = { ok: false, reason: 'unreadable' };
    }

    if (options.signal?.aborted) {
      cancelled = true;
      break;
    }

    if (!read.ok || read.content === undefined) {
      if (read.reason) {
        skipped.push({ relativePath: candidate.relativePath, reason: read.reason });
      }
      options.onProgress?.({ processed: index + 1, total, currentFile: candidate.relativePath });
      continue;
    }

    const fileFindings = evaluateContent(
      {
        absolutePath: candidate.absolutePath,
        relativePath: candidate.relativePath,
        workspaceFolder: candidate.workspaceFolder,
        fileName: candidate.fileName,
        extension: candidate.extension,
      },
      read.content,
      options.registry,
      {
        settings: options.settings,
        rootFileContents: rootFiles.get(candidate.workspaceFolder) ?? {},
      },
    );

    findings.push(...fileFindings);
    filesScanned += 1;
    options.onProgress?.({ processed: index + 1, total, currentFile: candidate.relativePath });

    if ((index + 1) % yieldEvery === 0) {
      await yieldToEventLoop();
    }
  }

  return emptyResult();
}

export interface SingleFileOptions {
  candidate: FileCandidate;
  settings: ScannerSettings;
  registry: RuleRegistry;
  port: Pick<ScanPort, 'readFile' | 'readRootFile'>;
  signal?: AbortSignal;
  now?: () => Date;
}

export async function runSingleFileScan(options: SingleFileOptions): Promise<ScanResult> {
  const now = options.now ?? (() => new Date());
  const startedAt = nowIso(now);
  const result: ScanResult = {
    startedAt,
    finishedAt: startedAt,
    findings: [],
    filesScanned: 0,
    filesSkipped: 0,
    skipped: [],
    errors: 0,
    cancelled: false,
    workspaceFolders: [options.candidate.workspaceFolder],
    settings: options.settings,
  };

  if (options.signal?.aborted) {
    result.cancelled = true;
    result.finishedAt = nowIso(now);
    return result;
  }

  if (options.candidate.sizeBytes > options.settings.maxFileSizeBytes) {
    result.filesSkipped = 1;
    result.skipped.push({ relativePath: options.candidate.relativePath, reason: 'too-large' });
    result.finishedAt = nowIso(now);
    return result;
  }

  let read: ReadResult;
  try {
    read = await options.port.readFile(options.candidate, options.settings.maxFileSizeBytes);
  } catch {
    read = { ok: false, reason: 'unreadable' };
  }

  if (!read.ok || read.content === undefined) {
    result.filesSkipped = 1;
    if (read.reason) {
      result.skipped.push({ relativePath: options.candidate.relativePath, reason: read.reason });
      if (read.reason === 'unreadable') {
        result.errors = 1;
      }
    }
    result.finishedAt = nowIso(now);
    return result;
  }

  let gitignore: string | undefined;
  try {
    gitignore = await options.port.readRootFile(options.candidate.workspaceFolder, '.gitignore');
  } catch {
    gitignore = undefined;
  }

  result.findings = evaluateContent(
    {
      absolutePath: options.candidate.absolutePath,
      relativePath: options.candidate.relativePath,
      workspaceFolder: options.candidate.workspaceFolder,
      fileName: options.candidate.fileName,
      extension: options.candidate.extension,
    },
    read.content,
    options.registry,
    {
      settings: options.settings,
      rootFileContents: { '.gitignore': gitignore },
    },
  );
  result.filesScanned = 1;
  result.finishedAt = nowIso(now);
  return result;
}

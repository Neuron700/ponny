import { describe, expect, it } from 'vitest';
import type { FileCandidate, ReadResult } from '../src/models/types';
import type { ScanPort, ScanProgress } from '../src/scanner/scanRunner';
import { runScan, runSingleFileScan } from '../src/scanner/scanRunner';
import { createDefaultRegistry } from '../src/engine/registry';
import { makeCandidate, makeSettings } from './helpers';

function bytes(content: string): number {
  return Buffer.byteLength(content, 'utf8');
}

interface FakePortOptions {
  contents?: Record<string, string>;
  results?: Record<string, ReadResult>;
  rootFiles?: Record<string, Record<string, string | undefined>>;
  listError?: boolean;
}

function fakePort(candidates: FileCandidate[], options: FakePortOptions = {}) {
  const reads: string[] = [];
  let listCalls = 0;
  const port: ScanPort = {
    listFiles: async () => {
      listCalls += 1;
      if (options.listError) {
        throw new Error('listing failed');
      }
      return candidates;
    },
    readFile: async (candidate) => {
      reads.push(candidate.relativePath);
      if (options.results?.[candidate.relativePath]) {
        return options.results[candidate.relativePath];
      }
      if (options.contents?.[candidate.relativePath] !== undefined) {
        return { ok: true, content: options.contents[candidate.relativePath] };
      }
      return { ok: true, content: '' };
    },
    readRootFile: async (folderName, fileName) => options.rootFiles?.[folderName]?.[fileName],
  };
  return { port, reads, listCalls: () => listCalls };
}

describe('workspace scan runner', () => {
  it('handles an empty workspace', async () => {
    const { port } = fakePort([]);
    const result = await runScan({
      folders: ['fixture'],
      settings: makeSettings(),
      registry: createDefaultRegistry(),
      port,
    });

    expect(result.findings).toHaveLength(0);
    expect(result.filesScanned).toBe(0);
    expect(result.cancelled).toBe(false);
  });

  it('excludes dependencies, generated output, and unsupported files', async () => {
    const contents = {
      'src/app.js': 'const el = document.body; el.textContent = value;',
      'node_modules/pkg/index.js': 'eval(payload)',
      'dist/bundle.js': 'eval(payload)',
      'assets/logo.png': 'binary',
    };
    const candidates = Object.keys(contents).map((pathName) =>
      makeCandidate(pathName, bytes(contents[pathName as keyof typeof contents])),
    );
    const { port, reads } = fakePort(candidates, { contents });

    const result = await runScan({
      folders: ['fixture'],
      settings: makeSettings(),
      registry: createDefaultRegistry(),
      port,
    });

    expect(reads).toEqual(['src/app.js']);
    expect(result.filesScanned).toBe(1);
    expect(result.findings).toHaveLength(0);
  });

  it('skips files larger than the configured limit before reading', async () => {
    const content = 'const password = "synthetic-large-secret-123";';
    const { port, reads } = fakePort([makeCandidate('src/big.js', bytes(content))], {
      contents: { 'src/big.js': content },
    });

    const result = await runScan({
      folders: ['fixture'],
      settings: makeSettings({ maxFileSizeBytes: 10 }),
      registry: createDefaultRegistry(),
      port,
    });

    expect(reads).toHaveLength(0);
    expect(result.filesSkipped).toBe(1);
    expect(result.skipped[0]).toEqual({ relativePath: 'src/big.js', reason: 'too-large' });
  });

  it('handles binary, empty, and unreadable files without crashing', async () => {
    const candidates = [
      makeCandidate('src/binary.js', 20),
      makeCandidate('src/empty.js', 20),
      makeCandidate('src/unreadable.py', 20),
    ];
    const { port } = fakePort(candidates, {
      results: {
        'src/binary.js': { ok: false, reason: 'binary' },
        'src/empty.js': { ok: false, reason: 'empty' },
        'src/unreadable.py': { ok: false, reason: 'unreadable', detail: 'permission denied' },
      },
    });

    const result = await runScan({
      folders: ['fixture'],
      settings: makeSettings(),
      registry: createDefaultRegistry(),
      port,
    });

    expect(result.filesScanned).toBe(0);
    expect(result.filesSkipped).toBe(3);
    expect(result.errors).toBe(1);
    expect(result.findings).toHaveLength(0);
  });

  it('handles a project with no findings', async () => {
    const content = 'const value = 1;\nconst node = document.body;\nnode.textContent = value;\n';
    const candidates = [makeCandidate('src/safe.ts', bytes(content))];
    const { port } = fakePort(candidates, { contents: { 'src/safe.ts': content } });

    const result = await runScan({
      folders: ['fixture'],
      settings: makeSettings(),
      registry: createDefaultRegistry(),
      port,
    });

    expect(result.findings).toHaveLength(0);
    expect(result.filesScanned).toBe(1);
  });

  it('runs rules on actual content', async () => {
    const content = 'const password = "synthetic-runner-secret-123";\n';
    const candidates = [makeCandidate('src/config.js', bytes(content))];
    const { port } = fakePort(candidates, { contents: { 'src/config.js': content } });

    const result = await runScan({
      folders: ['fixture'],
      settings: makeSettings(),
      registry: createDefaultRegistry(),
      port,
    });

    expect(result.findings.some((finding) => finding.ruleId === 'RG001')).toBe(true);
  });

  it('passes the root gitignore to environment file checks', async () => {
    const content = 'SYNTHETIC_TOKEN=synthetic-env-runner-value\n';
    const candidates = [makeCandidate('.env', bytes(content))];
    const { port } = fakePort(candidates, {
      contents: { '.env': content },
      rootFiles: { fixture: { '.gitignore': 'node_modules/\n' } },
    });

    const result = await runScan({
      folders: ['fixture'],
      settings: makeSettings(),
      registry: createDefaultRegistry(),
      port,
    });

    expect(result.findings.some((finding) => finding.ruleId === 'RG007')).toBe(true);
  });

  it('supports cancellation before a scan starts', async () => {
    const controller = new AbortController();
    controller.abort();
    const { port, listCalls } = fakePort([]);

    const result = await runScan({
      folders: ['fixture'],
      settings: makeSettings(),
      registry: createDefaultRegistry(),
      port,
      signal: controller.signal,
    });

    expect(result.cancelled).toBe(true);
    expect(listCalls()).toBe(0);
  });

  it('supports cancellation between files', async () => {
    const candidates = [
      makeCandidate('src/a.js', 10),
      makeCandidate('src/b.js', 10),
      makeCandidate('src/c.js', 10),
    ];
    const controller = new AbortController();
    const progress: ScanProgress[] = [];
    const { port, reads } = fakePort(candidates, {
      contents: {
        'src/a.js': 'const a = 1;',
        'src/b.js': 'const b = 2;',
        'src/c.js': 'const c = 3;',
      },
    });

    const result = await runScan({
      folders: ['fixture'],
      settings: makeSettings(),
      registry: createDefaultRegistry(),
      port,
      signal: controller.signal,
      onProgress: (update) => {
        progress.push(update);
        if (update.processed === 1) {
          controller.abort();
        }
      },
    });

    expect(result.cancelled).toBe(true);
    expect(result.filesScanned).toBe(1);
    expect(reads).toEqual(['src/a.js']);
    expect(progress[0].total).toBe(3);
  });

  it('tolerates malformed text content', async () => {
    const content = 'const password = "synthetic-\uFFFD-secret-123";';
    const candidates = [makeCandidate('src/malformed.js', bytes(content))];
    const { port } = fakePort(candidates, { contents: { 'src/malformed.js': content } });

    const result = await runScan({
      folders: ['fixture'],
      settings: makeSettings(),
      registry: createDefaultRegistry(),
      port,
    });

    expect(result.filesScanned).toBe(1);
    expect(result.errors).toBe(0);
  });

  it('scans a single file with the same limits', async () => {
    const content = 'const password = "synthetic-single-file-secret-123";';
    const candidate = makeCandidate('src/single.js', bytes(content));
    const { port } = fakePort([candidate], { contents: { 'src/single.js': content } });

    const result = await runSingleFileScan({
      candidate,
      settings: makeSettings(),
      registry: createDefaultRegistry(),
      port,
    });
    expect(result.findings.some((finding) => finding.ruleId === 'RG001')).toBe(true);
    expect(result.filesScanned).toBe(1);

    const tooLarge = await runSingleFileScan({
      candidate,
      settings: makeSettings({ maxFileSizeBytes: 1 }),
      registry: createDefaultRegistry(),
      port,
    });
    expect(tooLarge.filesSkipped).toBe(1);
    expect(tooLarge.skipped[0].reason).toBe('too-large');
  });
});

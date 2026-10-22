import { describe, expect, it } from 'vitest';
import type { Finding } from '../src/models/types';
import {
  IGNORE_STORAGE_KEY,
  IgnoreStore,
  filterIgnoredFindings,
  ignoreKey,
  ignoredFromFinding,
  type MementoLike,
} from '../src/storage/ignoreStore';

class MemoryMemento implements MementoLike {
  readonly data = new Map<string, unknown>();

  get<T>(key: string, defaultValue: T): T | undefined {
    return this.data.has(key) ? (this.data.get(key) as T) : defaultValue;
  }

  async update(key: string, value: unknown): Promise<void> {
    this.data.set(key, value);
  }
}

function makeFinding(overrides: Partial<Finding> = {}): Finding {
  return {
    id: 'RG001:src/app.js:abc123',
    ruleId: 'RG001',
    ruleTitle: 'Potential Hardcoded Credential',
    severity: 'high',
    message: 'Possible hardcoded credential. The value is redacted.',
    explanation: 'explanation',
    whyRisky: 'risk',
    remediation: 'remediation',
    limitations: 'limitations',
    references: [],
    relativePath: 'src/app.js',
    absolutePath: 'C:/fixture/src/app.js',
    workspaceFolder: 'fixture',
    fileName: 'app.js',
    line: 4,
    column: 10,
    endLine: 4,
    endColumn: 20,
    fingerprint: 'abc123',
    maskedSnippet: 'const password = "[REDACTED]";',
    ...overrides,
  };
}

describe('ignore store', () => {
  it('adds and detects an ignored finding', async () => {
    const memento = new MemoryMemento();
    const store = new IgnoreStore(memento, () => new Date('2026-01-02T03:04:05Z'));
    const finding = makeFinding();

    await store.add(finding);
    expect(store.isFindingIgnored(finding)).toBe(true);
    expect(store.list()[0].ignoredAt).toBe('2026-01-02T03:04:05.000Z');
    expect(store.list()[0].maskedSnippet).not.toContain('synthetic');
  });

  it('persists ignores across store instances', async () => {
    const memento = new MemoryMemento();
    const finding = makeFinding();
    await new IgnoreStore(memento).add(finding);

    const reloaded = new IgnoreStore(memento);
    expect(reloaded.isFindingIgnored(finding)).toBe(true);
    expect(reloaded.list()).toHaveLength(1);
    expect((memento.data.get(IGNORE_STORAGE_KEY) as { version: number }).version).toBe(1);
  });

  it('keeps ignores scoped to one rule, path, and fingerprint', async () => {
    const store = new IgnoreStore(new MemoryMemento());
    const finding = makeFinding();
    const otherPath = makeFinding({
      id: 'RG001:src/other.js:abc123',
      relativePath: 'src/other.js',
    });
    const otherRule = makeFinding({
      id: 'RG002:src/app.js:abc123',
      ruleId: 'RG002',
    });

    await store.add(finding);
    expect(store.isFindingIgnored(finding)).toBe(true);
    expect(store.isFindingIgnored(otherPath)).toBe(false);
    expect(store.isFindingIgnored(otherRule)).toBe(false);
  });

  it('keeps identity stable when line numbers change', async () => {
    const store = new IgnoreStore(new MemoryMemento());
    const finding = makeFinding();
    await store.add(finding);

    expect(store.isFindingIgnored(makeFinding({ line: 99, column: 1 }))).toBe(true);
  });

  it('restores an ignored finding', async () => {
    const memento = new MemoryMemento();
    const store = new IgnoreStore(memento);
    const finding = makeFinding();
    await store.add(finding);
    const item = store.list()[0];

    await store.restore(item);
    expect(store.isFindingIgnored(finding)).toBe(false);
    expect(store.list()).toHaveLength(0);

    await store.add(finding);
    await store.remove(store.list()[0]);
    expect(store.list()).toHaveLength(0);
    expect(item.fingerprint).toBe('abc123');
  });

  it('filters ignored findings from a result set', async () => {
    const store = new IgnoreStore(new MemoryMemento());
    const kept = makeFinding({
      id: 'kept',
      relativePath: 'src/kept.js',
      fingerprint: 'kept-fp',
    });
    const ignored = makeFinding({
      id: 'ignored',
      relativePath: 'src/ignored.js',
      fingerprint: 'ignored-fp',
    });
    await store.add(ignored);
    expect(filterIgnoredFindings([kept, ignored], store)).toEqual([kept]);
  });

  it('drops malformed persisted records', () => {
    const memento = new MemoryMemento();
    memento.data.set(IGNORE_STORAGE_KEY, {
      version: 1,
      items: [
        { ruleId: 'RG001' },
        {
          ruleId: 'RG001',
          ruleTitle: 'Title',
          severity: 'high',
          relativePath: 'src/a.js',
          fingerprint: 'f',
          maskedSnippet: 'masked',
          ignoredAt: '2026-01-01T00:00:00.000Z',
        },
      ],
    });

    expect(new IgnoreStore(memento).list()).toHaveLength(1);
  });

  it('builds deterministic ignore keys', () => {
    expect(ignoreKey('RG001', 'src/a.js', 'fp')).toBe('RG001|src/a.js|fp');
    expect(ignoredFromFinding(makeFinding()).ruleId).toBe('RG001');
  });
});

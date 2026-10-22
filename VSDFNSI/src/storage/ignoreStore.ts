import type { Finding, IgnoredFinding } from '../models/types';
import { isSeverity } from '../models/severity';

export interface MementoLike {
  get<T>(key: string, defaultValue: T): T | undefined;
  update(key: string, value: unknown): Thenable<void>;
}

export const IGNORE_STORAGE_KEY = 'repoguard.ignoredFindings.v1';
const MAX_IGNORED_ITEMS = 5000;

export function ignoreKey(ruleId: string, relativePath: string, fingerprint: string): string {
  return `${ruleId}|${relativePath}|${fingerprint}`;
}

export function ignoredFromFinding(finding: Finding, now = new Date()): IgnoredFinding {
  return {
    ruleId: finding.ruleId,
    ruleTitle: finding.ruleTitle,
    severity: finding.severity,
    relativePath: finding.relativePath,
    fingerprint: finding.fingerprint,
    maskedSnippet: finding.maskedSnippet,
    ignoredAt: now.toISOString(),
  };
}

function isValidIgnored(value: unknown): value is IgnoredFinding {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const item = value as Record<string, unknown>;
  return (
    typeof item.ruleId === 'string' &&
    typeof item.ruleTitle === 'string' &&
    isSeverity(item.severity) &&
    typeof item.relativePath === 'string' &&
    typeof item.fingerprint === 'string' &&
    typeof item.maskedSnippet === 'string' &&
    typeof item.ignoredAt === 'string'
  );
}

export class IgnoreStore {
  private loaded = false;
  private items: IgnoredFinding[] = [];

  constructor(
    private readonly memento: MementoLike,
    private readonly now: () => Date = () => new Date(),
  ) {}

  private load(): void {
    if (this.loaded) {
      return;
    }
    this.loaded = true;
    const raw = this.memento.get<unknown>(IGNORE_STORAGE_KEY, undefined);
    if (Array.isArray(raw)) {
      this.items = raw.filter(isValidIgnored);
      return;
    }
    if (raw && typeof raw === 'object') {
      const record = raw as Record<string, unknown>;
      if (record.version === 1 && Array.isArray(record.items)) {
        this.items = record.items.filter(isValidIgnored);
      }
    }
  }

  private async persist(): Promise<void> {
    const unique = new Map<string, IgnoredFinding>();
    for (const item of this.items) {
      unique.set(ignoreKey(item.ruleId, item.relativePath, item.fingerprint), item);
    }
    this.items = [...unique.values()].slice(-MAX_IGNORED_ITEMS);
    await this.memento.update(IGNORE_STORAGE_KEY, {
      version: 1,
      items: this.items,
    });
  }

  list(): IgnoredFinding[] {
    this.load();
    return [...this.items];
  }

  isIgnored(ruleId: string, relativePath: string, fingerprint: string): boolean {
    this.load();
    const key = ignoreKey(ruleId, relativePath, fingerprint);
    return this.items.some(
      (item) => ignoreKey(item.ruleId, item.relativePath, item.fingerprint) === key,
    );
  }

  isFindingIgnored(finding: Finding): boolean {
    return this.isIgnored(finding.ruleId, finding.relativePath, finding.fingerprint);
  }

  async add(finding: Finding): Promise<void> {
    this.load();
    if (this.isFindingIgnored(finding)) {
      return;
    }
    this.items.push(ignoredFromFinding(finding, this.now()));
    await this.persist();
  }

  async remove(item: IgnoredFinding): Promise<void> {
    this.load();
    const key = ignoreKey(item.ruleId, item.relativePath, item.fingerprint);
    const next = this.items.filter(
      (candidate) =>
        ignoreKey(candidate.ruleId, candidate.relativePath, candidate.fingerprint) !== key,
    );
    if (next.length === this.items.length) {
      return;
    }
    this.items = next;
    await this.persist();
  }

  async restore(item: IgnoredFinding): Promise<void> {
    await this.remove(item);
  }

  async clear(): Promise<void> {
    this.load();
    this.items = [];
    await this.persist();
  }
}

export function filterIgnoredFindings(findings: readonly Finding[], store: IgnoreStore): Finding[] {
  return findings.filter((finding) => !store.isFindingIgnored(finding));
}

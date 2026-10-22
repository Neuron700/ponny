import type {
  Finding,
  RuleContext,
  RuleDefinition,
  RuleFileInfo,
  RuleMatch,
  ScannerSettings,
} from '../models/types';
import { findingId, shortFingerprint } from '../utils/hash';
import { redactSecrets } from '../utils/masking';
import { normalizeSeed, splitLines } from '../utils/text';
import { ruleAppliesToFile } from '../rules/helpers';
import type { RuleRegistry } from './registry';

export type EngineFileInfo = RuleFileInfo;

interface NormalizedMatch extends RuleMatch {
  endLine: number;
  endColumn: number;
}

export interface EvaluateOptions {
  settings: ScannerSettings;
  rootFileContents?: Readonly<Record<string, string | undefined>>;
}

export function activeRules(registry: RuleRegistry, settings: ScannerSettings): RuleDefinition[] {
  const enabled = new Set(settings.enabledRules.map((id) => id.trim().toUpperCase()));
  const disabled = new Set(settings.disabledRules.map((id) => id.trim().toUpperCase()));

  return registry.all().filter((rule) => {
    if (disabled.has(rule.id.toUpperCase())) {
      return false;
    }
    if (enabled.size > 0 && !enabled.has(rule.id.toUpperCase())) {
      return false;
    }
    return true;
  });
}

function normalizeMatch(match: RuleMatch): NormalizedMatch {
  const endLine = match.endLine ?? match.line;
  const endColumn = match.endColumn ?? match.column + 1;
  return {
    ...match,
    endLine,
    endColumn: endLine === match.line && endColumn <= match.column ? match.column + 1 : endColumn,
  };
}

export function evaluateContent(
  file: EngineFileInfo,
  content: string,
  registry: RuleRegistry,
  options: EvaluateOptions,
): Finding[] {
  const lines = splitLines(content);
  const context: RuleContext = {
    file,
    content,
    lines,
    rootFileContents: options.rootFileContents ?? {},
  };
  const findings: Finding[] = [];
  const occurrence = new Map<string, number>();

  for (const rule of activeRules(registry, options.settings)) {
    if (!ruleAppliesToFile(rule, file)) {
      continue;
    }

    let matches: RuleMatch[];
    try {
      matches = rule.detect(context);
    } catch {
      continue;
    }

    for (const rawMatch of matches) {
      const match = normalizeMatch(rawMatch);
      const seed = `${rule.id}\n${normalizeSeed(match.fingerprintSeed)}\n${normalizeSeed(match.message)}`;
      const count = (occurrence.get(seed) ?? 0) + 1;
      occurrence.set(seed, count);
      const fingerprint = shortFingerprint(`${seed}\n${count}`);

      findings.push({
        id: findingId(rule.id, file.relativePath, fingerprint),
        ruleId: rule.id,
        ruleTitle: rule.title,
        severity: rule.severity,
        message: redactSecrets(match.message),
        explanation: rule.explanation,
        whyRisky: rule.whyRisky,
        remediation: rule.remediation,
        limitations: rule.limitations,
        references: rule.references ?? [],
        relativePath: file.relativePath,
        absolutePath: file.absolutePath,
        workspaceFolder: file.workspaceFolder,
        fileName: file.fileName,
        line: match.line,
        column: match.column,
        endLine: match.endLine,
        endColumn: match.endColumn,
        fingerprint,
        maskedSnippet: redactSecrets(match.snippet ?? ''),
      });
    }
  }

  return findings;
}

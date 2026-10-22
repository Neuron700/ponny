import type { RuleDefinition } from '../models/types';
import { isEnvFileName } from '../utils/paths';
import { isPlaceholderValue, redactSecrets } from '../utils/masking';
import { normalizeSeed } from '../utils/text';
import { findLineHits, SOURCE_EXTENSIONS, trimSnippet } from './helpers';

const SENSITIVE_NAMES =
  'api[_-]?key|apikey|secret|client[_-]?secret|password|passwd|pwd|auth[_-]?token|access[_-]?token|refresh[_-]?token|private[_-]?key|token';

const QUOTED_ASSIGNMENT = new RegExp(
  `\\b(${SENSITIVE_NAMES})\\b["']?\\s*(?::\\s*[A-Za-z_][\\w[\\]<>|., ]{0,40}?\\s*)?[:=]\\s*(['"\`])([^'"\`\\r\\n]{8,})\\2`,
  'gi',
);

const ENV_ASSIGNMENT = new RegExp(
  '^\\s*(?:export\\s+)?([A-Z0-9_]*(?:PASSWORD|PASSWD|PWD|SECRET|TOKEN|API_?KEY|ACCESS_?KEY|PRIVATE_?KEY)[A-Z0-9_]*)\\s*=\\s*([^\\s#]{8,})\\s*$',
  'i',
);

function isComment(line: string): boolean {
  const trimmed = line.trimStart();
  return trimmed.startsWith('//') || trimmed.startsWith('#') || trimmed.startsWith('/*');
}

function snippetFor(line: string): string {
  return trimSnippet(redactSecrets(line));
}

export const rg001HardcodedCredentials: RuleDefinition = {
  id: 'RG001',
  title: 'Potential Hardcoded Credential',
  severity: 'high',
  explanation:
    'A secret-like key name is assigned a literal string value. RepoGuard flags the assignment pattern, not a verified credential.',
  whyRisky:
    'Credentials committed to source control can be copied from history, shared accidentally, or exposed in build artifacts. Rotating a leaked secret is often harder than removing it, so the risk extends beyond the current file.',
  remediation:
    'Move the value into an environment variable or a local secret manager, load it at runtime, and rotate the exposed value if it was ever committed or shared. Remove the literal from source history where appropriate.',
  limitations:
    'This is a pattern match. Placeholder strings, test values, and values composed at runtime may be reported or missed. The matched value is never displayed or exported.',
  references: ['OWASP Top 10 A07: Identification and Authentication Failures'],
  fileExtensions: SOURCE_EXTENSIONS,
  scanEnvFiles: true,
  detect(context) {
    const matches = [];
    const seenLines = new Set<number>();

    for (const hit of findLineHits(context.lines, QUOTED_ASSIGNMENT)) {
      if (isComment(hit.lineText)) {
        continue;
      }
      const value = hit.text.replace(/^.*?[:=]\s*['"`]/, '').replace(/['"`]$/, '');
      if (isPlaceholderValue(value)) {
        continue;
      }
      seenLines.add(hit.line);
      matches.push({
        line: hit.line,
        column: hit.column,
        endLine: hit.line,
        endColumn: hit.endColumn,
        message: `Possible hardcoded credential assigned to "${hit.text.match(/^[^:=\s]+/)?.[0] ?? 'secret'}". The value is redacted.`,
        fingerprintSeed: normalizeSeed(redactSecrets(hit.lineText)),
        snippet: snippetFor(hit.lineText),
      });
    }

    if (isEnvFileName(context.file.fileName)) {
      for (let index = 0; index < context.lines.length; index += 1) {
        const line = context.lines[index];
        if (seenLines.has(index + 1) || isComment(line)) {
          continue;
        }
        const envMatch = ENV_ASSIGNMENT.exec(line);
        if (!envMatch) {
          continue;
        }
        const key = envMatch[1];
        const rawValue = envMatch[2].replace(/^['"]|['"]$/g, '');
        if (isPlaceholderValue(rawValue)) {
          continue;
        }
        const column = line.indexOf(envMatch[1]) + 1;
        matches.push({
          line: index + 1,
          column,
          endLine: index + 1,
          endColumn: column + envMatch[0].length,
          message: `Possible hardcoded credential assigned to "${key}". The value is redacted.`,
          fingerprintSeed: normalizeSeed(redactSecrets(line)),
          snippet: snippetFor(line),
        });
      }
    }

    return matches;
  },
};

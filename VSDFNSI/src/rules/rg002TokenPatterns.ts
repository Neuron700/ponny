import type { RuleDefinition, RuleMatch } from '../models/types';
import { redactSecrets } from '../utils/masking';
import { normalizeSeed } from '../utils/text';
import { findLineHits, trimSnippet } from './helpers';

interface TokenPattern {
  name: string;
  pattern: RegExp;
}

const TOKEN_PATTERNS: readonly TokenPattern[] = [
  {
    name: 'GitHub personal access token',
    pattern: /\bgh[pousr]_[A-Za-z0-9]{20,}\b/g,
  },
  {
    name: 'GitHub fine-grained personal access token',
    pattern: /\bgithub_pat_[A-Za-z0-9_]{20,}\b/g,
  },
  {
    name: 'AWS access key ID',
    pattern: /\bAKIA[0-9A-Z]{12,}\b/g,
  },
  {
    name: 'Stripe live secret key',
    pattern: /\bsk_live_[A-Za-z0-9]{10,}\b/g,
  },
  {
    name: 'Google API key',
    pattern: /\bAIza[0-9A-Za-z_-]{20,}\b/g,
  },
  {
    name: 'Slack token',
    pattern: /\bxox[baprs]-[A-Za-z0-9-]{10,}\b/g,
  },
];

export const rg002TokenPatterns: RuleDefinition = {
  id: 'RG002',
  title: 'Recognizable Token Pattern',
  severity: 'high',
  explanation:
    'A string matching the documented format of a well-known access token was found. RepoGuard supports a small, deliberately scoped set of token formats.',
  whyRisky:
    'If the value is a live token, anyone with read access to the repository, logs, or generated artifacts may be able to use it. Even example tokens can be mistaken for real ones and copied into other projects.',
  remediation:
    'Remove the token from the file, revoke or rotate it with the provider if there is any chance it was valid, and load credentials from a local secret store or environment variable instead.',
  limitations:
    'Format-only detection cannot prove validity. RepoGuard intentionally supports only a few providers and will miss other token formats. Synthetic or expired tokens with matching shapes can still be reported.',
  references: ['Provider token format documentation'],
  fileExtensions: '*',
  detect(context) {
    const matches: RuleMatch[] = [];

    for (const tokenPattern of TOKEN_PATTERNS) {
      for (const hit of findLineHits(context.lines, tokenPattern.pattern)) {
        const line = hit.lineText;
        matches.push({
          line: hit.line,
          column: hit.column,
          endLine: hit.line,
          endColumn: hit.endColumn,
          message: `A value matching the ${tokenPattern.name} format was found. The value is redacted.`,
          fingerprintSeed: `${tokenPattern.name}|${normalizeSeed(redactSecrets(line))}`,
          snippet: trimSnippet(redactSecrets(line)),
        });
      }
    }

    return matches;
  },
};

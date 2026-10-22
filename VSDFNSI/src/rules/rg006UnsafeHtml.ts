import type { RuleDefinition } from '../models/types';
import { redactSecrets } from '../utils/masking';
import { isCommentLine, normalizeSeed } from '../utils/text';
import { findLineHits, JS_TS_EXTENSIONS, trimSnippet } from './helpers';

const HTML_SINK_PATTERNS: readonly { name: string; pattern: RegExp }[] = [
  { name: 'innerHTML', pattern: /\.innerHTML\s*\+?=/g },
  { name: 'outerHTML', pattern: /\.outerHTML\s*\+?=/g },
  { name: 'insertAdjacentHTML', pattern: /\.insertAdjacentHTML\s*\(/g },
];

function assignsEmptyString(line: string, endColumn: number): boolean {
  const remainder = line.slice(Math.max(0, endColumn - 1));
  return /^\s*(['"`])\s*\1\s*;?\s*$/.test(remainder);
}

export const rg006UnsafeHtmlInjection: RuleDefinition = {
  id: 'RG006',
  title: 'Potentially Unsafe HTML Injection',
  severity: 'medium',
  explanation:
    'A direct HTML sink was assigned in JavaScript or TypeScript. The actual risk depends on whether untrusted input can reach that assignment.',
  whyRisky:
    'Assigning strings to innerHTML or outerHTML parses them as HTML. If attacker-controlled content reaches the sink, script or markup injection may be possible. Framework escaping does not apply when these DOM properties are used directly.',
  remediation:
    'Prefer textContent for plain text. When HTML is required, sanitize it with a maintained allowlist-based sanitizer or use the framework’s safe rendering path. Avoid string concatenation into HTML sinks.',
  limitations:
    'The rule detects selected DOM sinks and does not perform data-flow analysis. Constant markup, trusted templates, and values already sanitized can be reported as false positives. Other DOM APIs and template engines are not covered.',
  references: ['OWASP Cross Site Scripting Prevention Cheat Sheet'],
  fileExtensions: JS_TS_EXTENSIONS,
  detect(context) {
    const matches = [];
    for (const sink of HTML_SINK_PATTERNS) {
      for (const hit of findLineHits(context.lines, sink.pattern)) {
        if (isCommentLine(hit.lineText)) {
          continue;
        }
        if (sink.name !== 'insertAdjacentHTML' && assignsEmptyString(hit.lineText, hit.endColumn)) {
          continue;
        }
        matches.push({
          line: hit.line,
          column: hit.column,
          endLine: hit.line,
          endColumn: hit.endColumn,
          message: `Direct ${sink.name} assignment is potentially risky. Review whether untrusted input can reach it.`,
          fingerprintSeed: `${sink.name}|${normalizeSeed(redactSecrets(hit.lineText))}`,
          snippet: trimSnippet(redactSecrets(hit.lineText)),
        });
      }
    }
    return matches;
  },
};

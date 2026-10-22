import type { RuleDefinition } from '../models/types';
import { redactSecrets } from '../utils/masking';
import { normalizeSeed } from '../utils/text';
import { findLineHits, SOURCE_EXTENSIONS, trimSnippet } from './helpers';

interface TlsPattern {
  label: string;
  pattern: RegExp;
}

const TLS_PATTERNS: readonly TlsPattern[] = [
  { label: 'Python `verify=False`', pattern: /\bverify\s*=\s*False\b/g },
  { label: 'Python `verify_ssl=False`', pattern: /\bverify_ssl\s*=\s*False\b/g },
  { label: 'Python `ssl_verify=False`', pattern: /\bssl_verify\s*=\s*False\b/g },
  {
    label: 'Node.js `rejectUnauthorized: false`',
    pattern: /\brejectUnauthorized\s*:\s*false\b/g,
  },
  {
    label: 'Node.js `NODE_TLS_REJECT_UNAUTHORIZED=0`',
    pattern: /\bNODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['"]?0['"]?/g,
  },
  { label: 'Node.js `strictSSL: false`', pattern: /\bstrictSSL\s*:\s*false\b/g },
  { label: 'Go `InsecureSkipVerify: true`', pattern: /\bInsecureSkipVerify\s*:\s*true\b/g },
  {
    label: 'libcurl `CURLOPT_SSL_VERIFYPEER` disabled',
    pattern: /\bCURLOPT_SSL_VERIFYPEER\s*,\s*(?:false|0)\b/gi,
  },
];

export const rg004InsecureTls: RuleDefinition = {
  id: 'RG004',
  title: 'Insecure TLS Verification',
  severity: 'high',
  explanation:
    'A configuration that appears to disable TLS certificate verification was found. The real impact depends on which connection uses it and what data crosses that connection.',
  whyRisky:
    'Disabling certificate verification removes protection against impersonation and man-in-the-middle attacks. The code may be intentional for a local development server, but the same setting in production exposes traffic to interception.',
  remediation:
    'Re-enable certificate verification. If a private certificate authority is required, configure a trusted CA bundle instead of disabling verification. Keep development-only overrides out of production configuration.',
  limitations:
    'Pattern matching cannot establish whether the setting is reachable in production or limited to tests. Wrappers, constants, and framework-specific options may not be detected.',
  references: ['OWASP Transport Layer Security Cheat Sheet'],
  fileExtensions: SOURCE_EXTENSIONS,
  scanEnvFiles: true,
  detect(context) {
    const matches = [];
    for (const tlsPattern of TLS_PATTERNS) {
      for (const hit of findLineHits(context.lines, tlsPattern.pattern)) {
        matches.push({
          line: hit.line,
          column: hit.column,
          endLine: hit.line,
          endColumn: hit.endColumn,
          message: `TLS certificate verification appears to be disabled (${tlsPattern.label}).`,
          fingerprintSeed: `${tlsPattern.label}|${normalizeSeed(redactSecrets(hit.lineText))}`,
          snippet: trimSnippet(redactSecrets(hit.lineText)),
        });
      }
    }
    return matches;
  },
};

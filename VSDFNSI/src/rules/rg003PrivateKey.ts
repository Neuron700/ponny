import type { RuleDefinition } from '../models/types';
import { redactSecrets } from '../utils/masking';
import { normalizeSeed } from '../utils/text';
import { findLineHits, trimSnippet } from './helpers';

const PRIVATE_KEY_MARKER = /-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY(?: BLOCK)?-----/g;

export const rg003PrivateKeyMaterial: RuleDefinition = {
  id: 'RG003',
  title: 'Private Key Material',
  severity: 'critical',
  explanation:
    'A PEM-style private key block marker was found in a text file. The key material itself is never displayed or exported.',
  whyRisky:
    'A private key can authenticate a server, sign artifacts, or decrypt traffic. If it is committed, the identity it protects should be treated as compromised because copies may remain in history, caches, and forks.',
  remediation:
    'Remove the key from the file and repository history, revoke it at the issuing authority, generate a replacement, and store the replacement outside the repository with restrictive permissions.',
  limitations:
    'The rule detects BEGIN/END markers in scanned text files. Keys without standard markers, binary key stores, or key material in unsupported file types are not detected.',
  references: ['OpenSSL PEM private key format', 'OWASP Secrets Management Cheat Sheet'],
  fileExtensions: '*',
  detect(context) {
    return findLineHits(context.lines, PRIVATE_KEY_MARKER).map((hit) => ({
      line: hit.line,
      column: hit.column,
      endLine: hit.line,
      endColumn: hit.endColumn,
      message: 'Private key block marker found. Key material is intentionally not displayed.',
      fingerprintSeed: `private-key|${normalizeSeed(redactSecrets(hit.lineText))}`,
      snippet: trimSnippet(redactSecrets(hit.lineText)),
    }));
  },
};

import { createHash } from 'node:crypto';

const PLACEHOLDER_VALUES = [
  'changeme',
  'change-me',
  'change_me',
  'placeholder',
  'example',
  'sample',
  'dummy',
  'fake',
  'notasecret',
  'not-a-secret',
  'your-password',
  'your_password',
  'your-secret',
  'your_secret',
  'your-api-key',
  'your_api_key',
  'xxx',
  'redacted',
  'password',
  'secret',
  'apikey',
  'token',
];

const KNOWN_TOKEN_PATTERNS: readonly RegExp[] = [
  /\b(gh[pousr]_[A-Za-z0-9]{20,})\b/g,
  /\b(github_pat_[A-Za-z0-9_]{20,})\b/g,
  /\b(AKIA[0-9A-Z]{12,})\b/g,
  /\b(sk_live_[A-Za-z0-9]{10,})\b/g,
  /\b(AIza[0-9A-Za-z_-]{20,})\b/g,
  /\b(xox[baprs]-[A-Za-z0-9-]{10,})\b/g,
];

const SENSITIVE_KEY =
  '(?:api[_-]?key|apikey|secret|client[_-]?secret|password|passwd|pwd|auth[_-]?token|access[_-]?token|refresh[_-]?token|private[_-]?key|token)';

const ASSIGNMENT_PATTERN = new RegExp(
  `(${SENSITIVE_KEY}\\b["']?\\s*[:=]\\s*)(['"\`])([^'"\`\\r\\n]+)\\2`,
  'gi',
);

const ENV_ASSIGNMENT_PATTERN = new RegExp(
  `^([A-Z0-9_]*(?:API[_-]?KEY|SECRET|PASSWORD|PASSWD|PWD|TOKEN|ACCESS[_-]?KEY|PRIVATE[_-]?KEY)[A-Z0-9_]*)\\s*=\\s*(.+)$`,
  'i',
);

const PEM_BLOCK_PATTERN =
  /-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----/g;

export const REDACTED = '[REDACTED]';

export function isPlaceholderValue(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  if (
    normalized.startsWith('${') ||
    normalized.startsWith('$') ||
    normalized.startsWith('{{') ||
    normalized.startsWith('<') ||
    normalized.startsWith('%') ||
    normalized === 'null' ||
    normalized === 'undefined' ||
    normalized === 'none'
  ) {
    return true;
  }
  if (PLACEHOLDER_VALUES.includes(normalized)) {
    return true;
  }
  if (
    normalized.startsWith('your_') ||
    normalized.startsWith('your-') ||
    normalized.startsWith('example') ||
    normalized.startsWith('sample') ||
    normalized.startsWith('dummy') ||
    normalized.startsWith('fake') ||
    normalized.startsWith('redacted') ||
    normalized.includes('changeme') ||
    normalized.includes('placeholder') ||
    normalized.includes('not-a-secret') ||
    normalized.includes('not_a_secret')
  ) {
    return true;
  }
  if (/^x+$/i.test(normalized) || /^\*+$/.test(normalized) || /^\.+$/.test(normalized)) {
    return true;
  }
  return false;
}

export function maskSecret(): string {
  return REDACTED;
}

export function redactSecrets(text: string): string {
  if (!text) {
    return text;
  }

  let output = text;
  for (const pattern of KNOWN_TOKEN_PATTERNS) {
    output = output.replace(pattern, REDACTED);
  }

  output = output.replace(ASSIGNMENT_PATTERN, (_match, prefix: string, quote: string) => {
    return `${prefix}${quote}${REDACTED}${quote}`;
  });

  output = output.replace(ENV_ASSIGNMENT_PATTERN, (match, key: string, value: string) => {
    const trimmed = value.trim();
    if (!trimmed || trimmed.startsWith('#') || trimmed.startsWith('$')) {
      return match;
    }
    return `${key}=${REDACTED}`;
  });

  output = output.replace(PEM_BLOCK_PATTERN, REDACTED);

  return output;
}

export function snippetFingerprintSeed(line: string): string {
  const redacted = redactSecrets(line).replace(/\s+/g, ' ').trim();
  return createHash('sha256').update(redacted, 'utf8').digest('hex').slice(0, 24);
}

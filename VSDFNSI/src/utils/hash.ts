import { createHash } from 'node:crypto';

export function sha256Hex(value: string): string {
  return createHash('sha256').update(value, 'utf8').digest('hex');
}

export function shortFingerprint(seed: string, length = 16): string {
  return sha256Hex(seed).slice(0, length);
}

export function findingId(ruleId: string, relativePath: string, fingerprint: string): string {
  return `${ruleId}:${relativePath}:${fingerprint}`;
}

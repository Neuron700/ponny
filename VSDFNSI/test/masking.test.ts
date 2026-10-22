import { describe, expect, it } from 'vitest';
import {
  isPlaceholderValue,
  maskSecret,
  redactSecrets,
  snippetFingerprintSeed,
} from '../src/utils/masking';
import { isEnvFileIgnored } from '../src/utils/gitignore';

describe('secret masking', () => {
  it('masks quoted assignments', () => {
    const redacted = redactSecrets('const apiKey = "synthetic-value-123456";');
    expect(redacted).toContain('[REDACTED]');
    expect(redacted).not.toContain('synthetic-value-123456');
  });

  it('masks JSON-style assignments', () => {
    const redacted = redactSecrets('{"password": "synthetic-json-secret"}');
    expect(redacted).not.toContain('synthetic-json-secret');
  });

  it('masks unquoted environment assignments', () => {
    const redacted = redactSecrets('API_KEY=synthetic-env-secret');
    expect(redacted).toBe('API_KEY=[REDACTED]');
  });

  it('masks known token formats', () => {
    const redacted = redactSecrets('token=ghp_fake0123456789abcdef and AKIAFAKE12345678');
    expect(redacted).not.toContain('ghp_fake0123456789');
    expect(redacted).not.toContain('AKIAFAKE12345678');
    expect(redacted).toContain('[REDACTED]');
  });

  it('masks complete PEM private key blocks', () => {
    const begin = ['-----BEGIN', 'RSA', 'PRIVATE KEY-----'].join(' ');
    const end = ['-----END', 'RSA', 'PRIVATE KEY-----'].join(' ');
    const redacted = redactSecrets(`before\n${begin}\nsyntheticmaterial\n${end}\nafter`);
    expect(redacted).not.toContain('syntheticmaterial');
    expect(redacted).toContain('before');
    expect(redacted).toContain('after');
  });

  it('recognizes placeholders without hiding plausible values', () => {
    for (const value of [
      'changeme',
      'your_api_key_here',
      '${SECRET}',
      '{{secret}}',
      'xxxxx',
      'example-value',
      '',
    ]) {
      expect(isPlaceholderValue(value)).toBe(true);
    }
    expect(isPlaceholderValue('S3cret-Realistic-Value!')).toBe(false);
    expect(isPlaceholderValue('latest-token-123456')).toBe(false);
  });

  it('masks values completely', () => {
    expect(maskSecret()).toBe('[REDACTED]');
  });

  it('fingerprint seeds are stable and exclude raw secret values', () => {
    const first = snippetFingerprintSeed('const password = "synthetic-one";');
    const second = snippetFingerprintSeed('const password = "synthetic-two";');
    expect(first).toBe(second);
    expect(first).not.toContain('synthetic-one');
  });
});

describe('gitignore environment matching', () => {
  it('matches common env ignore patterns', () => {
    expect(isEnvFileIgnored('.env\n', '.env', '.env')).toBe(true);
    expect(isEnvFileIgnored('.env*\n', '.env.local', '.env.local')).toBe(true);
    expect(isEnvFileIgnored('*.env\n', 'prod.env', 'config/prod.env')).toBe(true);
    expect(isEnvFileIgnored('**/.env\n', '.env', 'config/.env')).toBe(true);
  });

  it('does not match unrelated patterns', () => {
    expect(isEnvFileIgnored('node_modules/\ndist/\n', '.env', '.env')).toBe(false);
    expect(isEnvFileIgnored(undefined, '.env', '.env')).toBe(false);
    expect(isEnvFileIgnored('# .env\n', '.env', '.env')).toBe(false);
  });

  it('honors later negated patterns', () => {
    expect(isEnvFileIgnored('.env*\n!.env.example\n', '.env.example', '.env.example')).toBe(false);
    expect(isEnvFileIgnored('.env*\n', '.env.example', '.env.example')).toBe(true);
  });

  it('handles a root-anchored .env pattern', () => {
    expect(isEnvFileIgnored('/.env\n', '.env', '.env')).toBe(true);
  });
});

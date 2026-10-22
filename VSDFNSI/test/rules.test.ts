import { describe, expect, it } from 'vitest';
import { byRule, evaluateContentAs, evaluateFixture } from './helpers';
import { readFixture } from './helpers';

describe('RG001 hardcoded credentials', () => {
  it('detects literal assignments but never exposes the values', () => {
    const findings = byRule(evaluateFixture('rules/rg001-positive.js'), 'RG001');
    expect(findings).toHaveLength(3);

    const raw = readFixture('rules/rg001-positive.js');
    for (const finding of findings) {
      expect(finding.message).not.toContain('synthetic-api-key-0123456789');
      expect(finding.message).not.toContain('S3cret-Synthetic-Value!');
      expect(finding.message).not.toContain('synthetic-token-abcdef123456');
      expect(finding.maskedSnippet).toContain('[REDACTED]');
    }
    expect(JSON.stringify(findings)).not.toContain('S3cret-Synthetic-Value!');
    expect(raw).toContain('synthetic-api-key-0123456789');
  });

  it('ignores environment references and placeholders', () => {
    expect(byRule(evaluateFixture('rules/rg001-negative.js'), 'RG001')).toHaveLength(0);
    expect(byRule(evaluateFixture('rules/rg001-negative.env'), 'RG001')).toHaveLength(0);
  });

  it('detects quoted and unquoted environment assignments', () => {
    expect(byRule(evaluateFixture('rules/rg001-positive.env'), 'RG001')).toHaveLength(3);
  });

  it('skips comment lines', () => {
    const findings = byRule(
      evaluateFixture('rules/rg001-negative.js', {
        settings: undefined,
      }),
      'RG001',
    );
    expect(findings).toHaveLength(0);
  });
});

describe('RG002 recognizable token patterns', () => {
  it('detects supported synthetic token formats', () => {
    const findings = byRule(evaluateFixture('rules/rg002-positive.js'), 'RG002');
    expect(findings).toHaveLength(5);
    expect(findings.map((finding) => finding.message).join(' ')).toContain('GitHub');
    expect(JSON.stringify(findings)).not.toContain('ghp_synthetic0123456789abcd');
  });

  it('does not report short or test-mode token shapes', () => {
    expect(byRule(evaluateFixture('rules/rg002-negative.js'), 'RG002')).toHaveLength(0);
  });
});

describe('RG003 private key material', () => {
  it('detects a private key block without including key material', () => {
    const keyMaterial = 'synthetic-key-material-for-testing-only';
    const begin = ['-----BEGIN', 'RSA', 'PRIVATE KEY-----'].join(' ');
    const end = ['-----END', 'RSA', 'PRIVATE KEY-----'].join(' ');
    const content = [begin, keyMaterial, end].join('\n');
    const findings = byRule(evaluateContentAs('rules/rg003-positive.pem', content), 'RG003');
    expect(findings).toHaveLength(1);
    expect(JSON.stringify(findings)).not.toContain(keyMaterial);
    expect(findings[0].message.toLowerCase()).toContain('not displayed');
  });

  it('ignores certificates and plain prose', () => {
    expect(byRule(evaluateFixture('rules/rg003-negative.pem'), 'RG003')).toHaveLength(0);
  });
});

describe('RG004 insecure TLS verification', () => {
  it('detects Python verification flags', () => {
    const findings = byRule(evaluateFixture('rules/rg004-positive.py'), 'RG004');
    expect(findings).toHaveLength(2);
  });

  it('detects Node.js TLS settings', () => {
    const findings = byRule(evaluateFixture('rules/rg004-positive.js'), 'RG004');
    expect(findings).toHaveLength(3);
  });

  it('ignores secure configurations', () => {
    expect(byRule(evaluateFixture('rules/rg004-negative.py'), 'RG004')).toHaveLength(0);
    expect(byRule(evaluateFixture('rules/rg004-negative.js'), 'RG004')).toHaveLength(0);
  });
});

describe('RG005 dynamic code evaluation', () => {
  it('detects eval, Function constructor, and string timers', () => {
    expect(byRule(evaluateFixture('rules/rg005-positive.js'), 'RG005')).toHaveLength(3);
    expect(byRule(evaluateFixture('rules/rg005-positive.py'), 'RG005')).toHaveLength(2);
  });

  it('ignores comments and similar-but-safe APIs', () => {
    expect(byRule(evaluateFixture('rules/rg005-negative.js'), 'RG005')).toHaveLength(0);
    expect(byRule(evaluateFixture('rules/rg005-negative.py'), 'RG005')).toHaveLength(0);
  });
});

describe('RG006 unsafe HTML injection', () => {
  it('detects direct HTML sinks and skips empty-string assignments', () => {
    expect(byRule(evaluateFixture('rules/rg006-positive.js'), 'RG006')).toHaveLength(3);
  });

  it('ignores textContent and unrelated property names', () => {
    expect(byRule(evaluateFixture('rules/rg006-negative.js'), 'RG006')).toHaveLength(0);
  });
});

describe('RG007 environment file hygiene', () => {
  it('reports an env file when the root gitignore has no matching pattern', () => {
    const findings = byRule(
      evaluateFixture('env/unignored/.env', {
        rootFileContents: { '.gitignore': readFixture('env/unignored/.gitignore') },
      }),
      'RG007',
    );
    expect(findings).toHaveLength(1);
    expect(findings[0].message).toContain('heuristic');
  });

  it('does not report when the root gitignore covers .env files', () => {
    expect(
      byRule(
        evaluateFixture('env/ignored/.env', {
          rootFileContents: { '.gitignore': readFixture('env/ignored/.gitignore') },
        }),
        'RG007',
      ),
    ).toHaveLength(0);
  });

  it('does not report example env files', () => {
    expect(
      byRule(
        evaluateFixture('env/ignored/.env.example', {
          rootFileContents: { '.gitignore': 'node_modules/' },
        }),
        'RG007',
      ),
    ).toHaveLength(0);
  });

  it('reports when no gitignore exists, with a heuristic explanation', () => {
    const findings = byRule(evaluateFixture('env/unignored/.env'), 'RG007');
    expect(findings).toHaveLength(1);
    expect(findings[0].limitations.toLowerCase()).toContain('heuristic');
  });
});

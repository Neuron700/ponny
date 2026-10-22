import { describe, expect, it } from 'vitest';
import type { Finding } from '../src/models/types';
import { escapeHtml, renderFindingDetailsHtml } from '../src/report/detailsHtml';

function finding(overrides: Partial<Finding> = {}): Finding {
  return {
    id: 'RG001:src/app.js:fp',
    ruleId: 'RG001',
    ruleTitle: 'Potential Hardcoded Credential',
    severity: 'high',
    message: 'Possible hardcoded credential. The value is redacted.',
    explanation: 'The assignment matched a secret-like key name.',
    whyRisky: 'The value may be usable by anyone with repository access.',
    remediation: 'Move the value to an environment variable and rotate it.',
    limitations: 'Pattern matching can report placeholders.',
    references: ['OWASP Top 10 A07'],
    relativePath: 'src/app.js',
    absolutePath: 'C:/fixture/src/app.js',
    workspaceFolder: 'fixture',
    fileName: 'app.js',
    line: 4,
    column: 10,
    endLine: 4,
    endColumn: 20,
    fingerprint: 'fp',
    maskedSnippet: 'const password = "[REDACTED]";',
    ...overrides,
  };
}

describe('finding details HTML', () => {
  it('renders all required detail sections with a CSP', () => {
    const html = renderFindingDetailsHtml(finding(), 'test-nonce');
    expect(html).toContain("default-src 'none'");
    expect(html).toContain("style-src 'nonce-test-nonce'");
    expect(html).toContain('RG001');
    expect(html).toContain('What was detected');
    expect(html).toContain('Why it can be risky');
    expect(html).toContain('Recommended remediation');
    expect(html).toContain('Detection limitations and false positives');
    expect(html).toContain('OWASP Top 10 A07');
    expect(html).toContain('not a confirmed vulnerability');
    expect(html).not.toContain('<script');
  });

  it('never renders raw secrets', () => {
    const secret = 'synthetic-details-secret-123';
    const token = 'ghp_fake0123456789abcdef';
    const html = renderFindingDetailsHtml(
      finding({
        message: `Hardcoded value: const password = "${secret}";`,
        maskedSnippet: `const password = "${secret}"; // ${token}`,
      }),
      'nonce',
    );

    expect(html).not.toContain(secret);
    expect(html).not.toContain(token);
    expect(html).toContain('[REDACTED]');
  });

  it('escapes HTML from finding text', () => {
    const html = renderFindingDetailsHtml(
      finding({
        explanation: '<script>alert("x")</script>',
        maskedSnippet: '<img src=x onerror=alert(1)>',
      }),
      'nonce',
    );
    expect(html).not.toContain('<script>alert');
    expect(html).toContain('&lt;script&gt;alert');
    expect(html).toContain('&lt;img src=x');
  });

  it('escapes HTML entities', () => {
    expect(escapeHtml(`<a href="x">'&'</a>`)).toBe(
      '&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;',
    );
  });
});

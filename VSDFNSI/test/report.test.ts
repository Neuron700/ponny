import { describe, expect, it } from 'vitest';
import type { Finding, ScanResult } from '../src/models/types';
import { buildReport, defaultReportFileName, serializeReport } from '../src/report/reportBuilder';

function finding(overrides: Partial<Finding> = {}): Finding {
  return {
    id: 'RG001:src/app.js:fp',
    ruleId: 'RG001',
    ruleTitle: 'Potential Hardcoded Credential',
    severity: 'high',
    message: 'Possible hardcoded credential assigned to "apiKey".',
    explanation: 'Explanation text.',
    whyRisky: 'Risk text.',
    remediation: 'Remediation text.',
    limitations: 'Limitations text.',
    references: ['Reference'],
    relativePath: 'src/app.js',
    absolutePath: 'C:/fixture/src/app.js',
    workspaceFolder: 'fixture',
    fileName: 'app.js',
    line: 4,
    column: 10,
    endLine: 4,
    endColumn: 20,
    fingerprint: 'fp',
    maskedSnippet: 'const apiKey = "[REDACTED]";',
    ...overrides,
  };
}

function scanResult(overrides: Partial<ScanResult> = {}): ScanResult {
  return {
    startedAt: '2026-01-01T00:00:00.000Z',
    finishedAt: '2026-01-01T00:00:02.000Z',
    findings: [],
    filesScanned: 4,
    filesSkipped: 1,
    skipped: [{ relativePath: 'src/big.js', reason: 'too-large' }],
    errors: 0,
    cancelled: false,
    workspaceFolders: ['fixture'],
    settings: {
      includeExtensions: ['js'],
      excludePatterns: [],
      maxFileSizeBytes: 1024,
      enabledRules: [],
      disabledRules: ['RG005'],
      scanOnSave: false,
    },
    ...overrides,
  };
}

describe('report builder', () => {
  it('builds structured findings with summary counts', () => {
    const active = finding();
    const ignored = finding({
      id: 'RG006:src/view.js:fp2',
      ruleId: 'RG006',
      ruleTitle: 'Potentially Unsafe HTML Injection',
      severity: 'medium',
      relativePath: 'src/view.js',
      line: 10,
      fingerprint: 'fp2',
    });

    const report = buildReport({
      toolVersion: '0.1.0',
      workspaceLabel: 'unit-test-workspace',
      workspaceFolders: ['fixture'],
      findings: [active, ignored],
      ignoredIds: new Set([ignored.id]),
      scan: scanResult(),
      generatedAt: new Date('2026-02-03T04:05:06.000Z'),
    });

    expect(report.schemaVersion).toBe(1);
    expect(report.tool).toEqual({ name: 'RepoGuard', version: '0.1.0' });
    expect(report.generatedAt).toBe('2026-02-03T04:05:06.000Z');
    expect(report.workspace).toEqual({
      label: 'unit-test-workspace',
      folders: ['fixture'],
    });
    expect(report.summary.total).toBe(2);
    expect(report.summary.active).toBe(1);
    expect(report.summary.ignored).toBe(1);
    expect(report.summary.bySeverity.high).toBe(1);
    expect(report.summary.bySeverity.medium).toBe(0);
    expect(report.summary.byRule).toEqual({ RG001: 1, RG006: 1 });
    expect(report.findings[0].fingerprint).toBeTruthy();
    expect(report.findings[0].ignored).toBe(false);
    expect(report.findings.find((item) => item.ruleId === 'RG006')?.ignored).toBe(true);
    expect(report.scan.filesSkipped).toBe(1);
    expect(report.scan.rulesDisabled).toEqual(['RG005']);
  });

  it('redacts secrets from every report text field', () => {
    const secret = 'synthetic-report-secret-123';
    const token = 'ghp_fake0123456789abcdef';
    const begin = ['-----BEGIN', 'RSA', 'PRIVATE KEY-----'].join(' ');
    const end = ['-----END', 'RSA', 'PRIVATE KEY-----'].join(' ');
    const report = buildReport({
      toolVersion: '0.1.0',
      workspaceLabel: 'workspace',
      workspaceFolders: ['fixture'],
      findings: [
        finding({
          message: `const apiKey = "${secret}";`,
          explanation: `Found token ${token}`,
          whyRisky: `Password: "${secret}"`,
          remediation: `Rotate the value: password="${secret}"`,
          limitations: `${begin}\n${secret}\n${end}`,
        }),
      ],
      scan: scanResult(),
    });

    const json = serializeReport(report);
    expect(json).not.toContain(secret);
    expect(json).not.toContain(token);
    expect(json).toContain('[REDACTED]');
    expect(json).toContain('src/app.js');
    expect(json).not.toContain(process.cwd());
    expect(json).not.toContain('C:\\\\fixture');
    expect(json).not.toContain('maskedSnippet');
  });

  it('handles a report without a completed scan', () => {
    const report = buildReport({
      toolVersion: '0.1.0',
      workspaceLabel: 'workspace',
      workspaceFolders: [],
      findings: [],
    });
    expect(report.scan.startedAt).toBeNull();
    expect(report.scan.filesScanned).toBe(0);
    expect(report.summary.total).toBe(0);
  });

  it('generates a filesystem-safe default report name', () => {
    expect(defaultReportFileName(new Date('2026-03-04T05:06:07.000Z'))).toBe(
      'repoguard-report-2026-03-04_05-06-07.json',
    );
  });
});

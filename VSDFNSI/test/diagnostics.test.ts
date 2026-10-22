import { describe, expect, it } from 'vitest';
import type { Finding, Severity } from '../src/models/types';
import {
  buildDiagnosticDescriptors,
  findingToRange,
  severityToDiagnosticName,
  toDiagnosticDescriptor,
} from '../src/diagnostics/descriptors';

function finding(overrides: Partial<Finding> = {}): Finding {
  return {
    id: 'RG001:src/app.js:fp',
    ruleId: 'RG001',
    ruleTitle: 'Potential Hardcoded Credential',
    severity: 'high',
    message: 'Possible hardcoded credential assigned to "password".',
    explanation: 'explanation',
    whyRisky: 'risk',
    remediation: 'remediation',
    limitations: 'limitations',
    references: [],
    relativePath: 'src/app.js',
    absolutePath: 'C:/fixture/src/app.js',
    workspaceFolder: 'fixture',
    fileName: 'app.js',
    line: 3,
    column: 5,
    endLine: 3,
    endColumn: 12,
    fingerprint: 'fp',
    maskedSnippet: 'const password = "[REDACTED]";',
    ...overrides,
  };
}

describe('diagnostic descriptors', () => {
  it('maps severities to VS Code diagnostic levels', () => {
    const expected: Record<Severity, string> = {
      critical: 'error',
      high: 'error',
      medium: 'warning',
      low: 'information',
      info: 'hint',
    };
    for (const [severity, name] of Object.entries(expected)) {
      expect(severityToDiagnosticName(severity as Severity)).toBe(name);
    }
  });

  it('converts one-based findings to zero-based ranges', () => {
    expect(findingToRange(finding())).toEqual({
      startLine: 2,
      startCharacter: 4,
      endLine: 2,
      endCharacter: 11,
    });
  });

  it('produces a non-empty range for zero-width findings', () => {
    expect(findingToRange(finding({ column: 1, endColumn: 1 })).endCharacter).toBe(1);
  });

  it('sets the RepoGuard source and rule id', () => {
    const descriptor = toDiagnosticDescriptor(finding());
    expect(descriptor.source).toBe('RepoGuard');
    expect(descriptor.code).toBe('RG001');
    expect(descriptor.message).toContain('RG001');
    expect(descriptor.severity).toBe('error');
  });

  it('never includes a raw secret in the diagnostic message', () => {
    const descriptor = toDiagnosticDescriptor(
      finding({
        message: 'Hardcoded password detected: const password = "synthetic-diagnostic-secret-123";',
      }),
    );
    expect(descriptor.message).not.toContain('synthetic-diagnostic-secret-123');
    expect(descriptor.message).toContain('[REDACTED]');
  });

  it('builds descriptors for every finding', () => {
    expect(buildDiagnosticDescriptors([finding(), finding({ id: 'two' })])).toHaveLength(2);
  });
});

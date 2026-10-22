import { describe, expect, it } from 'vitest';
import type { RuleDefinition } from '../src/models/types';
import { RuleRegistry, createDefaultRegistry } from '../src/engine/registry';
import { evaluateContent } from '../src/engine/ruleEngine';
import { byRule, evaluateContentAs, makeFileInfo, makeSettings } from './helpers';

describe('rule engine', () => {
  it('respects enabled and disabled rule settings', () => {
    const content = 'const password = "synthetic-engine-secret-123";';
    const registry = createDefaultRegistry();

    const onlyRg001 = evaluateContent(makeFileInfo('src/config.js'), content, registry, {
      settings: makeSettings({ enabledRules: ['RG001'] }),
    });
    expect(onlyRg001).toHaveLength(1);
    expect(onlyRg001[0].ruleId).toBe('RG001');

    const disabled = evaluateContent(makeFileInfo('src/config.js'), content, registry, {
      settings: makeSettings({ disabledRules: ['RG001'] }),
    });
    expect(byRule(disabled, 'RG001')).toHaveLength(0);

    const unrelated = evaluateContent(makeFileInfo('src/config.js'), content, registry, {
      settings: makeSettings({ enabledRules: ['RG002'] }),
    });
    expect(unrelated).toHaveLength(0);
  });

  it('applies rules only to relevant file types', () => {
    const findings = evaluateContentAs(
      'src/component.js',
      'const node = document.body; node.innerHTML = value;',
      { settings: makeSettings() },
    );
    expect(byRule(findings, 'RG006')).toHaveLength(1);

    const python = evaluateContentAs('src/component.py', 'node.innerHTML = value', {
      settings: makeSettings({ includeExtensions: ['py'] }),
    });
    expect(byRule(python, 'RG006')).toHaveLength(0);
  });

  it('keeps finding identity stable when line numbers shift', () => {
    const registry = createDefaultRegistry();
    const base = evaluateContent(
      makeFileInfo('src/config.js'),
      'const password = "synthetic-stable-secret-123";',
      registry,
      { settings: makeSettings() },
    );
    const shifted = evaluateContent(
      makeFileInfo('src/config.js'),
      '// header\n\nconst password = "synthetic-stable-secret-123";',
      registry,
      { settings: makeSettings() },
    );

    expect(base[0].id).toBe(shifted[0].id);
    expect(base[0].line).toBe(1);
    expect(shifted[0].line).toBe(3);
  });

  it('distinguishes identical matches on different lines', () => {
    const findings = evaluateContent(
      makeFileInfo('src/config.js'),
      'const password = "synthetic-duplicate-secret-123";\nconst password = "synthetic-duplicate-secret-123";',
      createDefaultRegistry(),
      { settings: makeSettings() },
    );

    expect(findings).toHaveLength(2);
    expect(findings[0].id).not.toBe(findings[1].id);
  });

  it('supports registering additional rules without changing the scanner', () => {
    const customRule: RuleDefinition = {
      id: 'RG008',
      title: 'Custom check',
      severity: 'info',
      explanation: 'Custom explanation',
      whyRisky: 'Custom risk',
      remediation: 'Custom remediation',
      limitations: 'Custom limitations',
      fileExtensions: '*',
      detect: () => [
        {
          line: 1,
          column: 1,
          endLine: 1,
          endColumn: 2,
          message: 'Custom finding',
          fingerprintSeed: 'custom',
        },
      ],
    };

    const registry = new RuleRegistry().register(customRule);
    const findings = evaluateContent(makeFileInfo('src/custom.js'), 'anything', registry, {
      settings: makeSettings(),
    });
    expect(findings).toHaveLength(1);
    expect(findings[0].ruleId).toBe('RG008');
  });

  it('rejects invalid and duplicate rule registrations', () => {
    const registry = new RuleRegistry();
    const baseRule: RuleDefinition = {
      id: 'RG100',
      title: 'Test',
      severity: 'info',
      explanation: 'x',
      whyRisky: 'x',
      remediation: 'x',
      limitations: 'x',
      fileExtensions: '*',
      detect: () => [],
    };
    registry.register(baseRule);
    expect(() => registry.register(baseRule)).toThrow(/Duplicate/);
    expect(() => registry.register({ ...baseRule, id: 'BAD' })).toThrow(/Invalid/);
  });

  it('survives a rule that throws', () => {
    const registry = new RuleRegistry().register({
      id: 'RG009',
      title: 'Broken',
      severity: 'low',
      explanation: 'x',
      whyRisky: 'x',
      remediation: 'x',
      limitations: 'x',
      fileExtensions: '*',
      detect: () => {
        throw new Error('rule failure');
      },
    });

    expect(() =>
      evaluateContent(makeFileInfo('src/test.js'), 'content', registry, {
        settings: makeSettings(),
      }),
    ).not.toThrow();
    expect(
      evaluateContent(makeFileInfo('src/test.js'), 'content', registry, {
        settings: makeSettings(),
      }),
    ).toHaveLength(0);
  });
});

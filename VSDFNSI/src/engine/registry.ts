import type { RuleDefinition } from '../models/types';
import { rg001HardcodedCredentials } from '../rules/rg001HardcodedCredentials';
import { rg002TokenPatterns } from '../rules/rg002TokenPatterns';
import { rg003PrivateKeyMaterial } from '../rules/rg003PrivateKey';
import { rg004InsecureTls } from '../rules/rg004InsecureTls';
import { rg005DynamicCodeEvaluation } from '../rules/rg005DynamicEvaluation';
import { rg006UnsafeHtmlInjection } from '../rules/rg006UnsafeHtml';
import { rg007EnvHygiene } from '../rules/rg007EnvHygiene';

export class RuleRegistry {
  private readonly rules = new Map<string, RuleDefinition>();

  register(rule: RuleDefinition): this {
    if (!/^RG\d{3}$/.test(rule.id)) {
      throw new Error(`Invalid rule id "${rule.id}". Rule ids must match RGnnn.`);
    }
    if (this.rules.has(rule.id)) {
      throw new Error(`Duplicate rule id "${rule.id}".`);
    }
    this.rules.set(rule.id, rule);
    return this;
  }

  registerAll(rules: readonly RuleDefinition[]): this {
    for (const rule of rules) {
      this.register(rule);
    }
    return this;
  }

  get(id: string): RuleDefinition | undefined {
    return this.rules.get(id);
  }

  all(): RuleDefinition[] {
    return [...this.rules.values()];
  }

  size(): number {
    return this.rules.size;
  }
}

export function createDefaultRegistry(): RuleRegistry {
  return new RuleRegistry().registerAll([
    rg001HardcodedCredentials,
    rg002TokenPatterns,
    rg003PrivateKeyMaterial,
    rg004InsecureTls,
    rg005DynamicCodeEvaluation,
    rg006UnsafeHtmlInjection,
    rg007EnvHygiene,
  ]);
}

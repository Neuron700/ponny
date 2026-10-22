import type { RuleDefinition } from '../models/types';
import { redactSecrets } from '../utils/masking';
import { isCommentLine, normalizeSeed } from '../utils/text';
import { findLineHits, JS_TS_EXTENSIONS, trimSnippet } from './helpers';

interface EvaluationPattern {
  name: string;
  pattern: RegExp;
  extensions: readonly string[];
}

const EVALUATION_PATTERNS: readonly EvaluationPattern[] = [
  {
    name: 'eval()',
    pattern: /\beval\s*\(/g,
    extensions: ['js', 'jsx', 'ts', 'tsx', 'mjs', 'cjs', 'py'],
  },
  {
    name: 'new Function()',
    pattern: /\bnew\s+Function\s*\(/g,
    extensions: JS_TS_EXTENSIONS,
  },
  {
    name: 'string-based timer',
    pattern: /\bset(?:Timeout|Interval)\s*\(\s*['"`]/g,
    extensions: JS_TS_EXTENSIONS,
  },
  { name: 'exec()', pattern: /\bexec\s*\(/g, extensions: ['py'] },
];

export const rg005DynamicCodeEvaluation: RuleDefinition = {
  id: 'RG005',
  title: 'Dynamic Code Evaluation',
  severity: 'medium',
  explanation:
    'Code that evaluates a string as executable code was found. This is potentially risky rather than automatically vulnerable; the risk depends on whether untrusted input can reach the evaluated string.',
  whyRisky:
    'Dynamic evaluation blurs the boundary between data and code. If user input, file contents, or network responses reach it, an attacker may be able to execute arbitrary logic in the application context.',
  remediation:
    'Prefer parsing data as data (for example JSON.parse, json.loads, or an allowlisted interpreter). If dynamic evaluation is unavoidable, strictly validate and constrain input, run it with minimal privileges, and isolate it from sensitive runtime state.',
  limitations:
    'This rule flags selected built-in constructs. It does not perform taint analysis and cannot determine whether the evaluated value is trusted. Framework wrappers and indirect references are not detected.',
  references: ['OWASP Top 10 A03: Injection'],
  fileExtensions: ['js', 'jsx', 'ts', 'tsx', 'mjs', 'cjs', 'py'],
  detect(context) {
    const matches = [];
    for (const evaluationPattern of EVALUATION_PATTERNS) {
      if (!evaluationPattern.extensions.includes(context.file.extension)) {
        continue;
      }
      for (const hit of findLineHits(context.lines, evaluationPattern.pattern)) {
        if (isCommentLine(hit.lineText)) {
          continue;
        }
        matches.push({
          line: hit.line,
          column: hit.column,
          endLine: hit.line,
          endColumn: hit.endColumn,
          message: `Dynamic code evaluation via ${evaluationPattern.name} is potentially risky. Review whether untrusted input can reach it.`,
          fingerprintSeed: `${evaluationPattern.name}|${normalizeSeed(redactSecrets(hit.lineText))}`,
          snippet: trimSnippet(redactSecrets(hit.lineText)),
        });
      }
    }
    return matches;
  },
};

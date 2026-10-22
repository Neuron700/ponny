import type { RuleDefinition } from '../models/types';
import { isEnvExampleFileName } from '../utils/paths';
import { isEnvFileIgnored } from '../utils/gitignore';

export const rg007EnvHygiene: RuleDefinition = {
  id: 'RG007',
  title: 'Environment File Hygiene',
  severity: 'medium',
  explanation:
    'An environment file was found, but the workspace root .gitignore does not appear to contain a matching .env pattern.',
  whyRisky:
    'Environment files commonly hold credentials and environment-specific settings. Without an ignore rule, they can be committed accidentally and shared with anyone who can read the repository.',
  remediation:
    'Add the environment file pattern to the root .gitignore (for example `.env` or `.env*`), verify that the file is not already tracked with `git ls-files`, and rotate any credentials that were committed. Commit a sanitized `.env.example` instead.',
  limitations:
    'This is a heuristic that only inspects the workspace root .gitignore. It cannot establish whether the file is actually tracked by Git, whether a parent directory or global ignore file applies, or whether Git is used at all. Nested .gitignore files are not considered.',
  references: ['Git documentation: gitignore'],
  fileExtensions: [],
  fileNamePattern: /^(\.env(\..+)?|.+\.env)$/i,
  detect(context) {
    const fileName = context.file.fileName;
    if (isEnvExampleFileName(fileName)) {
      return [];
    }

    const gitignore = context.rootFileContents['.gitignore'];
    const ignored = isEnvFileIgnored(gitignore, fileName, context.file.relativePath);
    if (ignored) {
      return [];
    }

    return [
      {
        line: 1,
        column: 1,
        endLine: 1,
        endColumn: 1,
        message: `Environment file "${fileName}" is not matched by a .env rule in the root .gitignore. This is a heuristic check.`,
        fingerprintSeed: `env-hygiene|${fileName}`,
        snippet: `Environment file: ${fileName}`,
      },
    ];
  },
};

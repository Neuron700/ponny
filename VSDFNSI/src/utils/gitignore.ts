import { minimatch } from 'minimatch';

function matchesGitignorePattern(pattern: string, fileName: string, relativePath: string): boolean {
  const cleaned = pattern.replace(/\\/g, '/').replace(/^\/+/, '');
  if (!cleaned) {
    return false;
  }

  const options = { dot: true, nocase: process.platform === 'win32' };
  const candidates = [
    minimatch(fileName, cleaned, options),
    minimatch(relativePath, cleaned, options),
    minimatch(relativePath, `**/${cleaned}`, options),
    minimatch(fileName, cleaned, { ...options, matchBase: true }),
  ];

  return candidates.some(Boolean);
}

export function isEnvFileIgnored(
  gitignoreContent: string | undefined,
  fileName: string,
  relativePath: string,
): boolean {
  if (!gitignoreContent) {
    return false;
  }

  let ignored = false;
  for (const rawLine of gitignoreContent.split(/\r\n|\r|\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) {
      continue;
    }
    if (line.endsWith('/')) {
      continue;
    }

    const negated = line.startsWith('!');
    const pattern = negated ? line.slice(1) : line;
    if (pattern && matchesGitignorePattern(pattern, fileName, relativePath)) {
      ignored = !negated;
    }
  }

  return ignored;
}

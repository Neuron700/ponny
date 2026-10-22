import { describe, expect, it } from 'vitest';
import {
  ALWAYS_EXCLUDED_SEGMENTS,
  buildExcludeGlob,
  buildIncludeGlobs,
  filterCandidatePaths,
  isExcludedPath,
  isSupportedFile,
} from '../src/scanner/filters';
import { DEFAULT_EXCLUDE_PATTERNS, DEFAULT_INCLUDE_EXTENSIONS } from '../src/config/defaults';

describe('scanner filters', () => {
  it('excludes dependency, VCS, and generated directories by default', () => {
    for (const relativePath of [
      'node_modules/pkg/index.js',
      '.git/config',
      'dist/app.js',
      'build/output.js',
      'coverage/report.json',
      'vendor/lib.py',
      '.venv/lib/python3/site.py',
      '__pycache__/cache.py',
      'src/app.min.js',
    ]) {
      expect(isExcludedPath(relativePath, DEFAULT_EXCLUDE_PATTERNS)).toBe(true);
    }
    expect(isExcludedPath('src/app.js', DEFAULT_EXCLUDE_PATTERNS)).toBe(false);
    expect(ALWAYS_EXCLUDED_SEGMENTS).toContain('.git');
  });

  it('always excludes node_modules and .git even without user patterns', () => {
    expect(isExcludedPath('node_modules/pkg/index.js', [])).toBe(true);
    expect(isExcludedPath('.git/config', [])).toBe(true);
    expect(isExcludedPath('src/index.js', [])).toBe(false);
  });

  it('applies custom exclusion patterns', () => {
    expect(isExcludedPath('samples/demo.js', ['**/samples/**'])).toBe(true);
    expect(isExcludedPath('samples/demo.js', DEFAULT_EXCLUDE_PATTERNS)).toBe(false);
  });

  it('supports common source, config, and environment files', () => {
    for (const fileName of [
      'app.js',
      'main.ts',
      'script.py',
      'data.json',
      'ci.yml',
      'Cargo.toml',
      '.env',
      '.env.local',
      'prod.env',
    ]) {
      expect(isSupportedFile(fileName, DEFAULT_INCLUDE_EXTENSIONS)).toBe(true);
    }
    expect(isSupportedFile('image.png', DEFAULT_INCLUDE_EXTENSIONS)).toBe(false);
    expect(isSupportedFile('README.md', DEFAULT_INCLUDE_EXTENSIONS)).toBe(false);
    expect(isSupportedFile('no-extension', DEFAULT_INCLUDE_EXTENSIONS)).toBe(false);
  });

  it('filters candidate paths with both include and exclude rules', () => {
    const paths = [
      'src/app.ts',
      'node_modules/pkg/index.js',
      'assets/logo.png',
      '.env',
      'dist/bundle.js',
    ];
    expect(
      filterCandidatePaths(paths, {
        includeExtensions: DEFAULT_INCLUDE_EXTENSIONS,
        excludePatterns: DEFAULT_EXCLUDE_PATTERNS,
      }),
    ).toEqual(['src/app.ts', '.env']);
  });

  it('builds include globs for extensions and env files', () => {
    const globs = buildIncludeGlobs(['js', '.ts', 'ts']);
    expect(globs[0]).toBe('**/*.{js,ts}');
    expect(globs).toContain('**/.env');
    expect(globs).toContain('**/.env.*');
    expect(buildIncludeGlobs([])).toEqual(['**/.env', '**/.env.*', '**/*.env']);
  });

  it('builds an exclusion glob', () => {
    expect(buildExcludeGlob(['**/dist/**', '**/out/**'])).toBe('{**/dist/**,**/out/**}');
    expect(buildExcludeGlob([])).toBe('**/{.git,node_modules}/**');
  });
});

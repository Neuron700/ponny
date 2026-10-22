export function normalizeSlashes(value: string): string {
  return value.replace(/\\/g, '/');
}

export function fileNameOf(filePath: string): string {
  const normalized = normalizeSlashes(filePath);
  const index = normalized.lastIndexOf('/');
  return index >= 0 ? normalized.slice(index + 1) : normalized;
}

export function extensionOf(fileName: string): string {
  const index = fileName.lastIndexOf('.');
  if (index <= 0) {
    return '';
  }
  return fileName.slice(index + 1).toLowerCase();
}

export function normalizeExtension(extension: string): string {
  return extension.trim().replace(/^\./, '').toLowerCase();
}

const ENV_EXAMPLE_SUFFIXES = [
  '.example',
  '.sample',
  '.template',
  '.tpl',
  '.dist',
  '.defaults',
  '.default',
];

export function isEnvFileName(fileName: string): boolean {
  if (fileName === '.env') {
    return true;
  }
  if (fileName.startsWith('.env.')) {
    return !ENV_EXAMPLE_SUFFIXES.includes(fileName.slice('.env'.length).toLowerCase());
  }
  return /\.env$/i.test(fileName);
}

export function isEnvExampleFileName(fileName: string): boolean {
  const lower = fileName.toLowerCase();
  if (lower === '.env.example' || lower === '.env.sample' || lower === '.env.template') {
    return true;
  }
  return ENV_EXAMPLE_SUFFIXES.some((suffix) => lower.endsWith(`.env${suffix}`));
}

export function isProbablyBinary(buffer: Buffer): boolean {
  const sampleLength = Math.min(buffer.length, 8192);
  for (let i = 0; i < sampleLength; i += 1) {
    if (buffer[i] === 0) {
      return true;
    }
  }
  return false;
}

export function splitLines(content: string): string[] {
  return content.split(/\r\n|\r|\n/);
}

export function normalizeSeed(value: string): string {
  return value.replace(/\s+/g, ' ').trim();
}

export function isCommentLine(line: string): boolean {
  const trimmed = line.trimStart();
  return (
    trimmed.startsWith('//') ||
    trimmed.startsWith('#') ||
    trimmed.startsWith('/*') ||
    trimmed.startsWith('*') ||
    trimmed.startsWith('--')
  );
}

export function lineIsBlank(line: string): boolean {
  return line.trim().length === 0;
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export async function yieldToEventLoop(): Promise<void> {
  await new Promise<void>((resolve) => setImmediate(resolve));
}

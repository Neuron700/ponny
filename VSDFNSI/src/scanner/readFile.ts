import { promises as fs } from 'node:fs';
import type { ReadResult } from '../models/types';
import { isProbablyBinary } from '../utils/paths';

export async function readFileContent(absolutePath: string, maxBytes: number): Promise<ReadResult> {
  try {
    const stats = await fs.stat(absolutePath);
    if (!stats.isFile()) {
      return { ok: false, reason: 'unreadable', detail: 'Not a regular file' };
    }
    if (stats.size === 0) {
      return { ok: false, reason: 'empty' };
    }
    if (stats.size > maxBytes) {
      return { ok: false, reason: 'too-large' };
    }

    const buffer = await fs.readFile(absolutePath);
    if (buffer.length > maxBytes) {
      return { ok: false, reason: 'too-large' };
    }
    if (isProbablyBinary(buffer)) {
      return { ok: false, reason: 'binary' };
    }

    return { ok: true, content: buffer.toString('utf8') };
  } catch (error) {
    return {
      ok: false,
      reason: 'unreadable',
      detail: error instanceof Error ? error.message : 'Unknown read error',
    };
  }
}

export async function readTextFileIfPresent(
  absolutePath: string,
  maxBytes = 1024 * 1024,
): Promise<string | undefined> {
  const result = await readFileContent(absolutePath, maxBytes);
  return result.ok ? result.content : undefined;
}

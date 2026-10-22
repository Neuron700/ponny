import type { Finding } from '../models/types';
import { SEVERITY_LABELS } from '../models/severity';
import { redactSecrets } from '../utils/masking';

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function safe(value: string): string {
  return escapeHtml(redactSecrets(value));
}

function listItems(items: readonly string[]): string {
  if (items.length === 0) {
    return '<p class="muted">None listed.</p>';
  }
  return `<ul>${items.map((item) => `<li>${safe(item)}</li>`).join('')}</ul>`;
}

export function renderFindingDetailsHtml(finding: Finding, nonce: string): string {
  const severity = finding.severity;
  const position = `${finding.relativePath}:${finding.line}:${finding.column}`;

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'nonce-${nonce}';">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RepoGuard ${safe(finding.ruleId)}</title>
<style nonce="${nonce}">
  :root { color-scheme: light dark; }
  body {
    margin: 0;
    padding: 20px 24px 40px;
    font-family: var(--vscode-font-family);
    font-size: var(--vscode-font-size);
    color: var(--vscode-foreground);
    background: var(--vscode-editor-background);
    line-height: 1.55;
  }
  h1 { font-size: 1.25rem; margin: 0 0 4px; font-weight: 600; }
  h2 { font-size: 0.95rem; margin: 24px 0 6px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--vscode-descriptionForeground); }
  .meta { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; margin: 16px 0 0; }
  .meta dt { color: var(--vscode-descriptionForeground); }
  .meta dd { margin: 0; overflow-wrap: anywhere; }
  .badge { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 0.8rem; font-weight: 600; border: 1px solid currentColor; }
  .severity-critical, .severity-high { color: var(--vscode-errorForeground); }
  .severity-medium { color: var(--vscode-editorWarning-foreground); }
  .severity-low, .severity-info { color: var(--vscode-editorInfo-foreground); }
  code { background: var(--vscode-textCodeBlock-background); padding: 2px 6px; border-radius: 4px; font-family: var(--vscode-editor-font-family); overflow-wrap: anywhere; }
  .snippet { display: block; padding: 10px 12px; border-left: 3px solid var(--vscode-focusBorder); background: var(--vscode-textCodeBlock-background); font-family: var(--vscode-editor-font-family); white-space: pre-wrap; overflow-wrap: anywhere; }
  ul { margin: 4px 0; padding-left: 22px; }
  .muted { color: var(--vscode-descriptionForeground); }
  .note { border: 1px solid var(--vscode-panel-border); border-radius: 6px; padding: 12px 14px; margin-top: 28px; color: var(--vscode-descriptionForeground); }
  a { color: var(--vscode-textLink-foreground); }
</style>
</head>
<body>
  <h1>${safe(finding.ruleId)} · ${safe(finding.ruleTitle)}</h1>
  <span class="badge severity-${severity}">${SEVERITY_LABELS[severity]}</span>

  <dl class="meta">
    <dt>Location</dt><dd>${safe(position)}</dd>
    <dt>Workspace</dt><dd>${safe(finding.workspaceFolder)}</dd>
    <dt>Confidence</dt><dd>Heuristic pattern match, not a confirmed vulnerability</dd>
  </dl>

  <h2>What was detected</h2>
  <p>${safe(finding.message)}</p>
  ${finding.maskedSnippet ? `<h2>Relevant line (masked)</h2><code class="snippet">${safe(finding.maskedSnippet)}</code>` : ''}

  <h2>Why it can be risky</h2>
  <p>${safe(finding.whyRisky)}</p>

  <h2>Recommended remediation</h2>
  <p>${safe(finding.remediation)}</p>

  <h2>Detection limitations and false positives</h2>
  <p>${safe(finding.explanation)}</p>
  <p>${safe(finding.limitations)}</p>

  <h2>References</h2>
  ${listItems(finding.references)}

  <div class="note">
    RepoGuard performs local, rule-based checks. It is not a full SAST, dependency scanner, or penetration test, and a match does not prove exploitability. Ignore only after reviewing the code path.
  </div>
</body>
</html>`;
}

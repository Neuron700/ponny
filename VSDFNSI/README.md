# RepoGuard — VS Code Security Assistant

RepoGuard is a **local-first, rule-based security hygiene checker** for Visual Studio Code. It scans the source and configuration files in your workspace for a small set of explainable risk patterns, shows findings in a dedicated sidebar and in the Problems panel, and helps you record reviewed false positives.

> **RepoGuard is not a full SAST, SCA, penetration test, or proof that your project is secure.** It is a pattern matcher that surfaces signals worth reviewing. Every finding is a heuristic and may be a false positive or a false negative.

## Highlights

- **Runs locally.** No network calls, accounts, cloud API, telemetry, or upload of source code.
- **Real scanning.** Uses `vscode.workspace.findFiles`, reads only eligible files, enforces size limits, skips binaries, and supports cancellation.
- **Actionable UI.** Findings explorer with severity groups, file groups, search, severity filter, inline diagnostics, quick fixes, and a details panel.
- **Privacy-aware output.** Detected credential values are masked in messages, tooltips, details, diagnostics, and exported reports.
- **Safe by default.** Never executes workspace code or shell commands, never edits project files, and is disabled in untrusted workspaces.
- **Extensible rule engine.** Add a new rule with a typed object and register it in one place.

## Requirements

- VS Code **1.85 or newer**
- Node.js **18 or newer** (for development)
- npm

## Install and try it

### Option A — run from source (development)

```powershell
npm install
npm test
npm run compile
```

1. Open the `VSDFNSI` folder (the folder containing this README) in VS Code.
2. Press **F5**. A new **Extension Development Host** window opens.
3. In the new window, open any project folder. Trust the folder when prompted.
4. Open the Command Palette (`Ctrl+Shift+P`) and run **RepoGuard: Scan Workspace**.
5. Click the RepoGuard shield icon in the Activity Bar to inspect results.

> The Extension Development Host runs the code from `out/extension.js`. Run `npm run compile` after changing source, or use the `npm: watch` task.

### Option B — install the packaged extension

```powershell
npm run package
```

This produces `repoguard-0.1.0.vsix`. Then either:

- In VS Code: **Extensions → … → Install from VSIX…**, or
- From a terminal: `code --install-extension repoguard-0.1.0.vsix`

Reload VS Code, open a trusted folder, and run **RepoGuard: Scan Workspace**.

## Commands

| Command | What it does |
| --- | --- |
| `RepoGuard: Scan Workspace` | Scans every eligible file in all workspace folders. Shows progress and supports cancellation. |
| `RepoGuard: Scan Current File` | Scans the active saved editor buffer, even if the file is outside the default extension allowlist. Size and binary checks still apply. |
| `RepoGuard: Refresh Findings` | Re-runs the most recent scan scope (workspace or single file). |
| `RepoGuard: Clear Findings` | Removes findings and diagnostics. Ignored findings are kept. |
| `RepoGuard: Manage Ignored Findings` | Lists persisted ignores and restores selected entries. |
| `RepoGuard: Export Report` | Writes a redacted JSON report to a destination you choose. |
| `RepoGuard: Search Findings` | Filters the sidebar by file path, rule ID, title, or message. |
| `RepoGuard: Filter by Severity` | Shows only one severity in the sidebar. |
| `RepoGuard: Toggle Group By…` | Switches sidebar grouping between severity and file. |
| `RepoGuard: Show or Hide Ignored Findings` | Adds a collapsed “Ignored” group to the sidebar. |

Internal commands such as **Ignore Finding**, **Restore Finding**, and **Show Finding Details** are available from the sidebar context menu and editor quick fixes.

## Using the Findings Explorer

- The top item summarizes total, active, and ignored counts. Hover it for per-severity counts.
- Findings are grouped by severity (default) or file. Each item shows its rule ID, title, and relative location.
- Clicking a finding opens the file at the matching range and opens the details panel.
- Use the eye icon to review ignored findings, then restore them from the context menu.
- Empty, loading, filtered-empty, clean, and failure states are real states driven by the last scan — there are no simulated events.

## Ignoring findings

Ignoring is stored in **VS Code workspace state** (`workspaceState`), not in project files. RepoGuard never inserts suppression comments.

An ignore is keyed by:

- rule ID,
- relative file path,
- a stable fingerprint derived from the redacted matching line.

Line shifts do not invalidate an ignore. Editing the matched line can create a new fingerprint, so the finding may reappear; this is intentional. Ignoring one occurrence does not disable the rule for other files or other lines.

## Settings

| Setting | Default | Purpose |
| --- | --- | --- |
| `repoguard.scanOnSave` | `false` | Scan the saved file (debounced) when it belongs to the workspace. |
| `repoguard.includeExtensions` | JS/TS, Python, JSON, YAML, TOML, env, shell, Go, Ruby, Java, PHP, C#, Rust, config files | Extensions to include, without the leading dot. `.env` files are always considered. |
| `repoguard.excludePatterns` | dependency, VCS, build, coverage, vendor, virtualenv, and generated folders | Glob patterns excluded from discovery. `.git` and `node_modules` segments are always excluded. |
| `repoguard.maxFileSizeKb` | `512` | Maximum file size to read. Larger files are skipped and counted in the summary. |
| `repoguard.enabledRules` | `[]` | If non-empty, only these rule IDs run. |
| `repoguard.disabledRules` | `[]` | Rule IDs to skip. |

Scan-on-save is opt-in and runs only after a save, never on keystrokes. It also requires a trusted workspace.

## Rules

| ID | Title | Default severity | Detects |
| --- | --- | --- | --- |
| RG001 | Potential Hardcoded Credential | High | A secret-like key assigned a literal string, including quoted assignments and unquoted `.env` values. Placeholders, environment lookups, and common example values are ignored. |
| RG002 | Recognizable Token Pattern | High | A deliberately limited set of documented token formats: GitHub PATs, AWS access key IDs, Stripe live secret keys, Google API keys, Slack tokens. |
| RG003 | Private Key Material | Critical | PEM private-key block markers. Key material is never displayed. |
| RG004 | Insecure TLS Verification | High | Selected settings such as Python `verify=False`, Node.js `rejectUnauthorized: false`, `strictSSL: false`, `NODE_TLS_REJECT_UNAUTHORIZED=0`, Go `InsecureSkipVerify: true`, and libcurl peer verification disabled. |
| RG005 | Dynamic Code Evaluation | Medium | Selected `eval`/`exec` calls, the `Function` constructor, and string-based timers. Reported as potentially risky, not confirmed vulnerable. |
| RG006 | Potentially Unsafe HTML Injection | Medium | Direct `.innerHTML`, `.outerHTML`, and `insertAdjacentHTML` sinks in JavaScript/TypeScript. Empty-string assignments are skipped. |
| RG007 | Environment File Hygiene | Medium | An environment file with no matching `.env` pattern in the workspace root `.gitignore`. Explicitly heuristic. |

Each rule returns a typed finding with:

- stable ID,
- explanation and risk context,
- remediation guidance,
- known limitations and false-positive notes,
- relative path and location when available,
- a masked snippet,
- a fingerprint used for ignores.

The full metadata for each rule lives in `src/rules/`. Findings never include a raw credential value.

### Adding a rule (RG008 slot)

The scanner is rule-agnostic. Create a `RuleDefinition`, add tests and fixtures, then register it in `src/engine/registry.ts`:

```ts
import type { RuleDefinition } from '../models/types';

export const rg008Example: RuleDefinition = {
  id: 'RG008',
  title: 'Example additional check',
  severity: 'low',
  explanation: 'What the pattern means.',
  whyRisky: 'Why it deserves review.',
  remediation: 'What to do instead.',
  limitations: 'What the check cannot know.',
  fileExtensions: ['js', 'ts'],
  detect(context) {
    return [];
  },
};
```

Rule IDs are validated as `RGnnn`, and duplicate registrations throw at activation.

## Diagnostics and quick fixes

Findings are attached to `vscode.languages.createDiagnosticCollection('repoguard')` with:

- source `RepoGuard`,
- rule ID as the diagnostic code,
- severity mapped from the finding,
- a range based on the matched location,
- a redacted message prefixed with the rule ID.

The collection is cleared and rebuilt after every completed scan, so stale diagnostics do not survive. Quick fixes offer **Ignore Finding** and **Show Finding Details**.

## Export

**RepoGuard: Export Report** writes JSON to a location selected through the standard save dialog. It includes:

- scan timestamps and workspace label/folder names,
- summary counts by severity and rule,
- rule IDs, titles, severities,
- relative paths and positions,
- explanations, risk context, remediation, and limitations,
- ignore status per finding,
- a redacted fingerprint.

It does **not** include source files, snippets, absolute paths, or raw credentials. All text fields pass through a defense-in-depth redactor before serialization.

The `scan` summary counts reflect the last completed scan. `bySeverity` counts active (non-ignored) findings; `total` and `byRule` include ignored ones, and `summary.ignored` reports the difference.

## Privacy and security model

- Everything runs in the extension host on your machine.
- There is no HTTP client, telemetry, account system, or remote database.
- RepoGuard never executes workspace code or shells out based on file contents.
- RepoGuard never writes to project files. The only writes are the explicitly chosen report destination.
- Source files are treated as untrusted text. Malformed UTF-8, binaries, empty files, and read failures are handled without crashing.
- The Output channel logs scan counts, rule IDs, and file paths — never file contents or detected values.
- The extension declares `capabilities.untrustedWorkspaces.supported = false`; VS Code will not activate it in Restricted Mode.
- The details webview uses `enableScripts: false`, no local resources, and a restrictive CSP with a per-view nonce.
- The only runtime dependency is `minimatch` (used for ignore/exclude glob matching), bundled into `out/extension.js`.

## Detection limitations (read this)

- **Heuristics only.** A match does not prove exploitability. A clean scan does not prove security.
- **No taint or data-flow analysis.** RG005/RG006 cannot know whether untrusted input reaches a sink.
- **Format matching is intentionally narrow.** RG002 supports a few providers and will miss most token formats. Synthetic values can match.
- **False positives are expected.** Configuration wrappers, dependencies, test fixtures, generated code, and documentation can produce findings.
- **False negatives are expected.** Secrets built at runtime, unusual key names, encoded values, and unsupported file types are not detected.
- **Git tracking is not verified.** RG007 only checks the workspace root `.gitignore`; it does not run Git, inspect the index, or read parent/global/nested ignore files.
- **Local files only.** File discovery uses workspace APIs, but content reading uses the local filesystem. Virtual and remote workspaces may not yield readable content.
- **Discovery limits.** Up to 20,000 results per include glob per workspace folder are requested; extremely large workspaces may be truncated silently.
- **Multi-root collisions.** Findings are scoped by workspace folder *name*. Two folders with the same name share a display prefix.
- **Line edits and ignores.** An ignore is tied to a fingerprint of the redacted line. Large edits to that line may require re-ignoring.
- **Scan-on-save scope.** Only the saved file is rescanned; other files keep their previous results until the next workspace scan.
- **No auto-remediation.** RepoGuard does not edit or delete files.

## Architecture

```
src/
  extension.ts                activation, wiring, subscriptions
  commands/                   scan, findings, view, export, registration
  scanner/                    discovery filters, file reading, scan orchestration, VS Code port
  engine/                     rule registry and evaluation/fingerprinting
  rules/                      RG001–RG007 definitions and match helpers
  diagnostics/                pure descriptor mapping + VS Code collection manager
  providers/                  tree view, code actions, details webview
  storage/                    validated workspace-state ignore store
  report/                     report builder, redaction, details HTML
  models/                     typed findings, rules, settings, severity
  utils/                      paths, hashing, masking, gitignore, text helpers
test/
  fixtures/                   synthetic positive/negative files (no real credentials)
  *.test.ts                   rule, scanner, engine, ignore, diagnostics, report, UI-text tests
```

Key boundaries:

- Rule detection is pure and has no VS Code imports.
- The scan runner depends on a small `ScanPort`, so limits, cancellation, exclusions, and error handling are testable with fakes.
- The VS Code port handles `findFiles`, relative paths, and root-file reads.
- Diagnostics map from pure descriptors; the collection manager is a thin adapter.
- Ignore storage takes a Memento-like interface, so persistence and schema validation are unit-tested.

## Development

```powershell
npm install
npm run typecheck   # TypeScript, including tests
npm run lint        # ESLint
npm test            # compiles, then runs Vitest
npm run format      # Prettier
npm run compile     # tsc + bundled extension entry
npm run watch       # incremental type emit
```

The suite currently contains **88 tests across 10 files**, covering:

- every initial rule with positive and negative fixtures,
- unstable/malformed input and safe projects,
- file exclusions, size limits, binary/empty/unreadable files,
- empty workspaces,
- finding identity stability across line shifts,
- ignore/restore persistence, scoping, and schema validation,
- diagnostic severity, ranges, source/code, and message redaction,
- report structure, redaction, and path hygiene,
- details HTML escaping and CSP,
- manifest command/setting wiring.

Tests use only synthetic placeholders. Do not add real credentials to fixtures.

## Packaging

```powershell
npm run package
```

The `.vsix` contains only `out/extension.js`, its source map, `media/shield.svg`, README, LICENSE, and the manifest. `minimatch` is bundled, so no dependency install is required by the end user.

To inspect the package contents first:

```powershell
npx vsce ls
```

## Troubleshooting

- **Commands are missing in Restricted Mode.** Trust the workspace; RepoGuard intentionally does not activate untrusted folders.
- **No files found.** Check workspace trust, `repoguard.includeExtensions`, and `repoguard.excludePatterns`. `.env` files are recognized by name.
- **A file is skipped.** It may exceed `repoguard.maxFileSizeKb`, contain NUL bytes, or be unreadable. The completion message reports skipped counts.
- **Stale-looking results.** Run **RepoGuard: Refresh Findings**. Cancelled scans keep the previous results.
- **A finding reappears after ignoring.** The matched line changed enough to produce a new fingerprint. Ignore it again after review.
- **Need to see everything again.** Use **Manage Ignored Findings** to restore entries, then scan.

## License

MIT. See the `LICENSE` file included with the extension.

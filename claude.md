# Claude Design Log - RSNA Anonymizer MCP Wrapper

## 1. Purpose
This document is the canonical reference for the lightweight MCP server that wraps the RSNA DICOM Anonymizer codebase. Every agent who works on this integration must read and extend this file so context is preserved across toolchains (Claude, GPT, etc.).

## 2. Operating Context
- The user already has a separate "DICOM MCP" that queries/filter/downloads studies into a local download folder.
- This new MCP focuses solely on anonymization of those downloaded files; no GUI is exposed, and end users never deal with "projects".
- All work is performed locally (no AWS exports, no remote SCP, no secret management).

## 3. Goals
1. Provide a minimal MCP server interface that:
   - Reads configuration from a YAML file.
   - Instantiates the existing RSNA anonymizer controllers headlessly.
   - Processes DICOM files from a configured input folder and writes anonymized copies to an output folder.
2. Offer a simple status/helper method so agents can see how many files were processed or remain.
3. Keep optional logic (quarantine, logging tweaks, pixel-PHI removal) configurable but hidden behind sane defaults.

## 4. Non-goals / Constraints
- No GUI orchestration, no Project selection UI, no multi-project awareness.
- No remote networking (AWS S3, remote SCP send, etc.).
- Keep the wrapper as thin as possible; reuse RSNA controllers/models instead of reimplementing anonymization logic.
- Avoid storing secrets in config; everything is filesystem-based.

## 5. High-Level Flow
1. YAML config is loaded on MCP startup.
2. Build a `ProjectModel` using defaults, overriding only the fields provided in YAML (primarily directories and anonymizer toggles).
3. Instantiate `AnonymizerController` with that model.
4. MCP exposes actions:
   - `anonymize_now`: scan the input directory, push every new DICOM into the controller queue, return counts (enqueued, completed, quarantined).
   - `status`: report queue sizes and totals (`patients`, `studies`, `series`, `instances`) plus simple filesystem stats (number of files currently present in input/output folders).
   - (Optional future) `list_pending` or `clear_quarantine`.
5. No SCP server is started; DICOM associations are not needed because files are already downloaded.

## 6. YAML Configuration
Place the config at the repo root (example filename: `anonymizer.mcp.yaml`). Structure:

```yaml
paths:
  input_dir: "C:/data/dicom/downloads"        # required
  output_dir: "C:/data/dicom/anonymized"      # required
  quarantine_dir: "C:/data/dicom/quarantine"  # optional; defaults to <output_dir>/quarantine
  temp_dir: "C:/data/dicom/tmp"               # optional; fallback to system temp

processing:
  recursive_scan: true        # default false; set true to walk subfolders
  remove_pixel_phi: false     # toggles OCR/inpainting worker
  anonymizer_script_path: "assets/scripts/default-anonymizer.script"

identity:
  site_id: "123456"
  uid_root: "1.2.840.113619"

logging:
  level: "INFO"               # overrides anonymizer logger; accepts DEBUG/INFO/WARNING/ERROR

limits:
  max_concurrent_files: 50    # optional throttle; default unlimited (bounded by existing queue logic)
```

Design notes:
- Sections are optional; unspecified fields fall back to `ProjectModel` defaults.
- `input_dir`/`output_dir` are normalized to absolute paths and created if missing.
- The config loader should validate folder existence/permissions and raise MCP-friendly errors.
- `recursive_scan` governs whether we walk nested directories or only look at top-level files; default to `false` to match a typical download folder layout.
- Future extensions (e.g., modality whitelists, custom logging targets) must update this schema here before implementation.

## 7. MCP Surface
| Action          | Request Payload                         | Response                                                 |
|-----------------|-----------------------------------------|----------------------------------------------------------|
| `anonymize_now` | `{ "force_rescan": false }` (optional)  | `{ enqueued, completed, quarantined, duration_ms }`      |
| `status`        | `null`                                  | `{ queue: {datasets, pixel_phi}, totals: {...}, input_files, output_files }` |

Implementation guidelines:
- `force_rescan` can tell the MCP to ignore any local cache and re-attempt every file. Default behavior should skip files already present in output (compare by SOPInstanceUID or filename hash).
- Status counts come from `AnonymizerController.queued()` and `AnonymizerModel.get_totals()` (or equivalent). For filesystem counts, use lightweight globbing.
- All actions must be synchronous and short-lived; if large jobs are running, return progress (queues) rather than blocking.

## 8. Future Work
- Add a filesystem watcher so the MCP can react immediately when the download MCP writes new DICOMs (currently manual `anonymize_now` calls).
- Provide a `list_recent` helper that enumerates the last N anonymized studies with metadata extracted from the model.
- Surface quarantine inspection/cleanup actions.
- Support batching multiple YAML profiles if the user ever needs different download folders (not currently requested).

## 9. Open Questions
- None outstanding as of 2025-10-26; user explicitly wants the simplest flow possible.

> **Maintenance rule:** Whenever you modify the anonymizer MCP wrapper (config schema, actions, behavior), update this document before or along with the change so future agents inherit the same context.

## 10. Implementation Notes (2025-10-26)
- Wrapper code lives in `src/anonymizer_mcp/*` (config loader, state persistence, service orchestrator, and FastMCP server entrypoint).
- The sample config file is `anonymizer.mcp.yaml` at the repo root; the server defaults to this path.
- Run the server with `poetry run python -m anonymizer_mcp.server --config anonymizer.mcp.yaml`. The CLI also accepts `--transport` (`stdio`, `sse`, `streamable-http`) and `--name` to mirror the FastMCP defaults.
- The entrypoint now delegates to `mcp.server.fastmcp.FastMCP`, so protocol negotiation, prompt/resource discovery, and notifications follow the official MCP SDK behavior automatically.
- `AnonymizerService` constructs `ProjectModel`/`AnonymizerController` lazily via `_ensure_controller()`, so MCP startup stays lightweight and the heavy RSNA initialization only runs when a tool is called. The controller import also happens inside that helper, preventing `torch`/`easyocr` from loading unless pixel-PHI is enabled.

## 11. Claude Desktop Configuration
- A ready-to-import Claude Desktop config lives at `claude.desktop.json`. It currently registers two MCPs:
  1. `DicomMCP` – runs the upstream dicom-mcp project via WSL/uv (path: `C:/Users/paulo/Python Projects/dicom-mcp`).
  2. `AnonymizerMCP` – launches this repo’s MCP wrapper with `uv run python -m anonymizer_mcp.server --config anonymizer.mcp.yaml` inside `/mnt/c/Users/paulo/PycharmProjects/rsna anonymizer/anonymizer`.
- Import the file via Claude Desktop → Settings → Advanced → “Open config file,” then merge/replace with the contents of `claude.desktop.json`.
- When editing paths, keep them wrapped in single quotes inside the `bash -lc` argument so Windows paths that include spaces (“Python Projects”, “rsna anonymizer”) resolve correctly inside WSL.

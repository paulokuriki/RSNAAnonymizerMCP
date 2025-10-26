# RSNAAnonymizerMCP

**RSNAAnonymizerMCP** is a thin Model Context Protocol (MCP) wrapper around the official [RSNA DICOM Anonymizer](https://github.com/RSNA/anonymizer). Instead of launching the GUI, this fork exposes the anonymizer headlessly to Claude, GPT, or any MCP client.

- MCP server lives in `src/anonymizer_mcp/` and is powered by [FastMCP](https://github.com/modelcontextprotocol/python-sdk).
- All workflow notes for Claude/Desktop agents live in `claude.md`.
- The original RSNA GUI code is left untouched so we can stay in sync with upstream when needed.

> Need the GUI? Use the upstream repository. Need an MCP tool? Stay here.

## Requirements

- Python **3.12** (matching upstream requirements)
- `uv` or `poetry` for dependency management (examples below use `uv`)
- Access to local DICOM downloads (the anonymizer runs over files you already have)

## Quick start

```bash
git clone https://github.com/paulokuriki/RSNAAnonymizerMCP.git
cd "RSNAAnonymizerMCP/anonymizer"
uv sync              # creates .venv and installs runtime deps
uv run python -m anonymizer_mcp.server --config anonymizer.mcp.yaml
```

The server listens on stdin/stdout (MCP `stdio` transport) and exposes the `status` and `anonymize_now` tools. Claude Desktop, Cursor, or any MCP client can now talk to it.

## Configuration

Create `anonymizer.mcp.yaml` (sample already checked in) to point at your download/output folders:

```yaml
paths:
  input_dir: "./data/downloads"
  output_dir: "./data/anonymized"
  quarantine_dir: "./data/anonymized/private/quarantine"
  temp_dir: "./data/tmp"

processing:
  recursive_scan: true
  remove_pixel_phi: false
  anonymizer_script_path: "src/anonymizer/assets/scripts/default-anonymizer.script"

identity:
  site_id: "123456"
  uid_root: "1.2.840.113619"

logging:
  level: "INFO"

limits:
  max_concurrent_files: 50
```

The wrapper lazily instantiates the heavy RSNA controller, so startup stays fast even on large configs. Individual tool calls trigger file scans and anonymization runs.

## Claude Desktop setup

`claude.desktop.json` contains a ready-to-import configuration that launches this server from Claude Desktop alongside the original DICOM MCP. Import it via **Claude Desktop → Settings → Advanced → Open config file** and merge as needed.

Key command:

```json
"bash", "-lc",
"cd '/mnt/c/Users/paulo/PycharmProjects/rsna anonymizer/anonymizer' && uv run python -m anonymizer_mcp.server --config anonymizer.mcp.yaml"
```

See `claude.md` for full agent context and maintenance rules.

## Development

The MCP wrapper lives entirely in `src/anonymizer_mcp/`. Typical workflow:

1. Create/edit `anonymizer.mcp.yaml` for your paths.
2. `uv run python -m anonymizer_mcp.server --config anonymizer.mcp.yaml` to run the server.
3. Use `uv run pytest` (or upstream’s `poetry run pytest`) if you need to exercise anonymizer internals.
4. Keep `claude.md` in sync whenever you change behavior so future agents inherit the same context.

We track upstream RSNA changes via the `upstream` remote (`https://github.com/RSNA/anonymizer.git`). Rebase or cherry-pick as needed, but keep MCP-specific logic isolated to the new package.

## Licensing

Same as upstream: RSNA-MIRC Public License. See `LICENSE` for details.

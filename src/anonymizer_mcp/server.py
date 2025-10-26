"""FastMCP-based JSON-RPC server for the RSNA anonymizer wrapper."""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from .config import MCPConfig
from .service import AnonymizerService


@dataclass(slots=True)
class ServiceContext:
    """Holds the lazily initialized anonymizer service for MCP lifespan."""

    service: AnonymizerService


def create_anonymizer_mcp_server(config_path: str, name: str = "RSNA Anonymizer MCP") -> FastMCP:
    """Configure a FastMCP server that exposes anonymization helpers."""

    @asynccontextmanager
    async def lifespan(_server: FastMCP):
        config = MCPConfig.from_file(config_path)
        service = AnonymizerService(config)
        try:
            yield ServiceContext(service=service)
        finally:
            service.shutdown()

    mcp = FastMCP(name=name, lifespan=lifespan)

    def _get_service(ctx: Context | None) -> AnonymizerService:
        if ctx is None or ctx.request_context is None or ctx.request_context.lifespan_context is None:
            raise RuntimeError("MCP tool context missing service reference")
        context: ServiceContext = ctx.request_context.lifespan_context
        return context.service

    @mcp.tool()
    def anonymize_now(force_rescan: bool = False, ctx: Context | None = None) -> dict[str, Any]:
        """Scan the input directory, anonymize new files, and report counts."""

        service = _get_service(ctx)
        return service.anonymize_now(force_rescan=force_rescan)

    @mcp.tool()
    def status(ctx: Context | None = None) -> dict[str, Any]:
        """Return anonymizer queue sizes and file-system statistics."""

        service = _get_service(ctx)
        return service.status()

    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RSNA anonymizer MCP server.")
    parser.add_argument(
        "--config",
        default="anonymizer.mcp.yaml",
        help="Path to the YAML configuration file (default: %(default)s).",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default="stdio",
        help="MCP transport to use when running the server (default: %(default)s).",
    )
    parser.add_argument(
        "--name",
        default="rsna-anonymizer-mcp",
        help="Optional server display name (default: %(default)s).",
    )
    args = parser.parse_args()

    server = create_anonymizer_mcp_server(args.config, name=args.name)
    server.run(args.transport)


if __name__ == "__main__":
    main()

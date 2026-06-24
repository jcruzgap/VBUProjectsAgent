"""MCP server entry point — exposes VBU-Projects-Agent tools to Claude Code."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# MCP server implementation using stdio transport
# Requires: pip install mcp  (or anthropic[mcp])

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp import types
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False


def create_server(base_dir: Path) -> "Server":
    if not _MCP_AVAILABLE:
        raise RuntimeError(
            "MCP library not installed. Run: pip install mcp"
        )

    from ..config.loader import load_global_config
    from ..storage.db import init_db
    from ..storage.snapshots import SnapshotManager
    from .tools import (
        tool_read_project_context,
        tool_write_project_context,
        tool_list_project_input_files,
        tool_archive_processed_input,
        tool_save_project_snapshot,
        tool_query_project_history,
        McpToolError,
    )

    cfg = load_global_config(base_dir / "config" / "vbu-agent.yaml", base_dir=base_dir)
    db = init_db(base_dir / cfg.storage.sqlite_path)
    snap_mgr = SnapshotManager(base_dir / cfg.storage.snapshots_path)
    projects_root = base_dir / cfg.projects.root_path

    server = Server("vbu-projects-agent")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="read_project_context",
                description="Read all context files for a project.",
                inputSchema={"type": "object", "properties": {
                    "project_id": {"type": "string"}
                }, "required": ["project_id"]},
            ),
            types.Tool(
                name="write_project_context",
                description="Surgical write to one context file (snapshot-guarded).",
                inputSchema={"type": "object", "properties": {
                    "project_id": {"type": "string"},
                    "file_name": {"type": "string"},
                    "content": {"type": "string"},
                }, "required": ["project_id", "file_name", "content"]},
            ),
            types.Tool(
                name="list_project_input_files",
                description="List pending input files for a project.",
                inputSchema={"type": "object", "properties": {
                    "project_id": {"type": "string"}
                }, "required": ["project_id"]},
            ),
            types.Tool(
                name="archive_processed_input",
                description="Move input files to timestamped archive folder.",
                inputSchema={"type": "object", "properties": {
                    "project_id": {"type": "string"}
                }, "required": ["project_id"]},
            ),
            types.Tool(
                name="save_project_snapshot",
                description="Persist a context snapshot for a project.",
                inputSchema={"type": "object", "properties": {
                    "project_id": {"type": "string"}
                }, "required": ["project_id"]},
            ),
            types.Tool(
                name="query_project_history",
                description="Return time-series data for a project metric.",
                inputSchema={"type": "object", "properties": {
                    "project_id": {"type": "string"},
                    "metric_name": {"type": "string",
                                    "enum": ["overall_percent", "health", "velocity_per_day",
                                             "forecast_date", "monthly_revenue"]},
                }, "required": ["project_id", "metric_name"]},
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        try:
            if name == "read_project_context":
                result = tool_read_project_context(arguments["project_id"], projects_root)
            elif name == "write_project_context":
                result = tool_write_project_context(
                    arguments["project_id"], arguments["file_name"],
                    arguments["content"], projects_root, snap_mgr,
                )
            elif name == "list_project_input_files":
                result = tool_list_project_input_files(arguments["project_id"], projects_root)
            elif name == "archive_processed_input":
                result = tool_archive_processed_input(arguments["project_id"], projects_root)
            elif name == "save_project_snapshot":
                result = tool_save_project_snapshot(
                    arguments["project_id"], projects_root, snap_mgr, db
                )
            elif name == "query_project_history":
                result = tool_query_project_history(
                    arguments["project_id"], arguments["metric_name"], db
                )
            else:
                result = {"error": f"Unknown tool: {name}"}
        except McpToolError as e:
            result = {"error": e.code, "message": str(e)}
        except Exception as e:
            from ..security.redaction import redact
            result = {"error": "InternalError", "message": redact(str(e))}

        return [types.TextContent(type="text", text=json.dumps(result, default=str))]

    return server


def run_server(base_dir: Path | None = None) -> None:
    import asyncio
    bd = base_dir or Path.cwd()
    server = create_server(bd)

    async def _run():
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    asyncio.run(_run())


if __name__ == "__main__":
    run_server()

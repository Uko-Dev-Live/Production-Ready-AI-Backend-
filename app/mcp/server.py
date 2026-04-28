"""
app/mcp/server.py
──────────────────
MCP (Model Context Protocol) Server.

MCP is an open standard that lets AI assistants (Claude, GPT, etc.) call
tools running on YOUR infrastructure. Think of it as a structured plugin
system for AI models.

This server exposes three tools:
  1. get_user_info     — look up a user from our database
  2. list_recent_jobs  — fetch recent AI jobs with their results
  3. run_ai_analysis   — submit a new AI job and wait for the result

When an AI assistant is configured to use this MCP server, it can call
these tools mid-conversation to fetch real data from your system.

Run this file standalone:  python -m app.mcp.server
Or as a Docker service (see docker-compose.yml).
"""

import asyncio
import json
import os
import sys

import structlog
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# MCP SDK
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp import types as mcp_types
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

from app.core.config import settings
from app.models.user import User
from app.models.job import Job
from app.workers.ai_engine import AIEngine

logger = structlog.get_logger(__name__)

# Use a sync engine — MCP tools run in their own process
sync_engine = create_engine(settings.SYNC_DATABASE_URL, pool_pre_ping=True)


def get_user_info_impl(username: str) -> dict:
    """Fetch user profile from the database."""
    with Session(sync_engine) as db:
        user = db.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()

        if not user:
            return {"error": f"User '{username}' not found"}

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
        }


def list_recent_jobs_impl(user_id: int, limit: int = 5) -> dict:
    """Fetch the most recent jobs for a user."""
    with Session(sync_engine) as db:
        jobs = db.execute(
            select(Job)
            .where(Job.user_id == user_id)
            .order_by(Job.created_at.desc())
            .limit(limit)
        ).scalars().all()

        return {
            "jobs": [
                {
                    "id": j.id,
                    "job_type": j.job_type,
                    "status": j.status,
                    "result": j.result,
                    "created_at": j.created_at.isoformat(),
                }
                for j in jobs
            ]
        }


def run_ai_analysis_impl(job_type: str, input_text: str) -> dict:
    """Run an AI analysis synchronously (for direct MCP tool use)."""
    engine = AIEngine()
    try:
        result = engine.run(job_type=job_type, input_text=input_text)
        return {"success": True, "job_type": job_type, "result": result}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def run_mcp_server() -> None:
    """Start the MCP stdio server and register tools."""
    if not MCP_AVAILABLE:
        logger.error(
            "mcp package not installed. Install with: pip install mcp"
        )
        # Run a simple HTTP health endpoint as fallback
        from fastapi import FastAPI
        import uvicorn
        fallback = FastAPI(title="MCP Fallback")

        @fallback.get("/health")
        def health():
            return {"status": "mcp_not_available", "note": "pip install mcp"}

        @fallback.post("/tools/run_ai_analysis")
        def run_analysis(job_type: str, input_text: str):
            return run_ai_analysis_impl(job_type, input_text)

        @fallback.get("/tools/get_user_info")
        def user_info(username: str):
            return get_user_info_impl(username)

        logger.info(
            "MCP fallback HTTP server starting",
            host=settings.MCP_SERVER_HOST,
            port=settings.MCP_SERVER_PORT,
        )
        config = uvicorn.Config(
            fallback,
            host=settings.MCP_SERVER_HOST,
            port=settings.MCP_SERVER_PORT,
        )
        server = uvicorn.Server(config)
        await server.serve()
        return

    # ── Real MCP server (stdio transport) ─────────────────────
    server = Server("ai-backend")

    @server.list_tools()
    async def list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name="get_user_info",
                description="Look up a user by username and return their profile.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "username": {"type": "string", "description": "The username to look up"},
                    },
                    "required": ["username"],
                },
            ),
            mcp_types.Tool(
                name="list_recent_jobs",
                description="List the most recent AI jobs for a given user ID.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "integer", "description": "User's database ID"},
                        "limit": {"type": "integer", "description": "Max jobs to return (default 5)"},
                    },
                    "required": ["user_id"],
                },
            ),
            mcp_types.Tool(
                name="run_ai_analysis",
                description=(
                    "Run an AI analysis task. "
                    "job_type: summarise | sentiment | classify | generate"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_type": {"type": "string"},
                        "input_text": {"type": "string"},
                    },
                    "required": ["job_type", "input_text"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict
    ) -> list[mcp_types.TextContent]:
        if name == "get_user_info":
            result = get_user_info_impl(arguments["username"])
        elif name == "list_recent_jobs":
            result = list_recent_jobs_impl(
                arguments["user_id"], arguments.get("limit", 5)
            )
        elif name == "run_ai_analysis":
            result = run_ai_analysis_impl(
                arguments["job_type"], arguments["input_text"]
            )
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [mcp_types.TextContent(type="text", text=json.dumps(result, indent=2))]

    logger.info("MCP server starting (stdio transport)")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(run_mcp_server())

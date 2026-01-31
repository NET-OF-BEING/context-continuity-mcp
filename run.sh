#!/bin/bash
# Context Continuity Engine MCP Server Launcher

SHARED_DIR="$HOME/.local/share/mcp-servers/shared"
SERVER_DIR="$HOME/.local/share/mcp-servers/custom/context-continuity-mcp"

export PYTHONPATH="$SHARED_DIR/modules:$PYTHONPATH"

exec "$SHARED_DIR/venv/bin/python3" "$SERVER_DIR/context_continuity_server.py"

#!/usr/bin/env python3
"""
Context Continuity Engine MCP Server
Read/query layer over the Context Continuity Engine daemon's data stores.
Does NOT start activity monitoring — the daemon runs separately.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Optional

# Engine location — all data paths resolved against this
ENGINE_DIR = Path.home() / "Documents" / "PythonScripts" / "ContextContinuityEngine"

if ENGINE_DIR.exists():
    sys.path.insert(0, str(ENGINE_DIR))

try:
    from context_engine.storage.activity_db import ActivityDatabase
    from context_engine.vector_db.embeddings import EmbeddingStore
    from context_engine.graph.temporal_graph import TemporalGraph
    from context_engine.prediction.context_predictor import ContextPredictor
    from context_engine.privacy.privacy_filter import PrivacyFilter
    ENGINE_AVAILABLE = True
except ImportError as e:
    print(f"Error: Context engine not found: {e}", file=sys.stderr)
    ENGINE_AVAILABLE = False

import yaml


class ContextContinuityMCPServer:
    """MCP Server providing read/query access to the Context Continuity Engine."""

    def __init__(self):
        self.version = "1.0.0"
        self.db: Optional[ActivityDatabase] = None
        self.embeddings: Optional[EmbeddingStore] = None
        self.graph: Optional[TemporalGraph] = None
        self.predictor: Optional[ContextPredictor] = None
        self.privacy: Optional[PrivacyFilter] = None

        if ENGINE_AVAILABLE:
            self._init_components()

    def _init_components(self):
        """Initialize engine components with absolute paths."""
        try:
            config_path = ENGINE_DIR / "config" / "default_config.yaml"
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)

            # Resolve all data paths as absolute against ENGINE_DIR
            db_path = str(ENGINE_DIR / config["storage"]["database_path"])
            embed_dir = str(ENGINE_DIR / "data" / "embeddings")
            graph_path = str(ENGINE_DIR / "data" / "temporal_graph.pkl")

            self.db = ActivityDatabase(db_path)

            self.embeddings = EmbeddingStore(
                persist_directory=embed_dir,
                collection_name=config["vector_db"]["collection_name"],
                model_name=config["vector_db"]["model"],
            )

            self.graph = TemporalGraph(
                persist_path=graph_path,
                max_nodes=config["graph"]["max_nodes"],
                decay_factor=config["graph"]["decay_factor"],
            )

            self.predictor = ContextPredictor(
                self.db,
                self.embeddings,
                self.graph,
                prediction_window=config["prediction"]["prediction_window"],
                min_confidence=config["prediction"]["min_confidence"],
            )

            self.privacy = PrivacyFilter(config["privacy"])

            print("All engine components initialized", file=sys.stderr)
        except Exception as e:
            print(f"Error initializing components: {e}", file=sys.stderr)
            ENGINE_AVAILABLE_RUNTIME = False

    # ── Tool implementations ────────────────────────────────────────────

    def context_recent_activities(self, hours: int = 24, limit: int = 50) -> dict:
        """Get recent tracked activities."""
        activities = self.db.get_recent_activities(limit=limit, hours=hours)
        return {"status": "success", "count": len(activities), "activities": activities}

    def context_search(self, query: str, limit: int = 10) -> dict:
        """Semantic search across tracked activities."""
        results = self.embeddings.search_similar(query_text=query, n_results=limit)
        return {"status": "success", "count": len(results), "results": results}

    def context_predict(self, activity_description: str, max_results: int = 5) -> dict:
        """Predict relevant context for an activity description."""
        activity = {"window_title": activity_description}
        predictions = self.predictor.predict_context(activity, max_results=max_results)
        return {"status": "success", "count": len(predictions), "predictions": predictions}

    def context_suggestions(self, activity_description: str) -> dict:
        """Get actionable context suggestions for an activity."""
        activity = {"window_title": activity_description}
        suggestions = self.predictor.get_context_suggestions(activity)
        return {"status": "success", "suggestions": suggestions}

    def context_related(self, activity_id: str, max_depth: int = 2) -> dict:
        """Get activities related to a given activity via the temporal graph."""
        related = self.graph.get_related_activities(
            activity_id=activity_id, max_depth=max_depth
        )
        return {"status": "success", "count": len(related), "related": related}

    def context_stats(self) -> dict:
        """Get stats from all engine components."""
        stats = {
            "database": self.db.get_stats(),
            "embeddings": self.embeddings.get_stats(),
            "graph": self.graph.get_stats(),
            "privacy": self.privacy.get_privacy_stats(),
        }
        return {"status": "success", "stats": stats}

    def context_list_contexts(self, limit: int = 20) -> dict:
        """List tracked contexts."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM contexts ORDER BY last_active DESC LIMIT ?", (limit,)
            )
            contexts = [dict(row) for row in cursor.fetchall()]
        return {"status": "success", "count": len(contexts), "contexts": contexts}

    def context_cleanup(self, days: int = 90) -> dict:
        """Remove activity data older than N days."""
        deleted = self.db.cleanup_old_data(days=days)
        return {"status": "success", "deleted_records": deleted, "retention_days": days}

    def context_privacy_blacklist(self, type: str, value: str, action: str) -> dict:
        """Add or remove privacy blacklist entries."""
        if type == "app":
            if action == "add":
                self.privacy.add_blacklist_app(value)
            elif action == "remove":
                self.privacy.remove_blacklist_app(value)
            else:
                return {"status": "error", "message": f"Unknown action: {action}"}
        elif type == "directory":
            if action == "add":
                self.privacy.add_blacklist_directory(value)
            elif action == "remove":
                self.privacy.remove_blacklist_directory(value)
            else:
                return {"status": "error", "message": f"Unknown action: {action}"}
        else:
            return {"status": "error", "message": f"Unknown type: {type}. Use 'app' or 'directory'."}

        return {
            "status": "success",
            "message": f"{action}ed {type} blacklist entry: {value}",
            "current_stats": self.privacy.get_privacy_stats(),
        }

    def context_create_context(self, name: str, description: str = "", tags: list = None) -> dict:
        """Create or update a named context."""
        context_id = self.db.create_or_update_context(
            name=name, description=description, tags=tags
        )
        return {"status": "success", "context_id": context_id, "name": name}

    # ── MCP protocol ────────────────────────────────────────────────────

    TOOLS = [
        {
            "name": "context_recent_activities",
            "description": "Get recent tracked activities from the Context Continuity Engine",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "hours": {"type": "integer", "description": "Look back this many hours (default 24)", "default": 24},
                    "limit": {"type": "integer", "description": "Max activities to return (default 50)", "default": 50},
                },
            },
        },
        {
            "name": "context_search",
            "description": "Semantic search across tracked activities using embeddings",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query text"},
                    "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10},
                },
                "required": ["query"],
            },
        },
        {
            "name": "context_predict",
            "description": "Predict relevant context for an activity description",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "activity_description": {"type": "string", "description": "Description of the current activity"},
                    "max_results": {"type": "integer", "description": "Max predictions (default 5)", "default": 5},
                },
                "required": ["activity_description"],
            },
        },
        {
            "name": "context_suggestions",
            "description": "Get actionable context suggestions (related files, apps, next actions)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "activity_description": {"type": "string", "description": "Description of the current activity"},
                },
                "required": ["activity_description"],
            },
        },
        {
            "name": "context_related",
            "description": "Get activities related to a given activity via the temporal graph",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "activity_id": {"type": "string", "description": "Activity ID to find relations for"},
                    "max_depth": {"type": "integer", "description": "Max graph depth (default 2)", "default": 2},
                },
                "required": ["activity_id"],
            },
        },
        {
            "name": "context_stats",
            "description": "Get statistics from all Context Continuity Engine components",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "context_list_contexts",
            "description": "List tracked work contexts ordered by last active",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max contexts to return (default 20)", "default": 20},
                },
            },
        },
        {
            "name": "context_cleanup",
            "description": "Remove activity data older than N days",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Retain data for this many days (default 90)", "default": 90},
                },
            },
        },
        {
            "name": "context_privacy_blacklist",
            "description": "Add or remove privacy blacklist entries for apps or directories",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["app", "directory"], "description": "Type of blacklist entry"},
                    "value": {"type": "string", "description": "App name or directory path"},
                    "action": {"type": "string", "enum": ["add", "remove"], "description": "Add or remove the entry"},
                },
                "required": ["type", "value", "action"],
            },
        },
        {
            "name": "context_create_context",
            "description": "Create or update a named work context",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Context name"},
                    "description": {"type": "string", "description": "Context description"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags for the context"},
                },
                "required": ["name"],
            },
        },
    ]

    async def handle_request(self, request: dict) -> Optional[dict]:
        """Handle a JSON-RPC 2.0 request."""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        # Notification (no id) — don't send a response
        if request_id is None:
            return None

        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "context-continuity",
                    "version": self.version,
                },
            }
            return {"jsonrpc": "2.0", "id": request_id, "result": result}

        elif method == "notifications/initialized":
            return None

        elif method == "tools/list":
            if not ENGINE_AVAILABLE:
                return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": []}}
            return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": self.TOOLS}}

        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})

            handlers = {
                "context_recent_activities": lambda: self.context_recent_activities(**args),
                "context_search": lambda: self.context_search(**args),
                "context_predict": lambda: self.context_predict(**args),
                "context_suggestions": lambda: self.context_suggestions(**args),
                "context_related": lambda: self.context_related(**args),
                "context_stats": lambda: self.context_stats(),
                "context_list_contexts": lambda: self.context_list_contexts(**args),
                "context_cleanup": lambda: self.context_cleanup(**args),
                "context_privacy_blacklist": lambda: self.context_privacy_blacklist(**args),
                "context_create_context": lambda: self.context_create_context(**args),
            }

            if tool_name not in handlers:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                }

            try:
                result = handlers[tool_name]()
                text = json.dumps(result, indent=2, default=str)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"content": [{"type": "text", "text": text}]},
                }
            except Exception as e:
                error_text = json.dumps({"status": "error", "message": str(e)})
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"content": [{"type": "text", "text": error_text}], "isError": True},
                }

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"},
        }

    async def run(self):
        """Run the MCP server on stdio."""
        print(f"Context Continuity MCP Server v{self.version}", file=sys.stderr)
        print(f"Engine: {'available' if ENGINE_AVAILABLE else 'unavailable'}", file=sys.stderr)

        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            try:
                line = await reader.readline()
                if not line:
                    break

                request = json.loads(line.decode())
                response = await self.handle_request(request)

                if response is not None:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()

            except json.JSONDecodeError as e:
                print(f"Invalid JSON: {e}", file=sys.stderr)
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)


def main():
    server = ContextContinuityMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()

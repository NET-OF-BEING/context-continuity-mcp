# Context Continuity MCP Server

MCP (Model Context Protocol) server that exposes the [Context Continuity Engine](https://github.com/NET-OF-BEING/context-continuity-engine) to AI assistants. Provides **10 tools** for querying activity history, running semantic searches, predicting context, traversing temporal graphs, and managing privacy controls.

This server is a **read/query layer only** — it does not start activity monitoring. The Context Continuity Engine daemon runs separately and populates the data stores that this server reads from.

## Architecture

```
┌─────────────────────┐       stdio (JSON-RPC)       ┌──────────────────────┐
│   AI Assistant       │ ◄──────────────────────────► │  MCP Server (this)   │
│   (Claude, etc.)     │                              │  10 query tools      │
└─────────────────────┘                               └──────────┬───────────┘
                                                                 │ imports
                                                      ┌──────────▼───────────┐
                                                      │  Context Continuity  │
                                                      │  Engine (daemon)     │
                                                      ├──────────────────────┤
                                                      │  SQLite DB           │
                                                      │  Vector Embeddings   │
                                                      │  Temporal Graph      │
                                                      │  Privacy Filter      │
                                                      └──────────────────────┘
```

The server initializes read-only handles to the engine's four core components:

| Component | What it stores |
|-----------|---------------|
| **ActivityDatabase** | Tracked activities in SQLite (window titles, apps, timestamps) |
| **EmbeddingStore** | Vector embeddings for semantic similarity search |
| **TemporalGraph** | Activity relationship graph with temporal decay |
| **ContextPredictor** | ML-based predictions combining all three data sources |

A **PrivacyFilter** sits in front of everything, enforcing app and directory blacklists.

## Tools

### Query Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `context_recent_activities` | Get recent tracked activities | `hours` (default 24), `limit` (default 50) |
| `context_search` | Semantic search across all activities using embeddings | `query` (required), `limit` (default 10) |
| `context_predict` | Predict relevant context for a given activity description | `activity_description` (required), `max_results` (default 5) |
| `context_suggestions` | Get actionable suggestions (related files, apps, next actions) | `activity_description` (required) |
| `context_related` | Traverse the temporal graph to find related activities | `activity_id` (required), `max_depth` (default 2) |
| `context_stats` | Get statistics from all engine components | — |
| `context_list_contexts` | List tracked work contexts ordered by last active | `limit` (default 20) |

### Management Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `context_cleanup` | Remove activity data older than N days | `days` (default 90) |
| `context_privacy_blacklist` | Add/remove privacy blacklist entries | `type` (app\|directory), `value`, `action` (add\|remove) |
| `context_create_context` | Create or update a named work context | `name` (required), `description`, `tags` |

## Prerequisites

- **Context Continuity Engine** — installed and running its daemon to populate data stores
  - Default expected location: `~/Documents/PythonScripts/ContextContinuityEngine/`
- **Python 3.10+**
- **PyYAML** — for reading engine configuration

The server imports directly from the engine's Python packages (`context_engine.*`), so the engine must be installed or on the Python path.

## Setup

### 1. Clone

```bash
git clone https://github.com/NET-OF-BEING/context-continuity-mcp.git
```

### 2. Configure Claude Code

Add to your `~/.mcp.json`:

```json
{
  "mcpServers": {
    "context-continuity": {
      "command": "/path/to/your/venv/bin/python3",
      "args": ["context_continuity_server.py"],
      "cwd": "/path/to/context-continuity-mcp"
    }
  }
}
```

Or use the included launcher script:

```json
{
  "mcpServers": {
    "context-continuity": {
      "command": "/path/to/context-continuity-mcp/run.sh"
    }
  }
}
```

### 3. Verify

Once configured, the AI assistant should have access to all 10 `context_*` tools. Ask it to run `context_stats` to confirm the engine components are connected.

## Configuration

The server reads its data paths from the engine's config file at:

```
ContextContinuityEngine/config/default_config.yaml
```

Key config sections used:

```yaml
storage:
  database_path: "data/activities.db"

vector_db:
  collection_name: "activities"
  model: "all-MiniLM-L6-v2"

graph:
  max_nodes: 10000
  decay_factor: 0.95

prediction:
  prediction_window: 3600
  min_confidence: 0.3

privacy:
  # blacklisted apps and directories
```

## Protocol

Communicates over **stdio** using **JSON-RPC 2.0** per the [MCP specification](https://modelcontextprotocol.io/) (protocol version `2024-11-05`).

- Reads newline-delimited JSON from stdin
- Writes newline-delimited JSON responses to stdout
- Diagnostic messages go to stderr

## Example Usage

Once connected to an AI assistant, you can ask natural language questions like:

- *"What was I working on yesterday?"* → `context_recent_activities`
- *"Find everything related to the API refactor"* → `context_search`
- *"What context is relevant to writing unit tests?"* → `context_predict`
- *"What should I do next on this task?"* → `context_suggestions`
- *"Show me activities connected to this one"* → `context_related`
- *"How much data is being tracked?"* → `context_stats`
- *"Clean up anything older than 60 days"* → `context_cleanup`
- *"Blacklist my banking app from tracking"* → `context_privacy_blacklist`

## Related

- [Context Continuity Engine](https://github.com/NET-OF-BEING/context-continuity-engine) — the core engine and daemon that powers this server

## License

MIT

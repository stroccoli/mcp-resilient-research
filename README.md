# Resilient Research MCP Server

[![CI](https://github.com/stroccoli/mcp-resilient-research/actions/workflows/ci.yml/badge.svg)](https://github.com/stroccoli/mcp-resilient-research/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io)
[![Hosted on Azure](https://img.shields.io/badge/hosted-Azure%20Container%20Apps-0078D4?logo=microsoftazure)](https://mcp-resilient-research.graysmoke-51700ada.eastus.azurecontainerapps.io)

An autonomous, multi-provider web research pipeline exposed as a **Model Context Protocol (MCP)** server.

Give it a **topic** and a **research goal** — it searches the web across multiple providers, scrapes candidate sources, scores their authority and relevance with an LLM, applies configurable constraints, and returns a curated **knowledge graph** with key findings and full provenance. Works with any MCP client: Claude Desktop, VS Code Copilot, Cursor, and more.

> **Live server** — `https://mcp-resilient-research.graysmoke-51700ada.eastus.azurecontainerapps.io/mcp`
> No API key required to connect. Bring your own search/LLM keys or use DuckDuckGo for zero-config research.

---

**Contents:** [Features](#features) · [Use the Hosted Server](#use-the-hosted-server-zero-setup) · [Quick Start](#quick-start) · [Deploy to Azure](#deploy-to-azure-your-own-instance) · [MCP Interface](#mcp-interface) · [Configuration](#configuration) · [Architecture](#project-structure)

---

## Features

- **Multiple search providers** — Brave Search, SerpAPI, DuckDuckGo (auto-fallback via `ProviderRouter`)
- **LLM-based evaluation** — metadata extraction, authority scoring, and relevance assessment via [LiteLLM](https://github.com/BerriAI/litellm) (works with Ollama, OpenAI, Anthropic, etc.)
- **Configurable query generation** — deterministic templates (default) or LLM-generated queries (`QUERY_GENERATION_MODE=llm`)
- **Resilient scraping** — exponential back-off with permanent-failure detection
- **Constraint filtering** — minimum authority level, country allow-list, composite confidence threshold
- **LangGraph pipeline** — each processing step is a discrete, checkpointed graph node; sessions survive server restarts
- **MCP tools and resources** — fully compatible with any MCP client (Claude Desktop, VS Code, etc.)

---

## Quick Start

```bash
# 1. Configure (see Configuration section)
cp .env.example .env   # edit with your keys and preferences

# 2. Run directly with uv (no manual install needed)
uv run resilient-research
```

### MCP Client Configuration (e.g. Claude Desktop)

Add the following to your MCP client config (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "resilient-research": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/mcp-resilient-research",
        "resilient-research"
      ]
    }
  }
}
```

---

## Use the Hosted Server (zero setup)

The server is already running on Azure Container Apps. Point any MCP client directly at it:

```
https://mcp-resilient-research.graysmoke-51700ada.eastus.azurecontainerapps.io/mcp
```

**Claude Desktop** — add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "resilient-research": {
      "type": "http",
      "url": "https://mcp-resilient-research.graysmoke-51700ada.eastus.azurecontainerapps.io/mcp"
    }
  }
}
```

**VS Code Copilot** — add to `.vscode/mcp.json` (or user `settings.json`):

```json
{
  "servers": {
    "resilient-research": {
      "type": "http",
      "url": "https://mcp-resilient-research.graysmoke-51700ada.eastus.azurecontainerapps.io/mcp"
    }
  }
}
```

---

## Deploy to Azure (your own instance)

Requires [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) with the Container Apps extension.

```bash
# 1. Login and install the extension (once)
az login
az extension add --name containerapp

# 2. Create a resource group and Container Apps environment
az group create --name my-rg --location eastus
az containerapp env create --name my-env --resource-group my-rg --location eastus

# 3. Build and push the image (requires Docker + a container registry)
docker build -t <registry>/mcp-resilient-research:latest .
docker push <registry>/mcp-resilient-research:latest

# 4. Deploy
az containerapp create \
  --name mcp-resilient-research \
  --resource-group my-rg \
  --environment my-env \
  --image <registry>/mcp-resilient-research:latest \
  --target-port 8000 \
  --ingress external \
  --env-vars \
      LITELLM_MODEL=gpt-4o-mini \
      OPENAI_API_KEY=secretref:openai-api-key \
  --secrets openai-api-key=<YOUR_OPENAI_KEY>
```

The server exposes `/mcp` (Streamable HTTP) and `/health` on port 8000. Scale-to-zero is supported — set `--min-replicas 0` to keep costs near zero when idle.

---

## MCP Interface

### Tools

| Tool | Description |
|------|-------------|
| `start_autonomous_research` | Start a background research session; returns `session_id` immediately |
| `get_research_status` | Poll progress (sources found / validated / discarded) |
| `get_discarded_logs` | Inspect rejected sources with reasons |

### Resources

| Resource URI | Description |
|--------------|-------------|
| `research://knowledge-graph/{session_id}` | Curated JSON knowledge graph for a completed session |

---

## Configuration

All options are set via environment variables (or a `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `BRAVE_API_KEY` | `""` | Brave Search API key |
| `SERPAPI_KEY` | `""` | SerpAPI key |
| `LITELLM_MODEL` | `ollama/llama3.1` | LiteLLM model string |
| `LITELLM_API_BASE` | `http://localhost:11434` | LiteLLM API base URL |
| `QUERY_GENERATION_MODE` | `deterministic` | `deterministic` or `llm` |
| `MIN_CONFIDENCE_SCORE` | `0.4` | Minimum composite score to persist an artifact |
| `MIN_AUTHORITY_LEVEL` | `Low` | Global authority floor (`High`/`Medium`/`Low`) |
| `AUTHORITY_WEIGHT` | `0.4` | Weight of authority score in composite score |
| `RELEVANCE_WEIGHT` | `0.6` | Weight of relevance score in composite score |
| `MAX_RETRY_COUNT` | `3` | Max retries for transient scrape failures |
| `BACKOFF_BASE_DELAY` | `1.0` | Initial retry wait time in seconds |
| `BACKOFF_MAX_DELAY` | `30.0` | Maximum retry wait time in seconds |
| `DATABASE_PATH` | `./research.db` | SQLite file path |

### Query Generation Modes

**`deterministic`** (default): Builds queries from hand-crafted templates — no LLM call, fully reproducible, fast.

**`llm`**: Asks the configured LLM to generate a diverse set of queries tailored to the topic and research goal. Automatically falls back to deterministic templates if the LLM call fails.

---

## Project Structure

```
resilient_research/
├── server.py               # FastMCP server — tools and resources
├── config.py               # Pydantic settings (env vars / .env)
├── database/
│   ├── connection.py       # aiosqlite connection lifecycle
│   ├── schema.py           # DDL — sessions, artifacts, discards, errors
│   └── repository.py       # Async data-access functions
├── graph/
│   ├── state.py            # ResearchState TypedDict
│   ├── builder.py          # LangGraph assembly and execution entry point
│   ├── edges.py            # Conditional routing functions
│   └── nodes/              # One file per pipeline node
│       ├── generate_queries.py
│       ├── search_web.py
│       ├── pick_next_url.py
│       ├── scrape_url.py
│       ├── extract_metadata.py
│       ├── score_authority.py
│       ├── assess_relevance.py
│       ├── apply_constraints.py
│       ├── save_artifact.py
│       ├── log_discard.py
│       ├── check_completion.py
│       └── handle_error.py
├── services/
│   ├── evaluator.py        # LLM prompts and evaluation helpers
│   ├── scraper.py          # HTTP scraping with resilience
│   ├── resilience.py       # Retry logic and PermanentFailure
│   └── search/
│       ├── base.py         # Abstract provider interface
│       ├── brave.py        # Brave Search adapter
│       ├── duckduckgo.py   # DuckDuckGo adapter
│       ├── serpapi.py      # SerpAPI adapter
│       └── router.py       # ProviderRouter with fallback logic
├── resources/
│   └── knowledge_graph.py  # knowledge-graph resource builder
└── tools/
    ├── start_research.py   # Tool: start_autonomous_research
    ├── get_status.py       # Tool: get_research_status
    └── get_discarded.py    # Tool: get_discarded_logs
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for Mermaid diagrams of the pipeline and component interactions.

---

## Example Output

After a session completes, the `research://knowledge-graph/{session_id}` resource returns a curated JSON document:

```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "topic": "French Revolution",
  "status": "completed",
  "summary": {
    "sources_validated": 8,
    "authority_distribution": { "High": 5, "Medium": 2, "Low": 1 },
    "average_confidence_score": 0.81
  },
  "artifacts": [
    {
      "source_url": "https://www.britannica.com/event/French-Revolution",
      "author": "Peter McPhee",
      "organization": "Encyclopaedia Britannica",
      "country": "US",
      "publication_date": "2024-01-15",
      "authority_level": "High",
      "confidence_score": 0.91,
      "key_findings": [
        "The Revolution began with the Estates-General convocation in May 1789.",
        "Financial crisis from American war debt was a primary trigger.",
        "The Declaration of the Rights of Man was adopted in August 1789."
      ],
      "provenance_metadata": {
        "scraped_at": "2026-05-06T14:32:10Z",
        "content_hash": "sha256:3f4a..."
      }
    }
  ]
}
```

---

## Running Tests

```bash
uv run pytest tests/ -x -q
```

# Video Agent — Architecture

## Overview

An automated multi-agent system that generates short-form AI/tech educational videos
in ByteByteGo style, posts them to YouTube Shorts and Facebook Reels 3x daily,
and monetizes Facebook posts with affiliate links — targeting the Vietnam market.

---

## Agent System (8 Agents)

### 1. Scheduler Agent
- **Type**: Cron-based trigger (no LLM)
- **Schedule**: 8:00 AM / 12:30 PM / 8:00 PM (UTC+7)
- **Jobs**:
  - At start of day, triggers Content Agent to pre-plan 3 different topics
  - Maintains a topic queue — one topic per time slot
  - Keeps a history log to prevent topic repeats
  - Triggers Orchestrator 3x/day with the assigned topic
  - Checks previous pipeline job finished before triggering next

### 2. Orchestrator Agent
- **Model**: `deepseek-r1:14b`
- **Jobs**:
  - Receives topic from Scheduler Agent
  - Coordinates the full pipeline in order
  - Passes state between agents
  - Handles errors and retries
  - Reports final status (YouTube URL + Facebook URL)

### 3. Content Agent
- **Model**: `deepseek-r1:14b`
- **Tools**: Tavily web search
- **Jobs**:
  - Searches web for trending AI/agent topics relevant to Vietnam
  - Picks the best topic for the time slot
  - Writes scene-by-scene plan (scene count, duration, visual description)
  - Writes text overlays per scene (in Vietnamese)
  - Writes YouTube title, description, hashtags (Vietnamese)
  - Writes Facebook caption, hashtags (Vietnamese)
  - Outputs structured JSON scene plan

### 4. Remotion Agent
- **Model**: `deepseek-coder:6.7b`
- **Jobs**:
  - Receives structured scene plan from Content Agent
  - Generates TypeScript React components for each scene
  - Follows ByteByteGo motion style:
    - Clean dark background
    - Bold typography with smooth reveal animations
    - Diagram-heavy: boxes, arrows, flowcharts
    - Color-coded components
    - Step-by-step scene reveals
    - Smooth fade/slide transitions
  - Writes Remotion composition file (9:16 vertical format)
  - Outputs TypeScript files into `/remotion/src/compositions/`

### 5. Render Agent
- **Model**: None (subprocess runner)
- **Jobs**:
  - Calls TypeScript render script via Python subprocess
  - Passes scene data as JSON arguments
  - Runs `@remotion/renderer` to render MP4
  - Saves output to `/outputs/`
  - Returns absolute MP4 file path to Orchestrator

### 6. YouTube Agent
- **Model**: `qwen2.5:7b`
- **Tools**: YouTube Data API v3
- **Jobs**:
  - Receives MP4 path + YouTube metadata from Orchestrator
  - Formats title, description, tags for Shorts (`#Shorts`)
  - Uploads video via YouTube Data API v3
  - Returns YouTube video URL

### 7. Facebook Agent
- **Model**: `qwen2.5:7b`
- **Tools**: Meta Graph API
- **Jobs**:
  - Receives MP4 path + Facebook caption from Orchestrator
  - Uploads Reel to Facebook Page via Meta Graph API
  - Passes post ID to Affiliate Agent
  - Returns Facebook post URL

### 8. Affiliate Agent
- **Model**: `deepseek-r1:7b`
- **Tools**: Shopee Affiliate API / AccessTrade API / Lazada Affiliate API / Tiki API
- **Jobs**:
  - **Before Facebook post**: scans video topic, finds relevant affiliate products
  - Passes product links to Facebook Agent to include in video caption
  - **After Facebook post**: posts a pinned comment with affiliate product links
  - Affiliate networks: Shopee, Lazada, AccessTrade, Tiki (Vietnam market)

---

## Pipeline Flow

```
Scheduler Agent (cron: 8AM / 12:30PM / 8PM UTC+7)
     │
     │  topic for this slot
     ▼
Orchestrator Agent
     │
     ▼
Content Agent
  ├─ web search (Tavily)
  ├─ scene plan (Vietnamese)
  └─ captions per platform
     │
     ▼
Remotion Agent
  └─ generates TSX components (ByteByteGo style)
     │
     ▼
Render Agent
  └─ @remotion/renderer → MP4 (9:16)
     │
     ├────────────────────┐
     ▼                    ▼
YouTube Agent        Affiliate Agent
  └─ upload Shorts        └─ find affiliate products
       │                       │
       ▼                       ▼
  YouTube URL            Facebook Agent
                           ├─ post Reel + affiliate links in caption
                           └─ post ID
                                │
                                ▼
                         Affiliate Agent
                           └─ post pinned comment with product links
```

---

## Tech Stack

| Layer             | Choice                                          |
|-------------------|-------------------------------------------------|
| Agent framework   | LangGraph (orchestration) + LangChain (tools)   |
| Local LLM runtime | Ollama                                          |
| Model (all agents)| `qwen2.5:7b`                                    |
| Web search        | DuckDuckGo (free, no API key)                   |
| Motion graphics   | Remotion + React (TypeScript)                   |
| Render            | `@remotion/renderer` (TypeScript/Node.js)       |
| YouTube upload    | YouTube Data API v3                             |
| Facebook upload   | Meta Graph API                                  |
| Affiliate         | Shopee / Lazada / Tiki (AccessTrade coming later)|
| Language          | Python (agents) + TypeScript (Remotion + render)|
| Target market     | Vietnam (UTC+7, Vietnamese content)             |

---

## LLM Assignment

All agents that require an LLM use a single model: **`qwen2.5:7b`**

> **Why `qwen2.5:7b` for everything?**
> - Single model to pull and maintain — `ollama pull qwen2.5:7b` is all that's needed
> - Only ~5 GB VRAM — runs comfortably on a single consumer GPU
> - Strong enough for Vietnamese content writing, TypeScript/React code generation, metadata formatting, and product-topic matching at this workload
> - Avoids juggling multiple large models (deepseek-r1:14b needed ~10 GB, deepseek-coder:6.7b ~4 GB, deepseek-r1:7b ~5 GB) that would require 20+ GB VRAM concurrently

| Agent       | Model         | Notes                          |
|-------------|---------------|--------------------------------|
| Orchestrator| `qwen2.5:7b`  | Routing, decisions, retries    |
| Content     | `qwen2.5:7b`  | Vietnamese scene plans         |
| Remotion    | `qwen2.5:7b`  | TypeScript/React generation    |
| Render      | None          | Subprocess only                |
| YouTube     | `qwen2.5:7b`  | Metadata formatting            |
| Facebook    | `qwen2.5:7b`  | Caption formatting             |
| Scheduler   | None          | Pure cron logic                |
| Affiliate   | `qwen2.5:7b`  | Product-topic matching         |

---

## Hardware Requirements

| Model        | VRAM   |
|--------------|--------|
| `qwen2.5:7b` | ~5 GB  |

Minimum recommended: **16GB VRAM GPU** to run models concurrently.

---

## Project Structure

```
video-agent/
├── architecture.md
├── .env.example
├── pyproject.toml
│
├── agents/                        # LangGraph agent nodes
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── content.py
│   ├── remotion_agent.py
│   ├── render.py
│   ├── youtube.py
│   ├── facebook.py
│   ├── scheduler.py
│   └── affiliate.py
│
├── tools/                         # LangChain tools
│   ├── __init__.py
│   ├── web_search.py              # Tavily search tool
│   ├── youtube_api.py             # YouTube Data API v3
│   ├── facebook_api.py            # Meta Graph API
│   └── affiliate_api.py           # Shopee / AccessTrade / Lazada / Tiki
│
├── graph/                         # LangGraph pipeline definition
│   ├── __init__.py
│   └── pipeline.py                # graph nodes, edges, conditional routing
│
├── state/                         # LangGraph shared state
│   ├── __init__.py
│   └── pipeline_state.py          # PipelineState TypedDict
│
├── config/
│   ├── settings.py                # env vars, model names, API keys
│   └── prompts/
│       ├── content_agent.py
│       ├── remotion_agent.py
│       └── affiliate_agent.py
│
├── remotion/                      # TypeScript Remotion project
│   ├── package.json
│   ├── tsconfig.json
│   ├── remotion.config.ts
│   └── src/
│       ├── index.ts
│       ├── Root.tsx
│       ├── compositions/          # generated per video
│       │   └── VideoComposition.tsx
│       ├── components/            # reusable ByteByteGo-style components
│       │   ├── Scene.tsx
│       │   ├── TextOverlay.tsx
│       │   ├── DiagramBox.tsx
│       │   └── Arrow.tsx
│       └── styles/
│           └── theme.ts           # colors, fonts, animation constants
│
├── outputs/                       # rendered MP4 files
└── logs/                          # pipeline run logs
```

---

## Daily Schedule

| Slot      | Time (UTC+7) | Topic        |
|-----------|--------------|--------------|
| Morning   | 08:00 AM     | Topic 1      |
| Afternoon | 12:30 PM     | Topic 2      |
| Evening   | 08:00 PM     | Topic 3      |

Topics are pre-planned at start of day — 3 unique trending AI/agent topics per day,
no repeats tracked in history log.

---

## Facebook Affiliate Strategy

Each Facebook Reel post includes affiliate links in two places:

1. **Video caption** — included at upload time
2. **Pinned comment** — posted immediately after upload

Example caption:
```
🤖 AI Agent là gì? Tìm hiểu ngay!
#AIAgent #CôngNghệAI #HọcAI

🛒 Khoá học AI được recommend:
👉 [Shopee link]
👉 [Tiki link]
```

Example pinned comment:
```
📚 Tài nguyên học AI mình recommend:
1. Khoá học Python AI - [AccessTrade link]
2. Sách AI cơ bản - [Tiki link]
3. Laptop cho học AI - [Lazada link]
```

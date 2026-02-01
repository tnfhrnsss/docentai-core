# Docent AI Core - Architecture

This document provides a comprehensive overview of the Docent AI Core system architecture, including component diagrams, data flows, and deployment architecture.

---

## Table of Contents

- [System Overview](#system-overview)
- [Component Architecture](#component-architecture)
- [API Request Flow](#api-request-flow)
- [Explanation Processing Flow](#explanation-processing-flow)
- [Database Schema](#database-schema)
- [Technology Stack](#technology-stack)

---

## System Overview

Docent AI Core is an AI-powered backend API that provides intelligent context and explanations for video subtitles.
It integrates with Chrome Extensions to enhance the viewing experience on platforms like Netflix and YouTube.

**Key Capabilities:**
- Real-time subtitle context analysis
- AI-powered explanations using Google Gemini
- Built-in web search via Gemini Search Grounding
- Screenshot-based multimodal context enhancement
- User session management
- 2-step architecture for cost optimization

---

## Component Architecture

```mermaid
graph LR
    subgraph "app/"
        MAIN[main.py<br/>FastAPI App]

        subgraph "routers/"
            R1[auth.py]
            R2[videos.py]
            R3[explanations.py]
            R4[images.py]
            R5[settings.py]
            R6[statistics.py]
            R7[debug.py]
        end

        subgraph "client/"
            C1[gemini.py<br/>Gemini Client<br/>+ Search Grounding]
        end

        subgraph "middleware/"
            M1[logging.py<br/>Request Logging]
        end

        AUTH_MOD[auth.py<br/>JWT Handler]

        subgraph "spec/"
            MODELS[models.py<br/>Pydantic Models]
        end

        subgraph "utils/"
            U1[client_ip.py]
        end

        subgraph "tasks/"
            T1[video_reference.py<br/>Background Tasks]
        end
    end

    subgraph "database/"
        DB_INIT[__init__.py<br/>DB Connection]

        subgraph "repositories/"
            REP1[VideoRepository]
            REP2[ImageRepository]
            REP3[RequestRepository]
            REP4[SettingsRepository]
            REP5[SessionRepository]
            REP6[ReferenceRepository]
        end

        subgraph "migrations/"
            MIG[init_db.py<br/>Schema Migrations]
        end
    end

    subgraph "config/"
        SETTINGS[settings.py<br/>Environment Config]
        LOGGING[logging.py<br/>Log Config]
        PROMPTS[prompts/<br/>AI Prompt Templates]
    end

    MAIN --> R1
    MAIN --> R2
    MAIN --> R3
    MAIN --> R4
    MAIN --> R5
    MAIN --> R6
    MAIN --> R7
    MAIN --> M1

    R3 --> C1
    R1 --> AUTH_MOD

    R1 --> REP5
    R2 --> REP1
    R3 --> REP3
    R3 --> REP6
    R4 --> REP2
    R5 --> REP4

    REP1 --> DB_INIT
    REP2 --> DB_INIT
    REP3 --> DB_INIT
    REP4 --> DB_INIT
    REP5 --> DB_INIT
    REP6 --> DB_INIT

    MAIN --> SETTINGS
    MAIN --> LOGGING
    R3 --> PROMPTS

    style MAIN fill:#009485,color:#fff
    style C1 fill:#4285f4,color:#fff
    style DB_INIT fill:#00758f,color:#fff
```

---

## API Request Flow

### 1. Explanation Request Flow (2-Step Architecture)

```mermaid
sequenceDiagram
    participant Client as Chrome Extension
    participant API as FastAPI Server
    participant Auth as Auth Middleware
    participant Router as Explanations Router
    participant Video as Video Repository
    participant Request as Request Repository
    participant Ref as Reference Repository
    participant Gemini as Gemini Client<br/>(with Search Grounding)
    participant DB as SQLite Database

    Client->>API: POST /api/explanations/videos/{video_id}
    Note over Client,API: Headers: Authorization: Bearer {token}<br/>Body: {selectedText, timestamp, metadata}

    API->>Auth: Validate JWT Token
    Auth->>DB: Check Session Exists
    DB-->>Auth: Session Valid
    Auth-->>API: Authenticated User

    API->>Router: Process Explanation Request

    Router->>Video: Get Video Metadata
    Video->>DB: SELECT * FROM da_videos WHERE video_id = ?
    DB-->>Video: Video Data
    Video-->>Router: Video Metadata

    Router->>Request: Check Cache (videoId, selectedText, timestamp)
    Request->>DB: SELECT * FROM da_request WHERE ...
    DB-->>Request: Cached Result or NULL
    Request-->>Router: Cache Result

    alt Cache Hit
        Router-->>Client: Return Cached Explanation
    else Cache Miss
        Router->>Ref: Get Stored References (STEP 1 data)
        Ref->>DB: SELECT * FROM da_videos_reference WHERE video_id = ?
        DB-->>Ref: Grounding Results (from STEP 1)
        Ref-->>Router: Search Grounding Data

        Router->>Router: Load Prompt Template from DB
        Router->>Router: Build Context with References

        Router->>Gemini: Generate Explanation (Text + Image)
        Note over Router,Gemini: Uses stored references from STEP 1<br/>No new search needed
        Gemini-->>Router: AI Generated Explanation

        Router->>Request: Save to Cache
        Request->>DB: INSERT INTO da_request
        DB-->>Request: Success

        Router-->>Client: Return New Explanation
    end
```

### 2. Video Registration Flow (STEP 1: Reference Collection)

```mermaid
sequenceDiagram
    participant Client as Chrome Extension
    participant API as FastAPI Server
    participant Auth as Auth Middleware
    participant Router as Videos Router
    participant Repo as Video Repository
    participant RefRepo as Reference Repository
    participant Task as Background Task
    participant Gemini as Gemini Client<br/>(Search Grounding)
    participant DB as SQLite Database

    Client->>API: POST /api/videos
    Note over Client,API: Body: {videoId, platform, title, season, episode}

    API->>Auth: Validate JWT Token
    Auth-->>API: Authenticated

    API->>Router: Create/Update Video
    Router->>Repo: Check if Video Exists
    Repo->>DB: SELECT * FROM da_videos WHERE video_id = ?
    DB-->>Repo: NULL or Existing Video

    alt Video Exists
        Router->>Repo: Update Video Metadata
        Repo->>DB: UPDATE da_videos SET ...
    else New Video (STEP 1)
        Router->>Repo: Insert Video
        Repo->>DB: INSERT INTO da_videos

        Router->>Task: Trigger Reference Collection
        Note over Task: STEP 1: Collect references once

        Task->>Gemini: Search with Grounding (title + context)
        Note over Gemini: Built-in web search<br/>Returns grounding metadata
        Gemini-->>Task: Search Results + Grounding Chunks

        Task->>RefRepo: Store Grounding Results
        RefRepo->>DB: INSERT INTO da_videos_reference
        Note over DB: Store for reuse in STEP 2
    end

    DB-->>Repo: Success
    Repo-->>Router: Video Data
    Router-->>Client: Response {success: true, data: {...}}
```
---

## Explanation Processing Flow

```mermaid
graph TD
    START([Explanation Request]) --> AUTH{Authenticated?}
    AUTH -->|No| REJECT[Return 401 Unauthorized]
    AUTH -->|Yes| GET_VIDEO[Get Video Metadata]

    GET_VIDEO --> CHECK_CACHE{Cache Exists?}

    CHECK_CACHE -->|Yes| RETURN_CACHE[Return Cached Result]
    RETURN_CACHE --> END([Response])

    CHECK_CACHE -->|No| GET_REF[Get Stored References<br/>from STEP 1]

    GET_REF --> HAS_REF{References<br/>Available?}
    HAS_REF -->|Yes| USE_REF[Use Search Grounding Results]
    HAS_REF -->|No| SKIP_REF[Skip References]

    USE_REF --> LOAD_PROMPT[Load Prompt Template]
    SKIP_REF --> LOAD_PROMPT

    LOAD_PROMPT --> BUILD_CONTEXT[Build Context]
    BUILD_CONTEXT --> |Video Metadata<br/>Stored References<br/>Selected Text<br/>Image Optional| CALL_GEMINI

    CALL_GEMINI[Call Gemini API<br/>Multimodal + Grounding] --> GEMINI_OK{API Success?}

    GEMINI_OK -->|No| ERROR[Return Error]
    ERROR --> END

    GEMINI_OK -->|Yes| PARSE[Parse Response]
    PARSE --> SAVE_CACHE[Save to Cache]
    SAVE_CACHE --> SAVE_STATS[Update Statistics]
    SAVE_STATS --> RETURN[Return Explanation]
    RETURN --> END

    style START fill:#4caf50,color:#fff
    style END fill:#4caf50,color:#fff
    style REJECT fill:#f44336,color:#fff
    style ERROR fill:#f44336,color:#fff
    style CALL_GEMINI fill:#4285f4,color:#fff
    style RETURN_CACHE fill:#ff9800,color:#fff
    style GET_REF fill:#ff9800,color:#fff
```

---

## Database Schema
### Core Tables

- `videos` - Video metadata
- `sessions` - JWT authentication
- `requests` - Explanation cache
- `references` - Search Grounding results
- `images` - Uploaded screenshots
- `settings` - App configuration

** Database Schema:** [DATABASE.md](DATABASE.md)

---

## Technology Stack

```mermaid
graph LR
    subgraph "Frontend"
        FE1[Chrome Extension<br/>JavaScript/TypeScript]
    end

    subgraph "Backend"
        BE1[FastAPI<br/>Python 3.9+]
        BE2[Uvicorn<br/>ASGI Server]
        BE3[Pydantic<br/>Data Validation]
    end

    subgraph "Database"
        DB1[(SQLite<br/>Production)]
    end

    subgraph "AI/ML"
        AI1[Google Gemini API<br/>generativeai 0.3.2+]
        AI2[Search Grounding<br/>Built-in]
    end

    subgraph "Authentication"
        AUTH1[PyJWT 2.8.0<br/>JWT Tokens]
    end

    subgraph "Infrastructure"
        INF1[Docker<br/>Containerization]
        INF2[Google Cloud Run<br/>Serverless]
        INF3[GitHub Actions<br/>CI/CD]
    end

    FE1 --> BE1
    BE1 --> BE2
    BE1 --> BE3
    BE1 --> DB1
    BE1 --> AI1
    AI1 --> AI2
    BE1 --> AUTH1
    BE1 --> INF1
    INF1 --> INF2
    INF3 --> INF2

    style BE1 fill:#009485,color:#fff
    style AI1 fill:#4285f4,color:#fff
    style AI2 fill:#4285f4,color:#fff
    style INF2 fill:#4285f4,color:#fff
```

### Key Technologies

| Category | Technology | Purpose |
|----------|-----------|---------|
| **AI/ML** | Google Gemini API | Multimodal AI explanations |
| **Search** | Gemini Search Grounding | Built-in web search (no separate API needed) |
| **Backend** | FastAPI | High-performance async API framework |
| **Database** | SQLite | Serverless, production-ready database |
| **Auth** | PyJWT | JWT token authentication |
| **Deployment** | Cloud Run | Serverless container deployment |
| **CI/CD** | GitHub Actions | Automated deployment pipeline |

---

## Data Flow Examples

### 1. Complete Video Explanation Flow (2-Step Architecture)

```
STEP 1: Video Registration (Once per video)
─────────────────────────────────────────────
Chrome Extension
    ↓ [POST /api/auth/sessions]
FastAPI (Create Session)
    ↓ [Generate JWT, Store Session]
SQLite (da_session table)
    ↓ [Return sessionId + token]
Chrome Extension (Store token)
    ↓ [POST /api/videos]
FastAPI (Register Video)
    ↓ [Store video metadata]
SQLite (da_videos table)
    ↓ [Background: Search with Grounding]
Gemini API (Search Grounding enabled)
    ↓ [Returns grounding chunks + metadata]
SQLite (da_videos_reference table)
    ✓ [Store for reuse - STEP 1 complete]

STEP 2: Generate Explanations (Many times per video)
────────────────────────────────────────────────────
Chrome Extension
    ↓ [POST /api/explanations/videos/{videoId}]
FastAPI (Check cache → miss)
    ↓ [Load stored references from STEP 1]
SQLite (da_videos_reference, da_settings tables)
    ↓ [Build context with stored grounding data]
FastAPI (Prepare prompt + references + image)
    ↓ [Generate explanation - no new search needed]
Gemini API (Multimodal generation)
    ↓ [Store result in cache]
SQLite (da_request table)
    ↓ [Return explanation]
Chrome Extension (Display)

Benefits:
✓ Search Grounding runs once (STEP 1)
✓ Explanations reuse references (STEP 2)
✓ Cost-effective and fast
```
---

## Key Gemini Features Integration

### 1. Search Grounding

```python
# Enable Search Grounding
from google.generativeai import protos

google_search_tool = protos.Tool(google_search={})
model = genai.GenerativeModel(
    "gemini-2.0-flash-exp",
    tools=[google_search_tool]
)

# Returns grounding_metadata with web sources
response = model.generate_content(prompt)
```

**Benefits:**
- Built-in web search (no separate API)
- Automatic source attribution
Real-time information
- Cost-effective 2-step architecture

### 2. Multimodal Analysis

```python
# Text + Image understanding
content = [
    "Explain this scene:",
    PIL.Image.open("screenshot.jpg")
]
response = model.generate_content(content)
```

**Use Cases:**
- Visual context understanding
- Character identification
- Scene analysis

### 3. Large Context Window

```python
# Entire episode context
prompt = f"""
Video: {video_metadata}
References: {grounding_results}
History: {conversation_history}
Selected: {subtitle_text}

Explain...
"""
```

---

## References

- [Google Gemini API Documentation](https://ai.google.dev/docs)
- [Gemini Search Grounding Guide](https://ai.google.dev/gemini-api/docs/grounding)
- [FastAPI Documentation](https://fastapi.tiangolo.com)



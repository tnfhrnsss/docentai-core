# Database Guide

SQLite database integration and usage guide for DocentAI.

## Table of Contents

- [Configuration](#configuration)
- [Installation & Setup](#installation--setup)
- [Database Schema](#database-schema)
- [Repository Usage](#repository-usage)
- [Database Management](#database-management)
- [Performance Optimization](#performance-optimization)

## Configuration

### 1. Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

`.env` file example:

```env
# Database
DATABASE_PATH=./data/docent.db
DATABASE_ECHO=false  # Set to true for SQL query logging

# Server
HOST=0.0.0.0
PORT=8001

# Logging
LOG_LEVEL=INFO
```

### 2. Database Configuration

Configure SQLite settings in `config/database.yml`:

```yaml
database:
  path: "./data/docent.db"
  echo: false
  journal_mode: "WAL"  # Write-Ahead Logging for better concurrency
  foreign_keys: true
  check_same_thread: false
  timeout: 30
```

## Installation & Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Test Database

```bash
python test_db.py
```

### 3. Start Server

```bash
python -m app.main
```

Or with uvicorn:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

The database will be automatically initialized on server startup.

## Database Schema

### 1. da_settings (Application Settings)

Stores application configuration and prompt templates.

```sql
CREATE TABLE da_settings (
    id TEXT UNIQUE NOT NULL,              -- Setting identifier (e.g., 'explain_prompt')
    setting_value TEXT NOT NULL,          -- Setting value
    metadata TEXT,                         -- JSON metadata
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 2. da_videos (Video Metadata)

Stores video information from various platforms.

```sql
CREATE TABLE da_videos (
    video_id TEXT PRIMARY KEY NOT NULL,   -- Video ID (Netflix, YouTube, etc.)
    platform TEXT NOT NULL,                -- Platform (netflix, youtube)
    title TEXT,                            -- Video title
    metadata TEXT,                         -- JSON metadata (season, episode, etc.)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 3. da_videos_reference (Search References)

Stores search grounding results and external references.

```sql
CREATE TABLE da_videos_reference (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    reference BLOB NOT NULL,               -- JSON: search results from Gemini
    metadata TEXT,                         -- JSON metadata
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES da_videos(video_id) ON DELETE CASCADE,
    UNIQUE(id, video_id)
);

-- Index for faster lookups
CREATE INDEX idx_reference_video_id ON da_videos_reference(video_id);
```

### 4. da_session (User Sessions)

Manages user authentication and session tokens.

```sql
CREATE TABLE da_session (
    session_id TEXT UNIQUE NOT NULL,       -- Unique session identifier
    token TEXT,                            -- Authentication token
    metadata TEXT,                         -- JSON metadata (user agent, IP, etc.)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT                        -- Session expiration time
);

-- Index for expiration cleanup
CREATE INDEX idx_session_expires ON da_session(expires_at);
```

### 5. da_images (Image Metadata)

Stores uploaded image metadata and storage paths.

```sql
CREATE TABLE da_images (
    image_id TEXT PRIMARY KEY,             -- Unique image identifier
    video_id TEXT NOT NULL,                -- Associated video
    depot_path TEXT NOT NULL,              -- Storage path (GCS or local)
    file_size INTEGER,                     -- File size in bytes
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES da_videos(video_id) ON DELETE CASCADE
);

-- Index for video-based queries
CREATE INDEX idx_images_video ON da_images(video_id);
```

### 6. da_request (API Request Log)

Logs API requests for analytics and debugging.

```sql
CREATE TABLE da_request (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,                -- Associated video
    image_id TEXT,                         -- Associated image (optional)
    session_id TEXT NOT NULL,              -- User session
    lang TEXT DEFAULT 'ko',                -- Request language
    created_at DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX idx_request_session ON da_request(session_id);
CREATE INDEX idx_request_video ON da_request(video_id);
CREATE INDEX idx_request_image ON da_request(image_id);
```

## Repository Usage

### VideoRepository

```python
from database import get_db
from database.repositories import VideoRepository

db = get_db()
video_repo = VideoRepository(db.connection)

# CREATE - Create new video
video_repo.create(
    video_id="81234567",
    platform="netflix",
    title="The King: Eternal Monarch",
    metadata={
        "season": 1,
        "episode": 14,
        "duration": 4200
    }
)

# READ - Get video by ID
video = video_repo.get_by_video_id("81234567")
print(video)  # {'video_id': '81234567', 'platform': 'netflix', ...}

# UPDATE - Update video
video_repo.update(
    video_id="81234567",
    title="New Title",
    metadata={"season": 1, "episode": 15}
)

# DELETE - Delete video
video_repo.delete("81234567")

# LIST - Get all videos
videos = video_repo.list_all(platform="netflix", limit=10)

# COUNT - Count videos
count = video_repo.count(platform="netflix")

# EXISTS - Check if video exists
exists = video_repo.exists("81234567")
```

### ReferenceRepository

```python
from database.repositories import ReferenceRepository

ref_repo = ReferenceRepository(db.connection)

# CREATE - Add search reference
ref_repo.create(
    video_id="81234567",
    reference={
        "search_results": [...],
        "grounding_chunks": [...]
    },
    metadata={"source": "gemini_search", "query": "The King drama"}
)

# READ - Get references for video
references = ref_repo.get_by_video_id("81234567")

# UPDATE - Update reference
ref_repo.update(
    reference_id=1,
    reference={"updated_data": "..."}
)

# DELETE - Delete reference
ref_repo.delete(reference_id=1)
```

### SessionRepository

```python
from database.repositories import SessionRepository

session_repo = SessionRepository(db.connection)

# CREATE - Create new session
session_repo.create(
    session_id="user_session_123",
    token="auth_token_abc",
    metadata={"user_agent": "Chrome", "ip": "127.0.0.1"},
    expires_in_hours=24  # Expires in 24 hours
)

# READ - Get session
session = session_repo.get_by_session_id("user_session_123")

# GET VALID - Get only valid (non-expired) session
valid_session = session_repo.get_valid_session("user_session_123")

# UPDATE TOKEN - Refresh token
session_repo.update_token("user_session_123", "new_token_xyz")

# EXTEND - Extend expiration time
session_repo.extend_expiration("user_session_123", extend_hours=24)

# DELETE - Delete session
session_repo.delete("user_session_123")

# CLEANUP - Delete expired sessions
deleted_count = session_repo.delete_expired_sessions()

# COUNT - Count active sessions
count = session_repo.count_active_sessions()
```

### ImageRepository

```python
from database.repositories import ImageRepository

image_repo = ImageRepository(db.connection)

# CREATE - Store image metadata
image_repo.create(
    image_id="img_123",
    video_id="81234567",
    depot_path="gs://bucket/images/img_123.jpg",
    file_size=1024000
)

# READ - Get image by ID
image = image_repo.get_by_image_id("img_123")

# LIST - Get all images for a video
images = image_repo.get_by_video_id("81234567")

# DELETE - Delete image
image_repo.delete("img_123")
```

### SettingsRepository

```python
from database.repositories import SettingsRepository

settings_repo = SettingsRepository(db.connection)

# CREATE - Create new setting
settings_repo.create(
    setting_id="explain_prompt",
    setting_value="You are a helpful assistant...",
    metadata={"version": "1.0", "last_updated": "2024-01-13"}
)

# READ - Get setting
setting = settings_repo.get_by_id("explain_prompt")

# GET VALUE - Get value directly
prompt = settings_repo.get_value("explain_prompt")

# UPSERT - Create or update
settings_repo.upsert(
    setting_id="explain_prompt",
    setting_value="Updated prompt...",
    metadata={"version": "1.1"}
)

# UPDATE - Update existing setting
settings_repo.update(
    setting_id="explain_prompt",
    setting_value="New value"
)

# DELETE - Delete setting
settings_repo.delete("explain_prompt")

# LIST - Get all settings
all_settings = settings_repo.list_all()
```

### RequestRepository

```python
from database.repositories import RequestRepository

request_repo = RequestRepository(db.connection)

# CREATE - Log API request
request_repo.create(
    video_id="81234567",
    image_id="img_123",
    session_id="user_session_123",
    lang="en"
)

# READ - Get request by ID
request = request_repo.get_by_id(request_id=1)

# LIST - Get requests by session
requests = request_repo.get_by_session_id("user_session_123")

# COUNT - Count requests
count = request_repo.count_by_video_id("81234567")

# DELETE - Delete request
request_repo.delete(request_id=1)
```

## Database Management

### Manual Initialization

```python
from database import init_db

init_db()  # Creates tables if they don't exist
```

### Table Recreation

```python
from database.migrations.init_db import drop_tables, create_tables
from database import get_db

db = get_db()

drop_tables(db.connection)    # Drop all tables
create_tables(db.connection)   # Recreate tables
```


## Performance Optimization

### 1. WAL Mode 

Write-Ahead Logging improves concurrent read performance:

```yaml
# config/database.yml
database:
  journal_mode: "WAL"
```

### 2. Indexes

Indexes are automatically created on frequently queried columns:
- `da_videos_reference.video_id`
- `da_session.expires_at`
- `da_images.video_id`
- `da_request.session_id`, `video_id`, `image_id`

### 3. Connection Pooling

FastAPI lifespan manages connection reuse (implemented in `database/connection.py`).


# API Guide

Complete API documentation for DocentAI Core Backend.

---

## Table of Contents

- [Quick Reference](#quick-reference)
- [Authentication](#authentication)
- [Video Management](#video-management)
- [Explanations](#explanations)
- [Image Upload](#image-upload)
- [Settings](#settings)
- [Statistics](#statistics)

---

## Quick Reference

### Documentation URL

```
Production: https://docentai-api-1064006289042.asia-northeast3.run.app/docs
Local: http://localhost:8001/docs
```

### Quick Test

```bash
# Health check (no auth required)
curl http://localhost:8001/health
```

---

## Authentication

All API endpoints (except `/health`) require JWT authentication.

### Get Token

**Endpoint**: `POST /api/auth/token`

**Description**: Create a new JWT token or reuse an existing valid token for the profile.

**Headers**:
- `X-Profile-ID` (required): User's profile identifier (e.g., like a uuid)

**Request**:
```bash
curl -X POST http://localhost:8001/api/auth/token \
  -H "X-Profile-ID: 123_456_789"
```

**Response** (200 OK):
```json
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expiresAt": "2026-02-07T12:00:00Z",
  "sessionId": "sess_abc123xyz",
  "reused": false
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Always `true` for successful requests |
| `token` | string | JWT access token to use in subsequent requests |
| `expiresAt` | string | Token expiration time (ISO 8601) |
| `sessionId` | string | Unique session identifier |
| `reused` | boolean | `true` if existing token was reused, `false` if new token was issued |

**Token Reuse Logic**:
- If a valid (non-expired) token exists for the profile, it will be reused and expiration extended
- Otherwise, a new token is issued
- This prevents creating multiple tokens for the same user

### Use Token

Include the token in `Authorization` header for all authenticated requests:

```bash
curl -X GET http://localhost:8001/api/videos/{videoId} \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Token Details

- **Expiration**: 7 days (configurable via `JWT_EXPIRATION_DAYS`)
- **Algorithm**: HS256
- **Payload**: Contains session ID and profile ID
- **Auto-extension**: Reused tokens have their expiration extended by 7 days

---

## Video Management

### Register Video (STEP 1 of 2-step process)

**Endpoint**: `POST /api/videos`

**Description**:
- Store video metadata in database
- Trigger background task to collect references using Gemini Search Grounding
- Prepare video for explanation requests

**Headers**:
- `Authorization: Bearer {token}` (required)
- `Content-Type: application/json`

**Request**:
```bash
curl -X POST http://localhost:8001/api/videos \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{
    "videoId": "81498621",
    "platform": "netflix",
    "title": "k-pop-demon-hunters",
    "lang": "en",
    "season": 1,
    "episode": 1,
    "duration": 4200
  }'
```

**Request Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `videoId` | string | Yes | Unique video identifier |
| `platform` | string | Yes | Platform name (`netflix`, `youtube`, etc.) |
| `title` | string | Yes | Video title |
| `lang` | string | No | Language code (default: `en`) |
| `season` | integer | No | Season number |
| `episode` | integer | No | Episode number |
| `duration` | integer | No | Duration in seconds |

**Response** (201 Created):
```json
{
  "success": true,
  "data": {
    "videoId": "81498621",
    "platform": "netflix",
    "title": "k-pop-demon-hunters",
    "season": 1,
    "episode": 1,
    "createdAt": "2026-01-31T12:00:00Z",
    "updatedAt": "2026-01-31T12:00:00Z"
  }
}
```

**Important Notes**:
- Reference collection happens in **background** - API returns immediately
- Background task uses Gemini Search Grounding to collect web references
- References are stored in `da_videos_reference` table
- If video already exists, metadata is updated and new references are NOT collected (prevents duplication)

---

## Explanations

### Generate Explanation (STEP 2 of 2-step process)

**Endpoint**: `POST /api/explanations/videos/{videoId}`

**Description**:
- Load stored references from STEP 1
- Build context with subtitle history, metadata, and references
- Call Gemini AI for multimodal explanation
- Return AI-generated explanation with sources

**Headers**:
- `Authorization: Bearer {token}` (required)
- `Content-Type: application/json`

**Path Parameters**:
- `videoId`: Video identifier (must be registered via `/api/videos` first)

**Request**:
```bash
curl -X POST http://localhost:8001/api/explanations/videos/81498621 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d "{
    "selectedText": "Okay, time for our pre-game ramyeon!",
    "timestamp": 992.5,
    "language": "en",
    "context": [
      {
        "text": "Okay, time for our pre-game ramyeon!",
        "timestamp": 990.0,
        "nonVerbalCues": [\"[밝은 음악]\"]
      }
    ],
    "currentSubtitle": {
      "text": "Happy fans, happy Honmoon!", 
      "timestamp": "244.354693", 
      "nonVerbalCues": []
    },
    "imageId": "img_abc123",
    "title": "k-pop-demon-hunters",
    "platform": "netflix",
    "metadata": {
      "episode": 1,
      "season": 1
    }
  }'
```

**Request Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `selectedText` | string | Yes | Current subtitle text to explain |
| `timestamp` | number | Yes | Timestamp in seconds |
| `language` | string | No | Response language (default: `en`) |
| `context` | array | No | Previous subtitles for conversation context (max 10) |
| `context[].text` | string | - | Subtitle text |
| `context[].timestamp` | number | - | Timestamp |
| `context[].nonVerbalCues` | array | - | Sound effects, actions, etc. |
| `currentSubtitle` | object | No | Current subtitle with non-verbal cues |
| `imageId` | string | No | Uploaded screenshot ID for visual context |
| `title` | string | No | Video title (fallback if not in DB) |
| `platform` | string | No | Platform name |
| `metadata` | object | No | Additional metadata |

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "explanation": {
      "text": "이강인이 언급한 '그 사람'은 1994년에 만난 정태을입니다. 처음 만났어요.",
      "sources": [
        {
          "type": "gemini_analysis",
          "title": "AI Analysis"
        },
        {
          "type": "search_grounding",
          "title": "k-pop-demon-hunters -wiki"
        }
      ],
      "references": [
        {
          "timestamp": 2720,
          "description": ""
        }
      ]
    },
    "cached": false,
    "responseTime": 1847
  }
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `explanation.text` | string | AI-generated explanation |
| `explanation.sources` | array | Information sources used |
| `explanation.sources[].type` | string | Source type (`gemini_analysis`, `search_grounding`) |
| `explanation.sources[].title` | string | Source title |
| `explanation.references` | array | Timeline references from video |
| `explanation.references[].timestamp` | number | Reference timestamp in seconds |
| `explanation.references[].description` | string | Reference description |
| `cached` | boolean | Whether result was cached (always `false` currently) |
| `responseTime` | number | Response time in milliseconds |

**Processing Flow**:
1. Validate authentication
2. Load prompt template from database (`explain_prompt` setting)
3. Get or create video metadata (priority: DB > request body)
4. Load stored references from STEP 1
5. Load image file if `imageId` provided
6. Build context string (subtitles + metadata + references)
7. Call Gemini AI with multimodal input
8. Log request to database
9. Return explanation

---

## Image Upload

### Upload Screenshot

**Endpoint**: `POST /api/upload/{videoId}`

**Description**: Upload screenshot for multimodal analysis.

**Headers**:
- `Authorization: Bearer {token}` (required)
- `Content-Type: multipart/form-data`

**Path Parameters**:
- `videoId`: Video identifier (must exist in database)

**Request**:
```bash
curl -X POST http://localhost:8001/api/upload/81498621 \
  -H "Authorization: Bearer {token}" \
  -F "image=@screenshot.jpg"
```

**Form Fields**:
- `image`: Image file (JPG, PNG)

**Response** (200 OK):
```json
{
  "success": true,
  "imageId": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "screenshot.jpg",
  "size": 245678
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `imageId` | string | Unique image identifier (UUID) - use this in explanation requests |
| `filename` | string | Original filename |
| `size` | number | File size in bytes |

**Constraints**:
- Stored in directory specified by `IMAGE_UPLOAD_PATH` env var
- Auto-deleted after 7 days (configurable)
- Max file size: Determined by server configuration
- Supported formats: JPG, PNG

**Storage**:
- File path: `{IMAGE_UPLOAD_PATH}/{imageId}.{extension}`
- Metadata stored in `da_images` table

---

## Settings

### Get Setting

**Endpoint**: `GET /api/settings/{settingId}`

**Description**: Retrieve a specific application setting.

**Headers**:
- `Authorization: Bearer {token}` (required)

**Path Parameters**:
- `settingId`: Setting identifier (e.g., `explain_prompt`)

**Request**:
```bash
curl -X GET http://localhost:8001/api/settings/explain_prompt \
  -H "Authorization: Bearer {token}"
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "setting_id": "explain_prompt",
    "setting_value": "You are an expert video docent explaining subtitles...",
    "metadata": {
      "description": "Prompt template for explanation API",
      "version": "1.0"
    },
    "created_at": "2026-01-31T12:00:00Z",
    "updated_at": "2026-01-31T12:00:00Z"
  }
}
```

### Update Setting

**Endpoint**: `PUT /api/settings/{settingId}`

**Description**: Update an application setting value.

**Headers**:
- `Authorization: Bearer {token}` (required)
- `Content-Type: application/json`

**Path Parameters**:
- `settingId`: Setting identifier

**Request**:
```bash
curl -X PUT http://localhost:8001/api/settings/explain_prompt \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{
    "settingValue": "New prompt template..."
  }'
```

**Request Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `settingValue` | string | Yes | New setting value |

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Setting 'explain_prompt' updated successfully"
}
```

**Common Settings**:
- `explain_prompt`: AI prompt template for explanations

---

## Statistics

### Get Request Statistics

**Endpoint**: `GET /api/statistics/requests`

**Description**: Retrieve overall request statistics.

**Headers**:
- `Authorization: Bearer {token}` (required)

**Request**:
```bash
curl -X GET http://localhost:8001/api/statistics/requests \
  -H "Authorization: Bearer {token}"
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "totalRequests": 15420,
    "byLanguage": {
      "ko": 12500,
      "en": 2920
    },
    "withImages": 3200,
    "withoutImages": 12220
  }
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `totalRequests` | number | Total number of explanation requests |
| `byLanguage` | object | Requests grouped by response language |
| `withImages` | number | Requests with image context |
| `withoutImages` | number | Requests without image context |

---

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Missing or invalid authentication token |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource already exists or conflict |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Temporary service outage (e.g., Gemini API down) |

### Common Error Codes

| Error Code | Description | Solution |
|------------|-------------|----------|
| `INVALID_TOKEN` | JWT token is invalid or malformed | Get new token via `/api/auth/token` |
| `TOKEN_EXPIRED` | JWT token has expired | Get new token via `/api/auth/token` |
| `MISSING_HEADER` | Required header missing | Add `X-Profile-ID` or `Authorization` header |
| `VIDEO_NOT_FOUND` | Video not found in database | Register video via `/api/videos` first |
| `SETTING_NOT_FOUND` | Setting not found | Check setting ID |
| `GEMINI_API_ERROR` | Gemini API call failed | Check API key and quota |
| `FILE_TOO_LARGE` | Uploaded file exceeds size limit | Reduce image file size |

### Example Error Responses

**401 Unauthorized** (Missing token):
```json
{
  "detail": "Not authenticated"
}
```

**400 Bad Request** (Validation error):
```json
{
  "detail": [
    {
      "loc": ["body", "selectedText"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**404 Not Found** (Video not found):
```json
{
  "detail": "Video not found: netflix_81234567"
}
```

**500 Internal Server Error** (Gemini API error):
```json
{
  "detail": "Failed to generate explanation: API quota exceeded"
}
```

---

## Best Practices

### 1. Token Management

```bash
# Store token in environment variable
export DOCENT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Use in requests
curl -H "Authorization: Bearer $DOCENT_TOKEN" \
  http://localhost:8001/api/videos
```

### 2. Video Registration

```bash
# Always register video FIRST (STEP 1)
curl -X POST http://localhost:8001/api/videos \
  -H "Authorization: Bearer $DOCENT_TOKEN" \
  -d '{"videoId": "netflix_123", "platform": "netflix", "title": "My Show"}'

# Then request explanations (STEP 2) - references will be available
curl -X POST http://localhost:8001/api/explanations/videos/netflix_123 \
  -H "Authorization: Bearer $DOCENT_TOKEN" \
  -d '{"selectedText": "그때 그 사람이었어", "timestamp": 100}'
```

### 3. Non-Verbal Cues

Include non-verbal cues for better context:

```json
{
  "currentSubtitle": {
    "text": "무슨 일이야?",
    "timestamp": 100.0,
    "nonVerbalCues": [
      "[긴장감 있는 음악]",
      "(놀란 표정)",
      "[발소리]"
    ]
  }
}
```

### 4. Error Handling

```python
import requests

try:
    response = requests.post(
        "http://localhost:8001/api/explanations/videos/netflix_123",
        headers={"Authorization": f"Bearer {token}"},
        json={"selectedText": "...", "timestamp": 100}
    )
    response.raise_for_status()
    data = response.json()
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 404:
        # Video not found - register it first
        print("Register video first via /api/videos")
    elif e.response.status_code == 401:
        # Token expired - get new token
        print("Get new token via /api/auth/token")
    else:
        print(f"Error: {e.response.json()}")
```

---

**Last Updated**: 2026-01-31
**API Version**: v1
**Maintained By**: tnfhrns(jhsim)

# Backend Server 개발 명세서
## Subtitle Context Explainer - Backend API & Worker

---

## 📋 목차
1. [프로젝트 개요](#프로젝트-개요)
2. [시스템 아키텍처](#시스템-아키텍처)
3. [기술 스택](#기술-스택)
4. [데이터베이스 설계](#데이터베이스-설계)
5. [API 명세](#api-명세)
6. [백그라운드 워커](#백그라운드-워커)
7. [외부 서비스 연동](#외부-서비스-연동)
8. [성능 최적화](#성능-최적화)
9. [배포 및 운영](#배포-및-운영)
10. [비용 산정](#비용-산정)

---

## 프로젝트 개요

### 목적
Chrome Extension에서 요청하는 자막 설명을 빠르게 제공하기 위한 Backend API 서버 및 영상 사전 분석을 위한 Background Worker 시스템

### 핵심 요구사항
1. **실시간 API 응답**: 2-3초 이내 설명 제공
2. **백그라운드 분석**: 영상당 5분 이내 사전 처리
3. **확장성**: 동시 사용자 1,000명 지원
4. **비용 효율**: Gemini API 호출 최소화

---

## 시스템 아키텍처

### 전체 구조도

```
┌─────────────────────────────────────────────────────┐
│                  Load Balancer                      │
│                   (Nginx/ALB)                       │
└──────────────────┬──────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        ↓                     ↓
┌──────────────┐      ┌──────────────┐
│  API Server  │      │  API Server  │
│   (Node.js)  │      │   (Node.js)  │
└───────┬──────┘      └───────┬──────┘
        │                     │
        └──────────┬──────────┘
                   ↓
        ┌─────────────────────┐
        │   Message Queue     │
        │   (Redis/BullMQ)    │
        └──────────┬──────────┘
                   ↓
        ┌─────────────────────┐
        │  Background Worker  │
        │    (Node.js)        │
        └──────────┬──────────┘
                   │
        ┌──────────┴──────────┐
        ↓                     ↓
┌──────────────┐      ┌──────────────┐
│  PostgreSQL  │      │  Redis Cache │
│  (Main DB)   │      │  (Fast Read) │
└──────────────┘      └──────────────┘
        ↓
┌──────────────┐      ┌──────────────┐
│  Vector DB   │      │   Gemini API │
│  (Qdrant)    │      │   (Google)   │
└──────────────┘      └──────────────┘
```

### 컴포넌트 역할

#### 1. API Server (실시간 응답)
- REST API 제공
- WebSocket 연결 관리
- 캐시된 데이터 조회
- Gemini API 호출

#### 2. Background Worker (비동기 처리)
- 영상 사전 분석
- 자막 다운로드 및 파싱
- 나무위키 크롤링
- 지식 그래프 구축
- 임베딩 생성

#### 3. Message Queue (작업 분배)
- 백그라운드 작업 큐잉
- 실패 시 재시도
- 우선순위 관리

#### 4. PostgreSQL (영구 저장)
- 영상 메타데이터
- 지식 그래프
- 사용자 인터랙션 로그

#### 5. Redis (캐싱)
- API 응답 캐시 (1시간)
- 세션 관리
- Rate Limiting

#### 6. Vector DB (임베딩 검색)
- 자막 세그먼트 벡터
- 유사도 검색

---

## 기술 스택

### Backend
```yaml
Runtime: Node.js 20 LTS
Framework: Express.js 4.18
Language: TypeScript 5.0

주요 라이브러리:
- google-generativeai: Gemini API
- ioredis: Redis 클라이언트
- pg: PostgreSQL 클라이언트
- ws: WebSocket 서버
- bullmq: 작업 큐
- axios: HTTP 클라이언트
- cheerio: HTML 파싱 (크롤링)
```

### Database
```yaml
Main DB: PostgreSQL 15
Cache: Redis 7.2
Vector DB: Qdrant 1.7
```

### Infrastructure
```yaml
Cloud: AWS / GCP
Container: Docker
Orchestration: Kubernetes (optional)
CI/CD: GitHub Actions
Monitoring: Prometheus + Grafana
```

---

## 데이터베이스 설계

### PostgreSQL 스키마

```sql
-- 1. 영상 메타데이터
CREATE TABLE videos (
    id SERIAL PRIMARY KEY,
    video_id VARCHAR(255) UNIQUE NOT NULL,
    platform VARCHAR(50) NOT NULL, -- netflix, youtube
    title VARCHAR(500),
    episode INTEGER,
    season INTEGER,
    duration INTEGER, -- 초 단위
    
    -- 처리 상태
    processed BOOLEAN DEFAULT FALSE,
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    processing_progress INTEGER DEFAULT 0, -- 0-100
    processing_error TEXT,
    
    -- 메타
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_video_id (video_id),
    INDEX idx_processed (processed),
    INDEX idx_platform (platform)
);

-- 2. 자막 데이터
CREATE TABLE subtitles (
    id SERIAL PRIMARY KEY,
    video_id VARCHAR(255) REFERENCES videos(video_id) ON DELETE CASCADE,
    
    start_time FLOAT NOT NULL, -- 초
    end_time FLOAT NOT NULL,
    text TEXT NOT NULL,
    
    segment_index INTEGER, -- 30초 단위 세그먼트 번호
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_video_time (video_id, start_time),
    INDEX idx_segment (video_id, segment_index)
);

-- 3. 자막 세그먼트 분석 결과
CREATE TABLE subtitle_analyses (
    id SERIAL PRIMARY KEY,
    video_id VARCHAR(255) REFERENCES videos(video_id) ON DELETE CASCADE,
    
    segment_index INTEGER NOT NULL,
    start_time FLOAT NOT NULL,
    end_time FLOAT NOT NULL,
    
    -- Gemini 분석 결과
    entities JSONB, -- { characters: [], locations: [], events: [] }
    topics TEXT[],
    complexity INTEGER, -- 1-10
    narrative_importance INTEGER, -- 1-10
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_video_segment (video_id, segment_index)
);

-- 4. 지식 그래프 - 엔티티
CREATE TABLE entities (
    id SERIAL PRIMARY KEY,
    video_id VARCHAR(255) REFERENCES videos(video_id) ON DELETE CASCADE,
    
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50), -- character, location, event, concept
    
    first_appearance_time FLOAT,
    appearances FLOAT[], -- 등장 타임스탬프 배열
    
    -- 외부 지식 (나무위키 등)
    external_info JSONB,
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_video_entity (video_id, name),
    INDEX idx_entity_type (video_id, type)
);

-- 5. 지식 그래프 - 관계
CREATE TABLE relationships (
    id SERIAL PRIMARY KEY,
    video_id VARCHAR(255) REFERENCES videos(video_id) ON DELETE CASCADE,
    
    entity_from_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    entity_to_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    
    relationship_type VARCHAR(100), -- co-appears, related-to, causes, etc.
    strength INTEGER DEFAULT 1,
    
    metadata JSONB, -- 추가 정보
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_video_rel (video_id),
    INDEX idx_entities (entity_from_id, entity_to_id)
);

-- 6. 참조 해결 맵
CREATE TABLE references (
    id SERIAL PRIMARY KEY,
    video_id VARCHAR(255) REFERENCES videos(video_id) ON DELETE CASCADE,
    
    expression VARCHAR(255) NOT NULL, -- "그 사람", "그때"
    timestamp FLOAT NOT NULL,
    
    referent_type VARCHAR(50), -- person, event, thing, time
    referent_id INTEGER, -- entities.id 또는 NULL
    referent_description TEXT,
    
    confidence FLOAT, -- 0.0-1.0
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_video_expr (video_id, expression)
);

-- 7. 외부 지식 캐시
CREATE TABLE external_knowledge (
    id SERIAL PRIMARY KEY,
    
    source VARCHAR(50) NOT NULL, -- namuwiki, wikipedia, fandom
    query VARCHAR(500) NOT NULL,
    
    data JSONB NOT NULL,
    
    fetched_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP, -- TTL
    
    INDEX idx_source_query (source, query),
    INDEX idx_expires (expires_at)
);

-- 8. 사용자 인터랙션 로그
CREATE TABLE user_interactions (
    id SERIAL PRIMARY KEY,
    
    video_id VARCHAR(255),
    selected_text TEXT,
    timestamp FLOAT,
    
    response_time_ms INTEGER,
    cached BOOLEAN,
    
    helpful BOOLEAN, -- 사용자 피드백
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_video (video_id),
    INDEX idx_created (created_at)
);

-- 9. API 캐시 테이블 (선택사항, Redis 백업용)
CREATE TABLE api_cache (
    id SERIAL PRIMARY KEY,
    
    cache_key VARCHAR(500) UNIQUE NOT NULL,
    data JSONB NOT NULL,
    
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    
    INDEX idx_key (cache_key),
    INDEX idx_expires (expires_at)
);
```

### Vector DB (Qdrant) 스키마

```python
# Collection 생성
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
    collection_name="subtitle_embeddings",
    vectors_config=VectorParams(
        size=768,  # Gemini embedding 차원
        distance=Distance.COSINE
    )
)

# 데이터 구조
{
    "id": "video_81234567_seg_45",
    "vector": [0.123, 0.456, ...],  # 768 차원
    "payload": {
        "video_id": "81234567",
        "segment_index": 45,
        "start_time": 1350.0,
        "end_time": 1380.0,
        "text": "그때 그 사람이었어",
        "entities": ["이강인", "정태을"],
        "topics": ["타임슬립", "과거회상"]
    }
}
```

### Redis 키 구조

```
# API 응답 캐시
explain:{videoId}:{selectedText}:{timestamp} -> JSON (TTL: 3600초)

# 영상 처리 상태
video:status:{videoId} -> JSON (TTL: 86400초)

# 세션
session:{sessionId} -> JSON (TTL: 3600초)

# Rate Limiting
ratelimit:{ip}:{endpoint} -> COUNT (TTL: 60초)

# WebSocket 연결
ws:connections:{videoId} -> SET[connectionId]
```

---

## API 명세

### Base URL
```
Production: https://api.yourservice.com
Development: http://localhost:3000
```

### 인증
```
현재 버전: 인증 없음 (퍼블릭 베타)
향후: API Key 또는 JWT
```

### 공통 응답 형식

#### 성공
```json
{
  "success": true,
  "data": { ... }
}
```

#### 실패
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message"
  }
}
```

---

### 1. POST /api/video/register
영상 등록 및 백그라운드 분석 시작

#### 요청
```json
{
  "platform": "netflix",
  "videoId": "81234567",
  "title": "더킹: 영원의 군주",
  "episode": 14,
  "season": 1,
  "duration": 4200,
  "url": "https://www.netflix.com/watch/81234567"
}
```

#### 응답 (처리 시작)
```json
{
  "success": true,
  "data": {
    "status": "processing",
    "jobId": "job_abc123",
    "videoId": "81234567",
    "estimatedTime": 300
  }
}
```

#### 응답 (이미 처리됨)
```json
{
  "success": true,
  "data": {
    "status": "ready",
    "videoId": "81234567",
    "processedAt": "2024-12-30T10:30:00Z"
  }
}
```

#### 에러 코드
- `INVALID_PLATFORM`: 지원하지 않는 플랫폼
- `INVALID_VIDEO_ID`: 유효하지 않은 영상 ID

---

### 2. POST /api/explain
자막 설명 요청 (핵심 API)

#### 요청
```json
{
  "videoId": "81234567",
  "selectedText": "그때 그 사람이었어",
  "timestamp": 992.5,
  "metadata": {
    "title": "더킹: 영원의 군주",
    "episode": 14,
    "platform": "netflix"
  }
}
```

#### 응답 (성공)
```json
{
  "success": true,
  "data": {
    "explanation": {
      "text": "이강인이 언급한 '그 사람'은 1994년에 만난 정태을입니다. 13화 45분에서 만파식적을 통해 과거로 이동했을 때 처음 만났어요.",
      "sources": [
        {
          "type": "namuwiki",
          "title": "더킹: 영원의 군주/등장인물",
          "url": "https://namu.wiki/w/..."
        },
        {
          "type": "video_analysis",
          "title": "14화 자막 분석"
        }
      ],
      "references": [
        {
          "timestamp": 2720,
          "description": "13화 45:20 - 만파식적으로 과거 이동"
        },
        {
          "timestamp": 3130,
          "description": "13화 52:10 - 1994년 태을 첫 만남"
        }
      ]
    },
    "cached": false,
    "responseTime": 2341
  }
}
```

#### 응답 (처리 중)
```json
{
  "success": false,
  "error": {
    "code": "VIDEO_PROCESSING",
    "message": "영상 분석 중입니다. 잠시 후 다시 시도해주세요.",
    "retryAfter": 30
  }
}
```

#### 에러 코드
- `VIDEO_NOT_FOUND`: 영상 정보 없음
- `VIDEO_PROCESSING`: 아직 분석 중
- `GEMINI_API_ERROR`: Gemini API 오류
- `RATE_LIMIT_EXCEEDED`: 요청 제한 초과

---

### 3. GET /api/video/:videoId/status
영상 처리 상태 확인

#### 응답
```json
{
  "success": true,
  "data": {
    "videoId": "81234567",
    "status": "processing", // processing, ready, error
    "progress": 45, // 0-100
    "currentStep": "자막 분석",
    "estimatedTimeRemaining": 120,
    "error": null
  }
}
```

---

### 4. WebSocket: /ws

#### 연결
```javascript
const ws = new WebSocket('wss://api.yourservice.com/ws');
```

#### 구독
```json
{
  "type": "subscribe",
  "videoId": "81234567"
}
```

#### 서버 → 클라이언트 메시지

**진행 상황 업데이트**
```json
{
  "type": "progress",
  "videoId": "81234567",
  "progress": 45,
  "currentStep": "지식 그래프 구축 중"
}
```

**처리 완료**
```json
{
  "type": "complete",
  "videoId": "81234567",
  "processedAt": "2024-12-30T10:35:00Z"
}
```

**오류**
```json
{
  "type": "error",
  "videoId": "81234567",
  "error": {
    "code": "SUBTITLE_DOWNLOAD_FAILED",
    "message": "자막을 다운로드할 수 없습니다."
  }
}
```

---

## 백그라운드 워커

### Worker 구조

```typescript
// worker/index.ts

import { Worker } from 'bullmq';
import { VideoProcessor } from './video-processor';

const worker = new Worker(
  'video-processing',
  async (job) => {
    const processor = new VideoProcessor();
    return await processor.process(job.data);
  },
  {
    connection: redisConnection,
    concurrency: 5, // 동시 처리 작업 수
  }
);

worker.on('completed', (job) => {
  console.log(`✅ Job ${job.id} 완료`);
  notifyClients(job.data.videoId, 'complete');
});

worker.on('failed', (job, err) => {
  console.error(`❌ Job ${job.id} 실패:`, err);
  notifyClients(job.data.videoId, 'error');
});
```

### 처리 파이프라인

```typescript
// worker/video-processor.ts

export class VideoProcessor {
  async process(data: VideoData): Promise<void> {
    const { videoId, title, episode, platform } = data;
    
    try {
      // Step 1: 자막 다운로드 (30초)
      await this.updateProgress(videoId, 10, '자막 다운로드 중');
      const subtitles = await this.downloadSubtitles(videoId, platform);
      
      // Step 2: 자막 세그먼트 분할 (5초)
      await this.updateProgress(videoId, 15, '자막 분석 준비');
      const segments = this.segmentSubtitles(subtitles);
      
      // Step 3: 배치 분석 - Gemini API (2-3분)
      await this.updateProgress(videoId, 20, '자막 분석 중');
      const analyzed = await this.batchAnalyzeSegments(segments, videoId);
      
      // Step 4: 외부 지식 수집 (1-2분)
      await this.updateProgress(videoId, 60, '외부 지식 수집 중');
      const externalKnowledge = await this.fetchExternalKnowledge(title);
      
      // Step 5: 지식 그래프 구축 (30초)
      await this.updateProgress(videoId, 80, '지식 그래프 구축 중');
      const knowledgeGraph = await this.buildKnowledgeGraph(
        analyzed,
        externalKnowledge
      );
      
      // Step 6: 임베딩 생성 & Vector DB 저장 (1분)
      await this.updateProgress(videoId, 90, '임베딩 생성 중');
      await this.generateAndStoreEmbeddings(segments, videoId);
      
      // Step 7: 데이터 저장
      await this.updateProgress(videoId, 95, '데이터 저장 중');
      await this.saveAllData(videoId, {
        subtitles,
        analyzed,
        externalKnowledge,
        knowledgeGraph
      });
      
      // Step 8: 완료
      await this.markComplete(videoId);
      await this.updateProgress(videoId, 100, '완료');
      
    } catch (error) {
      await this.markError(videoId, error);
      throw error;
    }
  }
  
  // 1. 자막 다운로드
  private async downloadSubtitles(
    videoId: string,
    platform: string
  ): Promise<Subtitle[]> {
    if (platform === 'netflix') {
      return await this.netflixSubtitleDownloader.download(videoId);
    }
    throw new Error(`Unsupported platform: ${platform}`);
  }
  
  // 2. 세그먼트 분할 (30초 단위)
  private segmentSubtitles(subtitles: Subtitle[]): Segment[] {
    const segments: Segment[] = [];
    let currentSegment: Segment = {
      index: 0,
      startTime: 0,
      endTime: 30,
      lines: []
    };
    
    for (const subtitle of subtitles) {
      if (subtitle.startTime < currentSegment.endTime) {
        currentSegment.lines.push(subtitle);
      } else {
        segments.push(currentSegment);
        currentSegment = {
          index: currentSegment.index + 1,
          startTime: currentSegment.endTime,
          endTime: currentSegment.endTime + 30,
          lines: [subtitle]
        };
      }
    }
    
    if (currentSegment.lines.length > 0) {
      segments.push(currentSegment);
    }
    
    return segments;
  }
  
  // 3. 배치 분석
  private async batchAnalyzeSegments(
    segments: Segment[],
    videoId: string
  ): Promise<AnalyzedSegment[]> {
    const batchSize = 10;
    const results: AnalyzedSegment[] = [];
    
    for (let i = 0; i < segments.length; i += batchSize) {
      const batch = segments.slice(i, i + batchSize);
      
      // 10개씩 한 번에 Gemini 호출
      const batchPrompt = this.buildBatchPrompt(batch);
      const response = await geminiAPI.generate(batchPrompt);
      const parsed = this.parseBatchResponse(response, batch);
      
      results.push(...parsed);
      
      // 진행률 업데이트
      const progress = 20 + Math.floor((i / segments.length) * 40);
      await this.updateProgress(
        videoId,
        progress,
        `자막 분석 중 (${i}/${segments.length})`
      );
      
      // Rate limit
      await this.sleep(1000);
    }
    
    return results;
  }
  
  // 4. 배치 프롬프트 생성
  private buildBatchPrompt(segments: Segment[]): string {
    return `
다음 ${segments.length}개의 자막 세그먼트를 각각 분석하세요.

${segments.map((seg, i) => `
[Segment ${i}]
시간: ${seg.startTime}초 ~ ${seg.endTime}초
자막: ${seg.lines.map(l => l.text).join(' ')}
`).join('\n')}

각 세그먼트마다 다음을 JSON 배열로 추출:
[
  {
    "segment_index": 0,
    "entities": {
      "characters": ["인물명"],
      "locations": ["장소명"],
      "events": ["사건명"]
    },
    "topics": ["주제1", "주제2"],
    "references": [
      {
        "text": "언급된 표현",
        "referent": "가리키는 대상",
        "type": "person/event/thing"
      }
    ],
    "complexity": 1-10,
    "narrative_importance": 1-10
  },
  ...
]
    `;
  }
  
  // 5. 외부 지식 수집
  private async fetchExternalKnowledge(title: string): Promise<ExternalKnowledge> {
    // 병렬 조회
    const [namuwiki, wikipedia] = await Promise.allSettled([
      this.namuwikiCrawler.fetch(title),
      this.wikipediaAPI.fetch(title)
    ]);
    
    return {
      namuwiki: namuwiki.status === 'fulfilled' ? namuwiki.value : null,
      wikipedia: wikipedia.status === 'fulfilled' ? wikipedia.value : null
    };
  }
  
  // 6. 지식 그래프 구축
  private async buildKnowledgeGraph(
    analyzed: AnalyzedSegment[],
    externalKnowledge: ExternalKnowledge
  ): Promise<KnowledgeGraph> {
    const graph: KnowledgeGraph = {
      entities: new Map(),
      relationships: [],
      timeline: [],
      references: new Map()
    };
    
    // 분석 결과에서 추출
    for (const segment of analyzed) {
      this.addEntitiesToGraph(graph, segment);
      this.inferRelationships(graph, segment);
      this.mapReferences(graph, segment);
    }
    
    // 외부 지식으로 보강
    this.enrichWithExternalKnowledge(graph, externalKnowledge);
    
    return graph;
  }
  
  // 7. 임베딩 생성
  private async generateAndStoreEmbeddings(
    segments: Segment[],
    videoId: string
  ): Promise<void> {
    const embeddings: Embedding[] = [];
    
    for (const segment of segments) {
      const text = segment.lines.map(l => l.text).join(' ');
      
      // Gemini Embedding API
      const vector = await geminiAPI.embed(text);
      
      embeddings.push({
        id: `${videoId}_seg_${segment.index}`,
        vector,
        payload: {
          video_id: videoId,
          segment_index: segment.index,
          start_time: segment.startTime,
          end_time: segment.endTime,
          text
        }
      });
    }
    
    // Qdrant에 저장
    await vectorDB.upsert('subtitle_embeddings', embeddings);
  }
  
  // 8. 진행률 업데이트
  private async updateProgress(
    videoId: string,
    progress: number,
    currentStep: string
  ): Promise<void> {
    // PostgreSQL 업데이트
    await db.query(
      `UPDATE videos 
       SET processing_progress = $1 
       WHERE video_id = $2`,
      [progress, videoId]
    );
    
    // Redis 캐시 업데이트
    await redis.set(
      `video:status:${videoId}`,
      JSON.stringify({ progress, currentStep }),
      'EX',
      86400
    );
    
    // WebSocket 알림
    await this.notifyClients(videoId, {
      type: 'progress',
      progress,
      currentStep
    });
  }
  
  // 9. 완료 표시
  private async markComplete(videoId: string): Promise<void> {
    await db.query(
      `UPDATE videos 
       SET processed = TRUE,
           processing_completed_at = NOW(),
           processing_progress = 100
       WHERE video_id = $1`,
      [videoId]
    );
  }
}
```

---

## 외부 서비스 연동

### 1. Gemini API

#### 설정
```typescript
import { GoogleGenerativeAI } from '@google/generative-ai';

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
const model = genAI.getGenerativeModel({ model: 'gemini-3-pro' });
```

#### 분석 호출
```typescript
async function analyzeSegment(segment: Segment): Promise<Analysis> {
  const prompt = buildPrompt(segment);
  
  const result = await model.generateContent(prompt);
  const response = await result.response;
  const text = response.text();
  
  return JSON.parse(text);
}
```

#### 임베딩 생성
```typescript
async function embedText(text: string): Promise<number[]> {
  const embeddingModel = genAI.getGenerativeModel({ 
    model: 'text-embedding-004' 
  });
  
  const result = await embeddingModel.embedContent(text);
  return result.embedding.values;
}
```

#### 비용 최적화
```typescript
// 배치 처리로 API 호출 횟수 줄이기
async function batchAnalyze(segments: Segment[]): Promise<Analysis[]> {
  const batchPrompt = segments.map((seg, i) => 
    `[Segment ${i}]\n${seg.text}`
  ).join('\n\n');
  
  const result = await model.generateContent(batchPrompt);
  return parseBatchResponse(result);
}
```

---

### 2. 나무위키 크롤러

```typescript
// services/namuwiki-crawler.ts

import axios from 'axios';
import * as cheerio from 'cheerio';

export class NamuwikiCrawler {
  private baseURL = 'https://namu.wiki';
  
  async fetch(title: string): Promise<NamuwikiData | null> {
    try {
      // 캐시 확인
      const cached = await this.checkCache(title);
      if (cached) return cached;
      
      // 페이지 가져오기
      const url = `${this.baseURL}/w/${encodeURIComponent(title)}`;
      const html = await this.fetchPage(url);
      
      // 파싱
      const data = this.parse(html, title);
      
      // 캐싱 (7일)
      await this.saveCache(title, data, 7 * 24 * 60 * 60);
      
      return data;
      
    } catch (error) {
      console.error('나무위키 크롤링 실패:', error);
      return null;
    }
  }
  
  private async fetchPage(url: string): Promise<string> {
    const response = await axios.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
      },
      timeout: 10000
    });
    
    return response.data;
  }
  
  private parse(html: string, title: string): NamuwikiData {
    const $ = cheerio.load(html);
    
    const data: NamuwikiData = {
      title,
      summary: this.extractSummary($),
      sections: this.extractSections($),
      infobox: this.extractInfobox($),
      characters: this.extractCharacters($),
      plot: this.extractPlot($)
    };
    
    return data;
  }
  
  private extractSummary($: cheerio.Root): string {
    const firstParagraph = $('.wiki-paragraph').first();
    return firstParagraph.text().trim();
  }
  
  private extractCharacters($: cheerio.Root): Character[] {
    const characters: Character[] = [];
    
    // "등장인물" 섹션 찾기
    $('h2, h3').each((i, elem) => {
      const heading = $(elem).text();
      
      if (heading.includes('등장인물')) {
        // 다음 섹션까지의 내용 파싱
        let next = $(elem).next();
        
        while (next.length && !next.is('h2, h3')) {
          if (next.is('ul, ol')) {
            next.find('li').each((j, li) => {
              const text = $(li).text();
              const match = text.match(/(.+?):\s*(.+)/);
              
              if (match) {
                characters.push({
                  name: match[1].trim(),
                  description: match[2].trim()
                });
              }
            });
          }
          
          next = next.next();
        }
      }
    });
    
    return characters;
  }
  
  // 캐시 관리
  private async checkCache(title: string): Promise<NamuwikiData | null> {
    const result = await db.query(
      `SELECT data, expires_at 
       FROM external_knowledge 
       WHERE source = 'namuwiki' AND query = $1`,
      [title]
    );
    
    if (result.rows.length > 0) {
      const row = result.rows[0];
      
      // 만료 확인
      if (new Date(row.expires_at) > new Date()) {
        return row.data;
      }
    }
    
    return null;
  }
  
  private async saveCache(
    title: string,
    data: NamuwikiData,
    ttlSeconds: number
  ): Promise<void> {
    const expiresAt = new Date(Date.now() + ttlSeconds * 1000);
    
    await db.query(
      `INSERT INTO external_knowledge (source, query, data, expires_at)
       VALUES ('namuwiki', $1, $2, $3)
       ON CONFLICT (source, query) 
       DO UPDATE SET data = $2, expires_at = $3, fetched_at = NOW()`,
      [title, JSON.stringify(data), expiresAt]
    );
  }
}
```

---

## 성능 최적화

### 1. 캐싱 전략

```typescript
// services/cache-manager.ts

export class CacheManager {
  private redis: Redis;
  
  // API 응답 캐시
  async cacheAPIResponse(
    key: string,
    data: any,
    ttl: number = 3600
  ): Promise<void> {
    await this.redis.setex(
      `explain:${key}`,
      ttl,
      JSON.stringify(data)
    );
  }
  
  async getAPIResponse(key: string): Promise<any | null> {
    const cached = await this.redis.get(`explain:${key}`);
    return cached ? JSON.parse(cached) : null;
  }
  
  // 영상 데이터 캐시
  async cacheVideoData(
    videoId: string,
    data: ProcessedData
  ): Promise<void> {
    await this.redis.setex(
      `video:data:${videoId}`,
      86400, // 24시간
      JSON.stringify(data)
    );
  }
  
  // 캐시 워밍
  async warmCache(videoId: string): Promise<void> {
    // 자주 조회될 데이터를 미리 Redis에 로드
    const preprocessed = await db.getPreprocessedData(videoId);
    await this.cacheVideoData(videoId, preprocessed);
  }
}
```

### 2. Database 최적화

```sql
-- 인덱스 생성
CREATE INDEX CONCURRENTLY idx_subtitles_video_time 
ON subtitles (video_id, start_time);

CREATE INDEX CONCURRENTLY idx_entities_video_name 
ON entities (video_id, name);

-- 파티셔닝 (대용량 데이터 시)
CREATE TABLE user_interactions_2024_12 
PARTITION OF user_interactions
FOR VALUES FROM ('2024-12-01') TO ('2025-01-01');

-- Materialized View (자주 조회되는 통계)
CREATE MATERIALIZED VIEW video_stats AS
SELECT 
  video_id,
  COUNT(*) as interaction_count,
  AVG(response_time_ms) as avg_response_time
FROM user_interactions
GROUP BY video_id;

-- 자동 갱신
REFRESH MATERIALIZED VIEW CONCURRENTLY video_stats;
```

### 3. API 응답 최적화

```typescript
// API에서 병렬 조회
async function explainSubtitle(req: Request): Promise<Response> {
  const { videoId, selectedText, timestamp } = req.body;
  
  // 병렬로 여러 소스에서 데이터 수집
  const [temporal, semantic, entities] = await Promise.all([
    db.getSubtitlesInRange(videoId, timestamp - 60, timestamp + 60),
    vectorDB.searchSimilar(selectedText, videoId),
    db.getEntities(videoId, selectedText)
  ]);
  
  // 컨텍스트 구성
  const context = { temporal, semantic, entities };
  
  // Gemini 호출 (유일한 느린 부분)
  const explanation = await geminiAPI.generate(context);
  
  return explanation;
}
```

### 4. Rate Limiting

```typescript
// middleware/rate-limiter.ts

import rateLimit from 'express-rate-limit';
import RedisStore from 'rate-limit-redis';

export const apiLimiter = rateLimit({
  store: new RedisStore({
    client: redis,
    prefix: 'ratelimit:api:'
  }),
  windowMs: 60 * 1000, // 1분
  max: 30, // 분당 30회
  message: {
    error: {
      code: 'RATE_LIMIT_EXCEEDED',
      message: '요청 제한을 초과했습니다. 잠시 후 다시 시도해주세요.'
    }
  }
});

// 적용
app.use('/api/explain', apiLimiter);
```

---

## 배포 및 운영

### Docker 구성

```dockerfile
# Dockerfile - API Server

FROM node:20-alpine

WORKDIR /app

# 의존성 설치
COPY package*.json ./
RUN npm ci --only=production

# 소스 복사
COPY . .

# 빌드
RUN npm run build

EXPOSE 3000

CMD ["node", "dist/api/index.js"]
```

```dockerfile
# Dockerfile - Worker

FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

CMD ["node", "dist/worker/index.js"]
```

```yaml
# docker-compose.yml

version: '3.8'

services:
  # API Server
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/subtitle_explainer
      - REDIS_URL=redis://redis:6379
      - GEMINI_API_KEY=${GEMINI_API_KEY}
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
  
  # Background Worker
  worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/subtitle_explainer
      - REDIS_URL=redis://redis:6379
      - GEMINI_API_KEY=${GEMINI_API_KEY}
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
  
  # PostgreSQL
  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=subtitle_explainer
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
  
  # Redis
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped
  
  # Qdrant Vector DB
  qdrant:
    image: qdrant/qdrant:v1.7.0
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
```

### 환경 변수

```bash
# .env

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/subtitle_explainer

# Redis
REDIS_URL=redis://localhost:6379

# Vector DB
QDRANT_URL=http://localhost:6333

# Gemini API
GEMINI_API_KEY=your-api-key-here

# Server
PORT=3000
NODE_ENV=production

# Worker
WORKER_CONCURRENCY=5

# Logging
LOG_LEVEL=info
```

### CI/CD (GitHub Actions)

```yaml
# .github/workflows/deploy.yml

name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Run tests
        run: npm test
      
      - name: Build
        run: npm run build
      
      - name: Build Docker images
        run: |
          docker build -t api:latest -f Dockerfile.api .
          docker build -t worker:latest -f Dockerfile.worker .
      
      - name: Push to registry
        run: |
          docker push your-registry/api:latest
          docker push your-registry/worker:latest
      
      - name: Deploy to production
        run: |
          # kubectl apply -f k8s/
          # 또는 docker-compose up -d
```

### 모니터링

```typescript
// monitoring/metrics.ts

import { register, Counter, Histogram } from 'prom-client';

// API 요청 카운터
export const apiRequestCounter = new Counter({
  name: 'api_requests_total',
  help: 'Total API requests',
  labelNames: ['endpoint', 'status']
});

// 응답 시간 히스토그램
export const apiResponseTime = new Histogram({
  name: 'api_response_time_seconds',
  help: 'API response time in seconds',
  labelNames: ['endpoint'],
  buckets: [0.1, 0.5, 1, 2, 5]
});

// Gemini API 호출
export const geminiAPICallCounter = new Counter({
  name: 'gemini_api_calls_total',
  help: 'Total Gemini API calls',
  labelNames: ['type'] // analyze, embed, etc.
});

// 캐시 히트율
export const cacheHitCounter = new Counter({
  name: 'cache_hits_total',
  help: 'Total cache hits',
  labelNames: ['cache_type']
});

// 메트릭 엔드포인트
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});
```

---

## 비용 산정

### Gemini API 비용

```
전제:
- 1시간 드라마 기준
- 자막 세그먼트: 120개 (30초 단위)
- 배치 처리: 10개씩

사전 처리 (영상당 1회):
- 분석 API 호출: 12회 (120/10)
- 임베딩 API 호출: 120회
- 비용: ~$0.50

실시간 처리 (질문당):
- 설명 생성: 1회
- 비용: ~$0.01

캐시 히트율: 70%
실제 비용: $0.01 × 30% = $0.003

월간 예상 (1,000명 사용자):
- 사전 처리: 100 episodes × $0.50 = $50
- 실시간: 1,000 users × 5 questions/day × 30 days × $0.003 = $450
- 총: ~$500/month
```

### 인프라 비용

```
AWS 기준:
- EC2 (API Server): t3.medium × 2 = $60/month
- EC2 (Worker): t3.medium × 1 = $30/month
- RDS PostgreSQL: db.t3.micro = $15/month
- ElastiCache Redis: cache.t3.micro = $12/month
- 데이터 전송: ~$20/month
- 총: ~$137/month

Qdrant Cloud:
- 1GB 벡터: ~$20/month

전체 인프라: ~$157/month
```

### 총 운영 비용

```
월간 (1,000 사용자):
- Gemini API: $500
- 인프라: $157
- 총: ~$657/month

연간:
- 총: ~$7,884/year
```

---

## 확장 계획

### 단기 (1-2개월)
- [ ] 유튜브 지원 추가
- [ ] API 인증 시스템
- [ ] 사용량 통계 대시보드

### 중기 (3-6개월)
- [ ] 다국어 지원
- [ ] 사용자 피드백 수집
- [ ] ML 모델 fine-tuning

### 장기 (6개월+)
- [ ] 다른 OTT 플랫폼
- [ ] 모바일 앱 백엔드
- [ ] 엔터프라이즈 버전

---

## 부록

### A. API 응답 시간 목표

```
캐시 HIT:
- 목표: < 100ms
- 현재: ~25ms ✅

캐시 MISS:
- 목표: < 3초
- 현재: ~2.3초 ✅

백그라운드 처리:
- 목표: < 10분
- 현재: ~5분 ✅
```

### B. 에러 처리 가이드

```typescript
// 에러 타입
enum ErrorCode {
  // Client errors (4xx)
  INVALID_REQUEST = 'INVALID_REQUEST',
  VIDEO_NOT_FOUND = 'VIDEO_NOT_FOUND',
  VIDEO_PROCESSING = 'VIDEO_PROCESSING',
  RATE_LIMIT_EXCEEDED = 'RATE_LIMIT_EXCEEDED',
  
  // Server errors (5xx)
  INTERNAL_ERROR = 'INTERNAL_ERROR',
  GEMINI_API_ERROR = 'GEMINI_API_ERROR',
  DATABASE_ERROR = 'DATABASE_ERROR',
  EXTERNAL_SERVICE_ERROR = 'EXTERNAL_SERVICE_ERROR'
}

// 에러 핸들러
app.use((err, req, res, next) => {
  console.error('Error:', err);
  
  // 에러 코드에 따른 HTTP 상태
  const statusCode = getHTTPStatus(err.code);
  
  res.status(statusCode).json({
    success: false,
    error: {
      code: err.code,
      message: err.message,
      ...(err.retryAfter && { retryAfter: err.retryAfter })
    }
  });
});
```

---

**문서 버전**: 1.0.0  
**최종 수정**: 2024-12-30  
**작성자**: Backend Team

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path

# Import database modules
from database import init_db, close_db, get_db
from database.repositories import SettingsRepository

# Import settings
from config.settings import get_settings
from config.logging import setup_logging

# Import routers
from app.routers import auth, videos, images, explanations, settings, statistics


def init_prompts():
    """Initialize prompt templates in database"""
    db = get_db()
    settings_repo = SettingsRepository(db.connection)

    # Load explain prompt from file
    prompt_file = Path(__file__).parent.parent / "config" / "prompts" / "explain_prompt.txt"

    if prompt_file.exists():
        with open(prompt_file, "r", encoding="utf-8") as f:
            prompt_content = f.read()

        # Upsert prompt to database
        settings_repo.upsert(
            setting_id="explain_prompt",
            setting_value=prompt_content,
            metadata={"description": "Prompt template for explanation API", "version": "1.0"},
        )
        print("✅ Prompt templates initialized")
    else:
        print("⚠️  Warning: explain_prompt.txt not found")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI
    Handles startup and shutdown events
    """
    # Startup: Setup logging
    settings = get_settings()
    setup_logging(
        log_dir="./logs",
        log_level=settings.LOG_LEVEL,
        app_name="docentai"
    )

    # Initialize database
    print("🚀 Starting Docent AI Core API...")
    init_db()

    # Ensure upload directory exists
    upload_path = Path(settings.IMAGE_UPLOAD_PATH)
    upload_path.mkdir(parents=True, exist_ok=True)
    print(f"📁 Upload directory ready: {upload_path}")

    # Initialize prompts
    init_prompts()

    yield
    # Shutdown: Close database connection
    print("👋 Shutting down Docent AI Core API...")
    close_db()


app = FastAPI(
    title="Docent AI Core API",
    description="Subtitle Context Explainer - Backend API (MVP)",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Root endpoints
@app.get("/")
async def root():
    return {
        "service": "Docent AI Core API",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# Include routers
app.include_router(auth.router)
app.include_router(videos.router)
app.include_router(images.router)
app.include_router(explanations.router)
app.include_router(settings.router)
app.include_router(statistics.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)

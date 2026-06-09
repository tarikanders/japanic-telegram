import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import engine, Base
from routers import search, admin, auth, telegram_setup
from routers import exchange, watchlist, archive

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)


def _copy_db_to_tmp() -> bool:
    """Copy DB from GCS FUSE mount to /tmp for fast local reads."""
    import shutil
    src = os.getenv("DATABASE_URL", "").replace("sqlite:////", "/").replace("sqlite:///", "")
    if not src or not src.startswith("/"):
        return False
    dst = "/tmp/japan_auctions.db"
    try:
        shutil.copy2(src, dst)
        size_mb = os.path.getsize(dst) / 1_048_576
        logger.info(f"DB copied to /tmp ({size_mb:.1f} MB) — reads will use local cache")
        return True
    except Exception as e:
        logger.warning(f"DB copy to /tmp failed: {e}")
        return False


async def _init_db_background():
    """Copy DB to /tmp, then init tables and reset stale checkpoint."""
    loop = asyncio.get_event_loop()

    # Copy DB from GCS FUSE to /tmp so SQLite reads hit local disk instead of network
    copied = await loop.run_in_executor(None, _copy_db_to_tmp)
    if copied:
        from database import _switch_to_tmp
        _switch_to_tmp()

    import database as _db_mod
    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, lambda: Base.metadata.create_all(bind=_db_mod.engine)),
            timeout=30.0,
        )
        logger.info("Database tables initialized")
    except asyncio.TimeoutError:
        logger.warning("DB init timed out")
    except Exception as e:
        logger.warning(f"Table creation skipped: {e}")

    from database import SessionLocal
    from models import SyncCheckpoint
    try:
        db = SessionLocal()
        try:
            cp = db.query(SyncCheckpoint).first()
            if cp and cp.status == "running":
                cp.status = "idle"
                db.commit()
                logger.info("Reset stale checkpoint to idle")
        except Exception as e:
            logger.warning(f"Checkpoint reset skipped: {e}")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"DB session failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Yield immediately so uvicorn binds port 8080 before Cloud Run's startup
    # probe fires. DB init (GCS FUSE access) runs in the background.
    asyncio.create_task(_init_db_background())
    yield


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Japan Auction Intelligence", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router)
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(telegram_setup.router)
app.include_router(exchange.router)
app.include_router(watchlist.router)
app.include_router(archive.router)


@app.get("/health")
def health():
    return {"status": "ok"}


STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"error": "Frontend not built"}

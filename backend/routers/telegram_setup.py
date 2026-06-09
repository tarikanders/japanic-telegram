"""
Two-step Telegram authentication via API.
Step 1: POST /api/telegram-setup/request  { phone }   → sends OTP to user's Telegram
Step 2: POST /api/telegram-setup/verify   { code }    → completes auth, saves session

All endpoints require admin JWT (same as /api/admin/*).
"""
import asyncio
import os
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from routers.auth import verify_token

router = APIRouter(prefix="/api/telegram-setup", tags=["telegram-setup"])

_pending_client = None
_pending_phone  = None


class PhoneRequest(BaseModel):
    phone: str


class CodeRequest(BaseModel):
    code: str
    phone_code_hash: str


@router.post("/request")
async def request_code(body: PhoneRequest, _token: dict = Depends(verify_token)):
    global _pending_client, _pending_phone

    api_id   = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    if not api_id or not api_hash:
        raise HTTPException(400, "TELEGRAM_API_ID / TELEGRAM_API_HASH not set in environment")

    try:
        from telethon import TelegramClient
    except ImportError:
        raise HTTPException(500, "telethon not installed")

    backend_dir  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    session_file = os.path.join(backend_dir, "telegram_session")

    if _pending_client:
        try:
            await _pending_client.disconnect()
        except Exception:
            pass

    client = TelegramClient(session_file, int(api_id), api_hash)
    await client.connect()

    result = await client.send_code_request(body.phone)
    _pending_client = client
    _pending_phone  = body.phone

    return {
        "message": f"Code sent to {body.phone}",
        "phone_code_hash": result.phone_code_hash,
    }


@router.post("/verify")
async def verify_code(body: CodeRequest, _token: dict = Depends(verify_token)):
    global _pending_client, _pending_phone

    if not _pending_client:
        raise HTTPException(400, "No pending login session. Call /request first.")

    try:
        from telethon.errors import SessionPasswordNeededError
        await _pending_client.sign_in(
            phone=_pending_phone,
            code=body.code,
            phone_code_hash=body.phone_code_hash,
        )
    except SessionPasswordNeededError:
        raise HTTPException(400, "Two-step verification password required — use telegram_login.py instead")
    except Exception as e:
        raise HTTPException(400, f"Sign-in failed: {e}")

    me = await _pending_client.get_me()
    await _pending_client.disconnect()
    _pending_client = None
    _pending_phone  = None

    return {
        "message": f"Authenticated as {me.first_name} (@{me.username or 'no username'})",
        "session_saved": True,
    }


@router.get("/status")
async def setup_status(_token: dict = Depends(verify_token)):
    backend_dir  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    session_file = os.path.join(backend_dir, "telegram_session.session")
    return {"session_exists": os.path.exists(session_file)}

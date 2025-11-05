import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import (
    User, Role, Product, Affiliate, Strategy, Trade, Video, Job, Audit, ContactMessage, HealthCheck
)

app = FastAPI(title="Autonomous Asset Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------- Utility --------

def _now():
    return datetime.now(timezone.utc)


def _collection(name: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    return db[name]


# -------- Health + Self-Heal --------

@app.get("/api/health", response_model=Dict[str, Any])
def health() -> Dict[str, Any]:
    status = {
        "backend": "ok",
        "time": _now().isoformat(),
        "env": {
            "DATABASE_URL": bool(os.getenv("DATABASE_URL")),
            "DATABASE_NAME": bool(os.getenv("DATABASE_NAME")),
        },
        "database": "ok" if db is not None else "error",
        "collections": [],
    }

    if db is not None:
        try:
            status["collections"] = db.list_collection_names()
        except Exception as e:
            status["database"] = f"error: {str(e)[:80]}"

    return status


@app.post("/api/heal", response_model=Dict[str, Any])
def heal():
    """
    Self-healing routine that ensures critical collections exist, seeds admin role/user if missing,
    and writes an audit record. This is idempotent and safe to call anytime.
    """
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    ensured = []
    # Ensure indexes/collections by simple upserts
    critical = [
        "user", "role", "product", "affiliate", "strategy", "trade", "video", "job", "audit", "contactmessage"
    ]

    for c in critical:
        _collection(c).insert_one({"_ensure": True, "ts": _now()})
        _collection(c).delete_many({"_ensure": True})
        ensured.append(c)

    # Seed admin role
    roles = list(_collection("role").find({"name": "admin"}).limit(1))
    if not roles:
        create_document("role", Role(name="admin", permissions=["*"]).model_dump())

    # Seed admin user
    admins = list(_collection("user").find({"email": "admin@local"}).limit(1))
    if not admins:
        create_document(
            "user",
            User(name="Administrator", email="admin@local", role="admin", settings={"theme": "dark"}).model_dump(),
        )

    # Audit log
    create_document(
        "audit",
        Audit(action="self_heal", actor="system", severity="info", details={"ensured": ensured}).model_dump(),
    )

    return {"status": "ok", "ensured": ensured}


# -------- Users --------

@app.post("/api/users", response_model=Dict[str, Any])
def create_user(user: User):
    user_id = create_document("user", user)
    return {"id": user_id}


@app.get("/api/users", response_model=List[Dict[str, Any]])
def list_users(limit: int = 20):
    return get_documents("user", {}, limit)


# -------- Contact --------

@app.post("/api/contact", response_model=Dict[str, Any])
def submit_contact(msg: ContactMessage):
    msg_id = create_document("contactmessage", msg)
    create_document("audit", Audit(action="contact_submit", actor=msg.email, details={"name": msg.name}).model_dump())
    return {"id": msg_id}


# -------- Trading (mocked) --------

class BacktestRequest(BaseModel):
    symbol: str
    strategy: Strategy
    days: int = 30


@app.post("/api/trades/backtest", response_model=Dict[str, Any])
def backtest(req: BacktestRequest):
    import math
    days = max(5, min(365, req.days))
    # Produce a deterministic mock equity curve for demo purposes
    series = []
    base = 10000.0
    for i in range(days):
        drift = math.sin(i / 6.0) * 50
        noise = math.cos(i / 3.0) * 10
        value = base + i * 12 + drift + noise
        series.append({"t": (datetime.now(timezone.utc) - timedelta(days=(days - i))).isoformat(), "equity": round(value, 2)})
    stats = {
        "start": series[0]["equity"],
        "end": series[-1]["equity"],
        "return_pct": round((series[-1]["equity"] / series[0]["equity"] - 1) * 100, 2),
    }
    create_document("job", Job(kind="backtest", status="completed", payload=req.model_dump()).model_dump())
    return {"series": series, "stats": stats}


# -------- YouTube Automation (mocked) --------

class ScriptRequest(BaseModel):
    topic: str
    style: str = "educational"
    duration_min: int = 3


@app.post("/api/youtube/script", response_model=Dict[str, Any])
def generate_script(req: ScriptRequest):
    # Deterministic template script for demo; in production, integrate LLM/TTS services.
    outline = [
        "Hook: surprising fact about {}".format(req.topic),
        "What you'll learn in {} minutes".format(req.duration_min),
        "Three key ideas",
        "Quick demo",
        "Call to action",
    ]
    paragraphs = [
        f"Welcome! In this {req.style} video, we'll cover {req.topic} in just {req.duration_min} minutes.",
        f"First, let's ground the problem: why {req.topic} matters.",
        "Then we'll break it down into simple steps you can apply today.",
        "Stick around for a short demo and a quick recap!",
    ]
    content = "\n\n".join(paragraphs)
    vid = Video(title=f"{req.topic} in {req.duration_min} minutes", script=content, status="draft")
    video_id = create_document("video", vid)
    create_document("audit", Audit(action="script_generate", actor="system", details={"topic": req.topic}).model_dump())
    return {"id": video_id, "outline": outline, "script": content}


# -------- Settings --------

class SettingsUpdate(BaseModel):
    email: str
    settings: Dict[str, Any]


@app.post("/api/settings", response_model=Dict[str, Any])
def update_settings(req: SettingsUpdate):
    col = _collection("user")
    col.update_one({"email": req.email}, {"$set": {"settings": req.settings, "updated_at": _now()}}, upsert=True)
    create_document("audit", Audit(action="settings_update", actor=req.email, details={}).model_dump())
    doc = col.find_one({"email": req.email}, {"_id": 0})
    return {"user": doc}


# -------- Root & Test --------

@app.get("/")
def read_root():
    return {"message": "Autonomous Asset Platform Backend"}


@app.get("/test")
def test_database():
    response = {
        "backend": "ok",
        "database": "error",
        "env": {
            "DATABASE_URL": bool(os.getenv("DATABASE_URL")),
            "DATABASE_NAME": bool(os.getenv("DATABASE_NAME")),
        },
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "ok"
            response["collections"] = db.list_collection_names()
        else:
            response["database"] = "not_configured"
    except Exception as e:
        response["database"] = f"error: {str(e)[:80]}"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

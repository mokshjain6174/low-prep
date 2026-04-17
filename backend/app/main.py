from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


JWT_SECRET = os.getenv("JWT_SECRET", "low-prep-demo-secret")
TOKEN_TTL_SECONDS = 60 * 60 * 12

app = FastAPI(title="Low Prep API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    email: str
    password: str


class SessionRequest(BaseModel):
    topic: str
    goal: str
    preferred_time: str = "Today"


@dataclass
class User:
    id: str
    name: str
    email: str
    role: Literal["student", "tutor"]
    password: str


@dataclass
class Concept:
    id: str
    label: str
    x: float
    y: float
    owner: str


@dataclass
class Checkpoint:
    id: str
    text: str
    done: bool = False


@dataclass
class LoomState:
    notes: str = "Start by writing the simplest version of the idea. The tutor can turn it into concepts as the session grows."
    concepts: list[Concept] = field(default_factory=lambda: [
        Concept(id="c-foundation", label="Prior knowledge", x=18, y=28, owner="system"),
        Concept(id="c-target", label="Today's goal", x=62, y=34, owner="system"),
    ])
    links: list[dict[str, str]] = field(default_factory=lambda: [{"source": "c-foundation", "target": "c-target"}])
    clarity: dict[str, int] = field(default_factory=lambda: {"lost": 0, "steady": 0, "clear": 0})
    checkpoints: list[Checkpoint] = field(default_factory=lambda: [
        Checkpoint(id="cp-1", text="Explain the goal in your own words"),
        Checkpoint(id="cp-2", text="Solve one guided example"),
    ])


@dataclass
class TutoringSession:
    id: str
    student_id: str
    tutor_id: str | None
    topic: str
    goal: str
    preferred_time: str
    status: Literal["pending", "accepted"]
    created_at: float
    loom: LoomState = field(default_factory=LoomState)


USERS = {
    "student@lowprep.dev": User(
        id="u-student",
        name="Aarav Student",
        email="student@lowprep.dev",
        role="student",
        password="demo123",
    ),
    "tutor@lowprep.dev": User(
        id="u-tutor",
        name="Mira Tutor",
        email="tutor@lowprep.dev",
        role="tutor",
        password="demo123",
    ),
}

SESSIONS: dict[str, TutoringSession] = {}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def create_token(user: User) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": user.id, "email": user.email, "role": user.role, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    signing_input = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(payload).encode())}"
    signature = hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64(signature)}"


def verify_token(token: str) -> User:
    try:
        header_part, payload_part, signature_part = token.split(".")
        signing_input = f"{header_part}.{payload_part}"
        expected = _b64(hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature_part):
            raise ValueError("bad signature")
        payload = json.loads(_unb64(payload_part))
        if payload["exp"] < time.time():
            raise ValueError("expired")
        user = USERS.get(payload["email"])
        if not user:
            raise ValueError("unknown user")
        return user
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


def public_user(user: User) -> dict[str, str]:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}


def serialize_session(session: TutoringSession) -> dict[str, Any]:
    payload = asdict(session)
    payload["created_at"] = int(session.created_at)
    payload["student"] = public_user(next(user for user in USERS.values() if user.id == session.student_id))
    payload["tutor"] = public_user(next(user for user in USERS.values() if user.id == session.tutor_id)) if session.tutor_id else None
    return payload


def get_user_from_auth(authorization: str | None) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return verify_token(authorization.split(" ", 1)[1])


class ConnectionManager:
    def __init__(self) -> None:
        self.rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.rooms.setdefault(session_id, []).append(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        room = self.rooms.get(session_id, [])
        if websocket in room:
            room.remove(websocket)
        if not room and session_id in self.rooms:
            del self.rooms[session_id]

    async def broadcast(self, session_id: str, event: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for websocket in self.rooms.get(session_id, []):
            try:
                await websocket.send_json(event)
            except RuntimeError:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(session_id, websocket)


manager = ConnectionManager()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/login")
def login(payload: LoginRequest) -> dict[str, Any]:
    user = USERS.get(payload.email)
    if not user or user.password != payload.password:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return {"token": create_token(user), "user": public_user(user)}


@app.get("/me")
def me(authorization: str | None = Header(default=None)) -> dict[str, str]:
    return public_user(get_user_from_auth(authorization))


@app.get("/sessions")
def list_sessions(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
    user = get_user_from_auth(authorization)
    sessions = list(SESSIONS.values())
    if user.role == "student":
        sessions = [session for session in sessions if session.student_id == user.id]
    return [serialize_session(session) for session in sorted(sessions, key=lambda item: item.created_at, reverse=True)]


@app.post("/sessions/request")
def request_session(payload: SessionRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = get_user_from_auth(authorization)
    if user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can request sessions")
    session = TutoringSession(
        id=str(uuid.uuid4())[:8],
        student_id=user.id,
        tutor_id=None,
        topic=payload.topic,
        goal=payload.goal,
        preferred_time=payload.preferred_time,
        status="pending",
        created_at=time.time(),
    )
    SESSIONS[session.id] = session
    return serialize_session(session)


@app.post("/sessions/{session_id}/accept")
async def accept_session(session_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = get_user_from_auth(authorization)
    if user.role != "tutor":
        raise HTTPException(status_code=403, detail="Only tutors can accept sessions")
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.tutor_id = user.id
    session.status = "accepted"
    event = {"type": "session.accepted", "session": serialize_session(session), "server_ts": time.time()}
    await manager.broadcast(session.id, event)
    return serialize_session(session)


@app.get("/sessions/{session_id}")
def get_session(session_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    get_user_from_auth(authorization)
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return serialize_session(session)


def apply_loom_event(session: TutoringSession, event: dict[str, Any], user: User) -> dict[str, Any]:
    event_type = event.get("type")
    payload = event.get("payload", {})

    if event_type == "loom.notes.update":
        session.loom.notes = str(payload.get("notes", ""))[:5000]
    elif event_type == "loom.concept.add":
        label = str(payload.get("label", "New concept")).strip()[:48] or "New concept"
        session.loom.concepts.append(
            Concept(
                id=str(uuid.uuid4())[:8],
                label=label,
                x=float(payload.get("x", 50)),
                y=float(payload.get("y", 50)),
                owner=user.id,
            )
        )
    elif event_type == "loom.concept.link":
        source = str(payload.get("source", ""))
        target = str(payload.get("target", ""))
        known = {concept.id for concept in session.loom.concepts}
        if source in known and target in known and source != target:
            session.loom.links.append({"source": source, "target": target})
    elif event_type == "loom.clarity.vote":
        vote = str(payload.get("vote", "steady"))
        if vote in session.loom.clarity:
            session.loom.clarity[vote] += 1
    elif event_type == "loom.checkpoint.add":
        text = str(payload.get("text", "")).strip()[:140]
        if text:
            session.loom.checkpoints.append(Checkpoint(id=str(uuid.uuid4())[:8], text=text))
    elif event_type == "loom.checkpoint.toggle":
        checkpoint_id = str(payload.get("id", ""))
        for checkpoint in session.loom.checkpoints:
            if checkpoint.id == checkpoint_id:
                checkpoint.done = not checkpoint.done
                break

    return {
        "type": "loom.state",
        "session_id": session.id,
        "actor": public_user(user),
        "state": asdict(session.loom),
        "server_ts": time.time(),
    }


@app.websocket("/ws/sessions/{session_id}")
async def websocket_session(websocket: WebSocket, session_id: str, token: str) -> None:
    try:
        user = verify_token(token)
    except HTTPException:
        await websocket.close(code=4401)
        return

    session = SESSIONS.get(session_id)
    if not session:
        await websocket.close(code=4404)
        return

    await manager.connect(session_id, websocket)
    await websocket.send_json(
        {
            "type": "loom.state",
            "session_id": session.id,
            "actor": public_user(user),
            "state": asdict(session.loom),
            "server_ts": time.time(),
        }
    )
    await manager.broadcast(
        session_id,
        {"type": "presence.joined", "actor": public_user(user), "server_ts": time.time()},
    )

    try:
        while True:
            event = await websocket.receive_json()
            if event.get("type") == "ping":
                await websocket.send_json({"type": "pong", "server_ts": time.time()})
                continue
            normalized = apply_loom_event(session, event, user)
            await manager.broadcast(session_id, normalized)
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)
        await manager.broadcast(
            session_id,
            {"type": "presence.left", "actor": public_user(user), "server_ts": time.time()},
        )

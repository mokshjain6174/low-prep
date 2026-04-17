from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import select
import socket
import struct
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


JWT_SECRET = os.getenv("JWT_SECRET", "low-prep-demo-secret")
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


@dataclass
class User:
    id: str
    name: str
    email: str
    role: str
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
    status: str
    created_at: float
    loom: LoomState = field(default_factory=LoomState)


USERS = {
    "student@lowprep.dev": User("u-student", "Aarav Student", "student@lowprep.dev", "student", "demo123"),
    "tutor@lowprep.dev": User("u-tutor", "Mira Tutor", "tutor@lowprep.dev", "tutor", "demo123"),
}

SESSIONS: dict[str, TutoringSession] = {}
ROOMS: dict[str, list[socket.socket]] = {}
LOCK = threading.Lock()


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def public_user(user: User) -> dict[str, str]:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}


def create_token(user: User) -> str:
    header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64(json.dumps({"email": user.email, "role": user.role, "exp": int(time.time()) + 43200}).encode())
    signing_input = f"{header}.{payload}"
    signature = b64(hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest())
    return f"{signing_input}.{signature}"


def verify_token(token: str) -> User | None:
    try:
        header, payload, signature = token.split(".")
        signing_input = f"{header}.{payload}"
        expected = b64(hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest())
        data = json.loads(unb64(payload))
        if not hmac.compare_digest(signature, expected) or data["exp"] < time.time():
            return None
        return USERS.get(data["email"])
    except Exception:
        return None


def session_payload(session: TutoringSession) -> dict[str, Any]:
    data = asdict(session)
    data["created_at"] = int(session.created_at)
    data["student"] = public_user(next(user for user in USERS.values() if user.id == session.student_id))
    data["tutor"] = public_user(next(user for user in USERS.values() if user.id == session.tutor_id)) if session.tutor_id else None
    return data


def read_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if not length:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def send_ws(sock: socket.socket, payload: dict[str, Any]) -> None:
    data = json.dumps(payload).encode("utf-8")
    header = bytearray([0x81])
    if len(data) < 126:
        header.append(len(data))
    elif len(data) < 65536:
        header.append(126)
        header.extend(struct.pack("!H", len(data)))
    else:
        header.append(127)
        header.extend(struct.pack("!Q", len(data)))
    sock.sendall(header + data)


def recv_exact(sock: socket.socket, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("socket closed")
        data += chunk
    return data


def recv_ws(sock: socket.socket) -> dict[str, Any]:
    first, second = recv_exact(sock, 2)
    opcode = first & 0x0F
    if opcode == 0x8:
        raise ConnectionError("close frame")
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", recv_exact(sock, 8))[0]
    mask = recv_exact(sock, 4)
    raw = recv_exact(sock, length)
    decoded = bytes(byte ^ mask[index % 4] for index, byte in enumerate(raw))
    return json.loads(decoded.decode("utf-8"))


def broadcast(session_id: str, event: dict[str, Any]) -> None:
    with LOCK:
        sockets = list(ROOMS.get(session_id, []))
    stale: list[socket.socket] = []
    for sock in sockets:
        try:
            send_ws(sock, event)
        except OSError:
            stale.append(sock)
    if stale:
        with LOCK:
            for sock in stale:
                if sock in ROOMS.get(session_id, []):
                    ROOMS[session_id].remove(sock)


def apply_loom_event(session: TutoringSession, event: dict[str, Any], user: User) -> dict[str, Any]:
    event_type = event.get("type")
    payload = event.get("payload", {})
    with LOCK:
        if event_type == "loom.notes.update":
            session.loom.notes = str(payload.get("notes", ""))[:5000]
        elif event_type == "loom.concept.add":
            session.loom.concepts.append(
                Concept(
                    id=str(uuid.uuid4())[:8],
                    label=(str(payload.get("label", "New concept")).strip()[:48] or "New concept"),
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
        state = asdict(session.loom)
    return {"type": "loom.state", "session_id": session.id, "actor": public_user(user), "state": state, "server_ts": time.time()}


class Handler(BaseHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def json(self, status: int, payload: Any) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def user_from_header(self) -> User | None:
        auth = self.headers.get("Authorization", "")
        if not auth.lower().startswith("bearer "):
            return None
        return verify_token(auth.split(" ", 1)[1])

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self.json(200, {"status": "ok"})
            return
        if parsed.path == "/sessions":
            user = self.user_from_header()
            if not user:
                self.json(401, {"detail": "Missing bearer token"})
                return
            with LOCK:
                sessions = list(SESSIONS.values())
                if user.role == "student":
                    sessions = [session for session in sessions if session.student_id == user.id]
                payload = [session_payload(session) for session in sorted(sessions, key=lambda item: item.created_at, reverse=True)]
            self.json(200, payload)
            return
        self.json(404, {"detail": "Not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/auth/login":
            data = read_body(self)
            user = USERS.get(str(data.get("email", "")))
            if not user or user.password != data.get("password"):
                self.json(401, {"detail": "Incorrect email or password"})
                return
            self.json(200, {"token": create_token(user), "user": public_user(user)})
            return
        user = self.user_from_header()
        if not user:
            self.json(401, {"detail": "Missing bearer token"})
            return
        if parsed.path == "/sessions/request":
            data = read_body(self)
            if user.role != "student":
                self.json(403, {"detail": "Only students can request sessions"})
                return
            session = TutoringSession(
                id=str(uuid.uuid4())[:8],
                student_id=user.id,
                tutor_id=None,
                topic=str(data.get("topic", "Quick tutoring session")),
                goal=str(data.get("goal", "Understand the next step")),
                preferred_time=str(data.get("preferred_time", "Today")),
                status="pending",
                created_at=time.time(),
            )
            with LOCK:
                SESSIONS[session.id] = session
                payload = session_payload(session)
            self.json(200, payload)
            return
        if parsed.path.endswith("/accept") and parsed.path.startswith("/sessions/"):
            session_id = parsed.path.split("/")[2]
            with LOCK:
                session = SESSIONS.get(session_id)
                if session and user.role == "tutor":
                    session.tutor_id = user.id
                    session.status = "accepted"
                    payload = session_payload(session)
                else:
                    payload = None
            if user.role != "tutor":
                self.json(403, {"detail": "Only tutors can accept sessions"})
                return
            if not payload:
                self.json(404, {"detail": "Session not found"})
                return
            broadcast(session_id, {"type": "session.accepted", "session": payload, "server_ts": time.time()})
            self.json(200, payload)
            return
        self.json(404, {"detail": "Not found"})

    def do_CONNECT(self) -> None:
        self.json(405, {"detail": "Method not allowed"})

    def handle_one_request(self) -> None:
        super().handle_one_request()


class WebSocketServer(ThreadingHTTPServer):
    def finish_request(self, request: socket.socket, client_address: tuple[str, int]) -> None:
        request.settimeout(None)
        first = request.recv(65536, socket.MSG_PEEK)
        if b"Upgrade: websocket" not in first and b"upgrade: websocket" not in first:
            return super().finish_request(request, client_address)
        data = request.recv(65536).decode("utf-8", errors="replace")
        line, *headers = data.split("\r\n")
        path = line.split(" ")[1]
        parsed = urlparse(path)
        token = parse_qs(parsed.query).get("token", [""])[0]
        user = verify_token(token)
        session_id = parsed.path.removeprefix("/ws/sessions/")
        session = SESSIONS.get(session_id)
        key = ""
        for header in headers:
            if header.lower().startswith("sec-websocket-key:"):
                key = header.split(":", 1)[1].strip()
                break
        if not user or not session or not key:
            request.close()
            return
        accept = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
        )
        request.sendall(response.encode("ascii"))
        with LOCK:
            ROOMS.setdefault(session_id, []).append(request)
            state = asdict(session.loom)
        send_ws(request, {"type": "loom.state", "session_id": session.id, "actor": public_user(user), "state": state, "server_ts": time.time()})
        broadcast(session_id, {"type": "presence.joined", "actor": public_user(user), "server_ts": time.time()})
        try:
            while True:
                readable, _, _ = select.select([request], [], [], 60)
                if not readable:
                    send_ws(request, {"type": "pong", "server_ts": time.time()})
                    continue
                event = recv_ws(request)
                if event.get("type") == "ping":
                    send_ws(request, {"type": "pong", "server_ts": time.time()})
                else:
                    broadcast(session_id, apply_loom_event(session, event, user))
        except Exception:
            with LOCK:
                if request in ROOMS.get(session_id, []):
                    ROOMS[session_id].remove(request)
            broadcast(session_id, {"type": "presence.left", "actor": public_user(user), "server_ts": time.time()})
            request.close()


if __name__ == "__main__":
    print("Low Prep local backend running at http://localhost:8000")
    print("No pip install needed for this dev server.")
    WebSocketServer(("0.0.0.0", 8000), Handler).serve_forever()

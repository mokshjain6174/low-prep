# Aura EdTech

Aura EdTech is a dual-pane live tutoring platform built for the Athira problem statement. It keeps the familiar video-call experience, then adds a real-time learning workspace where concepts, clarity, notes, and checkpoints become visible during the session.

## Live Links

- Live demo: [https://low-prep.vercel.app](https://low-prep.vercel.app)
- Backup Vercel deployment: [https://low-prep-dipyk7n3r-moksh-jains-projects-71607069.vercel.app](https://low-prep-dipyk7n3r-moksh-jains-projects-71607069.vercel.app)
- Backend health check: [https://low-prep.onrender.com/health](https://low-prep.onrender.com/health)
- GitHub repository: [https://github.com/mokshjain6174/low-prep](https://github.com/mokshjain6174/low-prep)

If the Render backend is asleep, open the health check first and wait for `{"status":"ok"}` before using the app.

## Demo Accounts

The login buttons use these accounts automatically.

| Role | Email | Password |
| --- | --- | --- |
| Student | `student@lowprep.dev` | `demo123` |
| Tutor | `tutor@lowprep.dev` | `demo123` |

## Problem Focus

Generic video calls are not enough for live tutoring. A good tutoring session is structured, collaborative, and adaptive. Low Prep upgrades the live learning moment with a synchronized workspace called the **Concept Loom**.

The tutor and student can:

- talk through WebRTC video/audio
- write a shared explanation
- build a concept graph
- signal clarity without interrupting
- create and complete learning checkpoints

## Core Features

- One-click demo login for student and tutor
- Student dashboard for session requests
- Tutor dashboard for accepting requests
- Basic scheduling flow: request, accept, open room
- Dual-pane live session room
- Peer-to-peer WebRTC video/audio
- WebSocket-powered real-time collaboration
- Concept Loom innovation workspace
- Shared live explanation notes
- Visual concept graph
- Clarity pulse: `lost`, `steady`, `clear`
- Checkpoint cards for proof of learning
- WebSocket event schema documentation
- Architecture documentation for judging

## Tech Stack

### Frontend

- Vite
- React
- TypeScript
- CSS
- Browser WebRTC APIs
- Browser MediaDevices camera/microphone APIs
- Vercel deployment

### Backend

- FastAPI
- Python
- Uvicorn
- WebSockets
- HMAC-signed JWT-style bearer tokens
- In-memory prototype state
- Render deployment

### Real-Time Systems

- WebSocket session rooms
- Server-authoritative Concept Loom state
- WebRTC signaling through WebSockets
- Peer-to-peer media through `RTCPeerConnection`
- STUN server for basic NAT traversal

### Documentation

- README
- Architecture summary
- WebSocket event schema

## How It Works

1. A student joins and requests a session.
2. A tutor joins and accepts the pending request.
3. Both users open the live session room.
4. The WebSocket connection sends the current Concept Loom state to both users.
5. Each client sends intent events such as `loom.notes.update`, `loom.concept.add`, `loom.clarity.vote`, and `loom.checkpoint.toggle`.
6. The backend validates and broadcasts the normalized room state.
7. WebRTC offer, answer, and ICE candidate messages are forwarded through the same authenticated WebSocket room.
8. Video/audio media flows peer-to-peer between browsers.

## Innovation Pane: Concept Loom

The Concept Loom is the main product differentiator. It turns a tutoring call into a live learning map.

It includes:

- **Live Explanation:** a shared writing area for the current reasoning.
- **Concept Graph:** visual nodes showing key ideas and their relationships.
- **Clarity Pulse:** a lightweight way for the student to say whether they are lost, steady, or clear.
- **Checkpoints:** small proof-of-learning tasks that can be completed during the session.

Pedagogically, this supports:

- retrieval practice
- metacognition
- reduced cognitive load
- visible progress
- faster tutor adjustment when a student is confused

## Judge Demo Flow

1. Open https://low-prep.onrender.com/health to wake the backend.
2. Open https://low-prep.vercel.app.
3. Click **Join as student**.
4. Request a session.
5. Open an incognito/private window.
6. Open the same frontend URL.
7. Click **Join as tutor**.
8. Accept the session.
9. Open the room in both windows.
10. Allow camera and microphone permissions.
11. Demonstrate:
    - WebRTC video/audio
    - live note sync
    - concept graph updates
    - clarity pulse updates
    - checkpoint creation and completion

## Project Structure

```text
low-prep/
  backend/
    app/
      main.py
    dev_server.py
    requirements.txt
    Procfile
    runtime.txt
  docs/
    architecture.md
    websocket-events.md
  frontend/
    src/
      App.tsx
      main.tsx
      styles.css
    package.json
    vite.config.ts
  README.md
```

## Run Locally

### Backend Option 1: No-Install Windows Dev Server

Use this if `pip` gives Windows permission errors.

```bash
cd "E:\low prep\backend"
python dev_server.py
```

This no-install server uses Python standard library code and mirrors the same demo API/WebSocket behavior.

### Backend Option 2: FastAPI Backend

```bash
cd "E:\low prep\backend"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd "E:\low prep\frontend"
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

## Environment Variables

No paid API keys are required.

| Name | Where | Required | Purpose |
| --- | --- | --- | --- |
| `VITE_API_URL` | Frontend | Yes for deployment | Points React to the deployed backend |
| `JWT_SECRET` | Backend | Recommended | Signs login tokens |

Frontend deployment value:

```env
VITE_API_URL=https://low-prep.onrender.com
```

Backend deployment value example:

```env
JWT_SECRET=lowprep-moksh-2026-athira-demo-jwt-secret-9f4c2a7b8e1d
```

## Deployment

### Backend On Render

Settings:

```text
Root Directory: backend
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Environment variable:

```env
JWT_SECRET=your-long-secret
```

### Frontend On Vercel

Settings:

```text
Framework Preset: Vite
Root Directory: frontend
Build Command: npm run build
Output Directory: dist
Install Command: npm install
```

Environment variable:

```env
VITE_API_URL=https://low-prep.onrender.com
```

## Notes

- Render free instances can sleep after inactivity, so the first backend request may take extra time.
- WebRTC works best on HTTPS, which the deployed Vercel app provides.
- Some strict networks may require TURN credentials for reliable WebRTC traversal. The current prototype uses STUN and direct peer-to-peer media.
- The project uses in-memory state for demo speed. A production version should use a database such as Postgres.




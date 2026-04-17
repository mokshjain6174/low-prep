# Low Prep

Low Prep is a dual-pane tutoring prototype: a simple student/tutor scheduling flow plus a live session room that combines video with a collaborative learning workspace.

## What Is Built

- Vite + React frontend
- FastAPI backend
- Basic JWT-style login
- Student and tutor dashboards
- Student session requests and tutor acceptance
- Dual-pane session room
- Peer-to-peer WebRTC video/audio pane
- WebSocket-synchronized "Concept Loom" innovation pane
- Architecture and WebSocket event documentation for judges

## Demo Accounts

| Role | Email | Password |
| --- | --- | --- |
| Student | `student@lowprep.dev` | `demo123` |
| Tutor | `tutor@lowprep.dev` | `demo123` |

## Run Locally

Fastest local backend, if `pip` gives permission errors on Windows:

```bash
cd "E:\low prep\backend"
python dev_server.py
```

This no-install dev server uses the same API routes and WebSocket events as the FastAPI version, so the frontend works immediately.

FastAPI backend for deployment:

```bash
cd "E:\low prep\backend"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Start the frontend:

```bash
cd "E:\low prep\frontend"
npm install
npm run dev
```

Open `http://localhost:5173`.

If Python is not available on your PATH, install Python 3.11+ first. The frontend can still be reviewed as code, but the real-time session flow needs the FastAPI server.

## Judge Flow

1. Log in as `student@lowprep.dev`.
2. Request a session from the student dashboard.
3. In another browser, log in as `tutor@lowprep.dev`.
4. Accept the pending request.
5. Open the session room from both dashboards.
6. Edit the Concept Loom notes, add concepts, vote on clarity, and create checkpoint cards. The second browser updates instantly.

## Innovation Pane

The Concept Loom turns a tutoring call into a live learning map. Instead of losing useful explanations inside a video call, the room captures concepts, connections, confusion signals, and next-step checkpoints as durable synchronized artifacts.

Docs:

- [Architecture](docs/architecture.md)
- [WebSocket Events](docs/websocket-events.md)

## Deployment Notes

- Frontend: deploy `frontend` to Vercel.
- Backend: deploy `backend` to Render or Railway with `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Set `VITE_API_URL` on the frontend to the backend URL.
- Set `JWT_SECRET` on the backend for a non-demo deployment.

No paid API keys are required for the current prototype. The app uses its own FastAPI/WebSocket backend, browser camera/microphone APIs, and local demo users.

Environment variables:

| Name | Where | Required | Purpose |
| --- | --- | --- | --- |
| `VITE_API_URL` | Frontend | Yes for deployment | Points the React app to the backend URL |
| `JWT_SECRET` | Backend | Recommended | Secret used to sign login tokens |

# Low Prep Architecture

## Product Shape

Low Prep is built around a fast path into the moment that matters: a student asks for help, a tutor accepts, and both enter a dual-pane live room. The left pane is a peer-to-peer WebRTC video/audio call. The right pane is the Concept Loom, a shared learning workspace that turns the session into structured memory.

## Stack

- Frontend: Vite, React, TypeScript
- Backend: FastAPI
- Auth: simple HMAC-signed JWT-style bearer token
- Realtime: FastAPI WebSockets
- Video: browser WebRTC peer connection with WebSocket signaling
- Storage: in-memory prototype state for competition demo speed

## Synchronization Strategy

The backend is the source of truth for session state. When a participant joins `/ws/sessions/{session_id}`, the server authenticates the token, accepts the socket, sends the latest `loom.state`, and broadcasts presence. Clients do not directly mutate each other. They send intent events such as `loom.concept.add`, `loom.notes.update`, and `loom.clarity.vote`. The server validates the payload, applies the mutation to the session's `LoomState`, and broadcasts the normalized `loom.state` to everyone in the room.

This keeps the client simple and avoids split-brain state. If a browser misses an event, the next normalized state replaces its local copy. For a production version, the same event stream can be persisted to a database or replay log, while the client contract stays stable.

The same WebSocket room also forwards `webrtc.signal` events for peer negotiation. Browsers exchange WebRTC offer, answer, and ICE candidate payloads through the authenticated room, then media flows peer-to-peer through the browser WebRTC connection.

## Innovation Pane: Concept Loom

Most tutoring tools treat the video call as the product. Low Prep treats the video call as the conversation layer and gives the learning work its own live surface.

The Concept Loom captures four learning signals:

- Live explanation notes: the tutor and student co-write the current idea in plain language.
- Concept graph: important ideas become nodes, and tutors can link recent nodes to make prerequisite relationships visible.
- Clarity pulse: the student can signal "lost", "steady", or "clear" without interrupting the tutor.
- Checkpoints: the pair creates tiny proof-of-learning tasks and marks them complete during the session.

Pedagogically, this supports retrieval practice, metacognition, and reduced cognitive load. A learner who feels lost can signal it quickly; a tutor can adjust the graph and checkpoint sequence; both leave with a concrete map of what happened instead of a vague memory of a call.

## Production Path

- Replace in-memory stores with Postgres.
- Add refresh tokens and hashed passwords.
- Persist WebSocket events for replay and analytics.
- Add role-based session authorization checks.
- Add TURN credentials for stricter networks where direct peer-to-peer WebRTC cannot connect.

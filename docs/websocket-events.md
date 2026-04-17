# WebSocket Event Schema

Endpoint:

```text
GET /ws/sessions/{session_id}?token={jwt}
```

The server authenticates the token before accepting the socket. All events are JSON objects with a `type` field.

## Server Events

### `loom.state`

Sent on join and after every accepted workspace mutation.

```json
{
  "type": "loom.state",
  "session_id": "abc123",
  "actor": {
    "id": "u-tutor",
    "name": "Mira Tutor",
    "email": "tutor@lowprep.dev",
    "role": "tutor"
  },
  "state": {
    "notes": "Current explanation",
    "concepts": [{ "id": "c1", "label": "Equation", "x": 40, "y": 30, "owner": "u-tutor" }],
    "links": [{ "source": "c1", "target": "c2" }],
    "clarity": { "lost": 0, "steady": 1, "clear": 3 },
    "checkpoints": [{ "id": "cp1", "text": "Solve one example", "done": false }]
  },
  "server_ts": 1710000000.0
}
```

### `presence.joined`

Broadcast when a participant enters the room.

```json
{
  "type": "presence.joined",
  "actor": { "id": "u-student", "name": "Aarav Student", "email": "student@lowprep.dev", "role": "student" },
  "server_ts": 1710000000.0
}
```

### `presence.left`

Broadcast when a participant disconnects.

### `session.accepted`

Broadcast when a tutor accepts a pending request while a listener is already connected.

## Client Events

### `ping`

Health check. The server replies with `pong`.

```json
{ "type": "ping" }
```

### `loom.notes.update`

Replaces the shared explanation buffer.

```json
{
  "type": "loom.notes.update",
  "payload": { "notes": "We isolate x by undoing addition first." },
  "client_ts": 1710000000000
}
```

### `loom.concept.add`

Adds a concept node at a percentage position on the graph surface.

```json
{
  "type": "loom.concept.add",
  "payload": { "label": "Inverse operation", "x": 55, "y": 44 }
}
```

### `loom.concept.link`

Creates a directed relationship between two existing concept IDs.

```json
{
  "type": "loom.concept.link",
  "payload": { "source": "c1", "target": "c2" }
}
```

### `loom.clarity.vote`

Adds one live clarity signal.

```json
{
  "type": "loom.clarity.vote",
  "payload": { "vote": "steady" }
}
```

Allowed votes: `lost`, `steady`, `clear`.

### `loom.checkpoint.add`

Adds a proof-of-learning checkpoint.

```json
{
  "type": "loom.checkpoint.add",
  "payload": { "text": "Student solves a fresh problem aloud." }
}
```

### `loom.checkpoint.toggle`

Toggles completion for one checkpoint.

```json
{
  "type": "loom.checkpoint.toggle",
  "payload": { "id": "cp1" }
}
```

### `webrtc.signal`

Forwards WebRTC offer, answer, and ICE candidate messages between the student and tutor in the same authenticated room. The server does not inspect or store media. It only relays signaling payloads.

Description payload:

```json
{
  "type": "webrtc.signal",
  "payload": {
    "kind": "description",
    "description": { "type": "offer", "sdp": "..." }
  }
}
```

ICE candidate payload:

```json
{
  "type": "webrtc.signal",
  "payload": {
    "kind": "ice",
    "candidate": { "candidate": "...", "sdpMid": "0", "sdpMLineIndex": 0 }
  }
}
```

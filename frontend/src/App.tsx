import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type Role = "student" | "tutor";

type User = {
  id: string;
  name: string;
  email: string;
  role: Role;
};

type Concept = {
  id: string;
  label: string;
  x: number;
  y: number;
  owner: string;
};

type Checkpoint = {
  id: string;
  text: string;
  done: boolean;
};

type LoomState = {
  notes: string;
  concepts: Concept[];
  links: { source: string; target: string }[];
  clarity: Record<"lost" | "steady" | "clear", number>;
  checkpoints: Checkpoint[];
};

type TutoringSession = {
  id: string;
  student_id: string;
  tutor_id: string | null;
  topic: string;
  goal: string;
  preferred_time: string;
  status: "pending" | "accepted";
  student: User;
  tutor: User | null;
  loom: LoomState;
};

const demoLogins = {
  student: { email: "student@lowprep.dev", password: "demo123" },
  tutor: { email: "tutor@lowprep.dev", password: "demo123" }
};

function wsUrl(sessionId: string, token: string) {
  const base = API_URL.replace(/^http/, "ws");
  return `${base}/ws/sessions/${sessionId}?token=${encodeURIComponent(token)}`;
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem("lowprep.token") ?? "");
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem("lowprep.user");
    return saved ? JSON.parse(saved) : null;
  });
  const [sessions, setSessions] = useState<TutoringSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers ?? {})
      }
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(detail.detail ?? "Request failed");
    }
    return response.json();
  }

  async function refreshSessions() {
    if (!token) return;
    const data = await api<TutoringSession[]>("/sessions");
    setSessions(data);
  }

  async function handleLogin(role: Role) {
    setError("");
    try {
      const response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(demoLogins[role])
      });
      if (!response.ok) throw new Error("Login failed. Is the backend running?");
      const data = (await response.json()) as { token: string; user: User };
      localStorage.setItem("lowprep.token", data.token);
      localStorage.setItem("lowprep.user", JSON.stringify(data.user));
      setToken(data.token);
      setUser(data.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  }

  function logout() {
    localStorage.removeItem("lowprep.token");
    localStorage.removeItem("lowprep.user");
    setToken("");
    setUser(null);
    setSessions([]);
    setActiveSessionId(null);
  }

  useEffect(() => {
    refreshSessions().catch((err) => setError(err.message));
  }, [token]);

  const activeSession = sessions.find((session) => session.id === activeSessionId) ?? null;

  if (!user || !token) {
    return <LoginScreen error={error} onLogin={handleLogin} />;
  }

  return (
    <main>
      <TopBar user={user} onLogout={logout} />
      {activeSession ? (
        <SessionRoom
          token={token}
          session={activeSession}
          user={user}
          onBack={() => {
            setActiveSessionId(null);
            refreshSessions().catch((err) => setError(err.message));
          }}
        />
      ) : (
        <Dashboard
          user={user}
          sessions={sessions}
          error={error}
          refresh={refreshSessions}
          requestSession={async (payload) => {
            const session = await api<TutoringSession>("/sessions/request", {
              method: "POST",
              body: JSON.stringify(payload)
            });
            setSessions((current) => [session, ...current]);
          }}
          acceptSession={async (id) => {
            const session = await api<TutoringSession>(`/sessions/${id}/accept`, { method: "POST" });
            setSessions((current) => current.map((item) => (item.id === id ? session : item)));
          }}
          openSession={setActiveSessionId}
        />
      )}
    </main>
  );
}

function LoginScreen({ error, onLogin }: { error: string; onLogin: (role: Role) => void }) {
  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <div>
          <p className="eyebrow">Low Prep Live Tutoring</p>
          <h1>Turn a tutoring call into a shared learning map.</h1>
          <p className="lede">
            Join as a student or tutor, request a session, then build concepts and checkpoints together in real time.
          </p>
        </div>
        <div className="login-actions">
          <button onClick={() => onLogin("student")}>Join as student</button>
          <button className="secondary" onClick={() => onLogin("tutor")}>
            Join as tutor
          </button>
        </div>
        {error && <p className="error">{error}</p>}
      </section>
      <img
        className="auth-image"
        src="https://images.unsplash.com/photo-1522202176988-66273c2fd55f?auto=format&fit=crop&w=1100&q=80"
        alt="Students working together around a laptop"
      />
    </main>
  );
}

function TopBar({ user, onLogout }: { user: User; onLogout: () => void }) {
  return (
    <header className="topbar">
      <div>
        <strong>Low Prep</strong>
        <span>{user.role} dashboard</span>
      </div>
      <div className="topbar-user">
        <span>{user.name}</span>
        <button className="ghost" onClick={onLogout}>
          Log out
        </button>
      </div>
    </header>
  );
}

function Dashboard({
  user,
  sessions,
  error,
  refresh,
  requestSession,
  acceptSession,
  openSession
}: {
  user: User;
  sessions: TutoringSession[];
  error: string;
  refresh: () => Promise<void>;
  requestSession: (payload: { topic: string; goal: string; preferred_time: string }) => Promise<void>;
  acceptSession: (id: string) => Promise<void>;
  openSession: (id: string) => void;
}) {
  return (
    <section className="dashboard">
      <div className="dashboard-intro">
        <div>
          <p className="eyebrow">Ready room</p>
          <h1>{user.role === "student" ? "Request focused help fast." : "Pick up the next learner."}</h1>
        </div>
        <button className="secondary" onClick={() => refresh()}>
          Refresh
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {user.role === "student" && <RequestForm onSubmit={requestSession} />}
      <div className="session-grid">
        {sessions.length === 0 && (
          <article className="empty-state">
            <h2>No sessions yet</h2>
            <p>{user.role === "student" ? "Request one to start the flow." : "Wait for a student request, then refresh."}</p>
          </article>
        )}
        {sessions.map((session) => (
          <article className="session-card" key={session.id}>
            <div>
              <p className={`status ${session.status}`}>{session.status}</p>
              <h2>{session.topic}</h2>
              <p>{session.goal}</p>
              <small>Preferred: {session.preferred_time}</small>
            </div>
            <div className="card-actions">
              {user.role === "tutor" && session.status === "pending" && (
                <button onClick={() => acceptSession(session.id)}>Accept</button>
              )}
              {session.status === "accepted" && <button onClick={() => openSession(session.id)}>Open room</button>}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function RequestForm({
  onSubmit
}: {
  onSubmit: (payload: { topic: string; goal: string; preferred_time: string }) => Promise<void>;
}) {
  const [topic, setTopic] = useState("Algebra word problems");
  const [goal, setGoal] = useState("Translate a word problem into an equation without freezing.");
  const [preferredTime, setPreferredTime] = useState("Today after class");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    await onSubmit({ topic, goal, preferred_time: preferredTime });
    setBusy(false);
  }

  return (
    <form className="request-form" onSubmit={submit}>
      <label>
        Topic
        <input value={topic} onChange={(event) => setTopic(event.target.value)} />
      </label>
      <label>
        Goal
        <input value={goal} onChange={(event) => setGoal(event.target.value)} />
      </label>
      <label>
        Preferred time
        <input value={preferredTime} onChange={(event) => setPreferredTime(event.target.value)} />
      </label>
      <button disabled={busy}>{busy ? "Sending..." : "Request session"}</button>
    </form>
  );
}

function SessionRoom({
  token,
  session,
  user,
  onBack
}: {
  token: string;
  session: TutoringSession;
  user: User;
  onBack: () => void;
}) {
  const [loom, setLoom] = useState<LoomState>(session.loom);
  const [connection, setConnection] = useState("connecting");
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const socket = new WebSocket(wsUrl(session.id, token));
    socketRef.current = socket;
    socket.onopen = () => setConnection("live");
    socket.onclose = () => setConnection("offline");
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data);
      if (event.type === "loom.state") setLoom(event.state);
    };
    return () => socket.close();
  }, [session.id, token]);

  function send(type: string, payload: Record<string, unknown>) {
    socketRef.current?.send(JSON.stringify({ type, payload, client_ts: Date.now() }));
  }

  return (
    <section className="room">
      <div className="room-header">
        <button className="ghost" onClick={onBack}>
          Back
        </button>
        <div>
          <p className="eyebrow">{session.topic}</p>
          <h1>{session.goal}</h1>
        </div>
        <span className={`connection ${connection}`}>{connection}</span>
      </div>
      <div className="dual-pane">
        <section className="video-pane">
          <LocalVideoPane sessionId={session.id} />
        </section>
        <ConceptLoom loom={loom} user={user} setLoom={setLoom} send={send} />
      </div>
    </section>
  );
}

function LocalVideoPane({ sessionId }: { sessionId: string }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [cameraState, setCameraState] = useState("camera off");
  const [muted, setMuted] = useState(false);

  useEffect(() => {
    let stream: MediaStream | null = null;

    async function startCamera() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
        setCameraState("camera live");
      } catch {
        setCameraState("camera blocked");
      }
    }

    startCamera();

    return () => {
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  function toggleMic() {
    const stream = videoRef.current?.srcObject as MediaStream | null;
    stream?.getAudioTracks().forEach((track) => {
      track.enabled = muted;
    });
    setMuted((value) => !value);
  }

  return (
    <div className="local-call">
      <video ref={videoRef} autoPlay playsInline muted />
      <div className="remote-tile">
        <span>tutor/student peer</span>
        <strong>Low Prep Room {sessionId}</strong>
      </div>
      <div className="call-controls">
        <span>{cameraState}</span>
        <button className="secondary" onClick={toggleMic}>
          {muted ? "Unmute mic" : "Mute mic"}
        </button>
      </div>
    </div>
  );
}

function ConceptLoom({
  loom,
  user,
  setLoom,
  send
}: {
  loom: LoomState;
  user: User;
  setLoom: (state: LoomState) => void;
  send: (type: string, payload: Record<string, unknown>) => void;
}) {
  const [conceptLabel, setConceptLabel] = useState("");
  const [checkpoint, setCheckpoint] = useState("");
  const totalVotes = useMemo(
    () => Object.values(loom.clarity).reduce((sum, value) => sum + value, 0),
    [loom.clarity]
  );

  function addConcept() {
    if (!conceptLabel.trim()) return;
    send("loom.concept.add", {
      label: conceptLabel,
      x: 15 + Math.random() * 70,
      y: 18 + Math.random() * 64
    });
    setConceptLabel("");
  }

  function linkRecent() {
    const [source, target] = loom.concepts.slice(-2);
    if (source && target) send("loom.concept.link", { source: source.id, target: target.id });
  }

  return (
    <section className="loom-pane">
      <div className="loom-top">
        <div>
          <p className="eyebrow">Concept Loom</p>
          <h2>Shared memory for this lesson</h2>
        </div>
        <span>{user.name}</span>
      </div>
      <label className="notes">
        Live explanation
        <textarea
          value={loom.notes}
          onChange={(event) => {
            const next = { ...loom, notes: event.target.value };
            setLoom(next);
            send("loom.notes.update", { notes: next.notes });
          }}
        />
      </label>
      <div className="loom-grid">
        <div className="graph-surface">
          {loom.links.map((link, index) => {
            const source = loom.concepts.find((concept) => concept.id === link.source);
            const target = loom.concepts.find((concept) => concept.id === link.target);
            if (!source || !target) return null;
            return (
              <svg className="graph-link" key={`${link.source}-${link.target}-${index}`}>
                <line x1={`${source.x}%`} y1={`${source.y}%`} x2={`${target.x}%`} y2={`${target.y}%`} />
              </svg>
            );
          })}
          {loom.concepts.map((concept) => (
            <button
              className="concept-node"
              key={concept.id}
              style={{ left: `${concept.x}%`, top: `${concept.y}%` }}
              title={concept.owner}
            >
              {concept.label}
            </button>
          ))}
        </div>
        <div className="side-tools">
          <div className="inline-form">
            <input
              value={conceptLabel}
              onChange={(event) => setConceptLabel(event.target.value)}
              placeholder="New concept"
            />
            <button onClick={addConcept}>Add</button>
          </div>
          <button className="secondary stretch" onClick={linkRecent}>
            Link last two concepts
          </button>
          <div className="pulse">
            <p>Clarity pulse</p>
            {(["lost", "steady", "clear"] as const).map((vote) => (
              <button key={vote} onClick={() => send("loom.clarity.vote", { vote })}>
                {vote} <strong>{loom.clarity[vote]}</strong>
              </button>
            ))}
            <small>{totalVotes} live signals</small>
          </div>
        </div>
      </div>
      <div className="checkpoint-row">
        <div className="inline-form">
          <input value={checkpoint} onChange={(event) => setCheckpoint(event.target.value)} placeholder="Next checkpoint" />
          <button
            onClick={() => {
              send("loom.checkpoint.add", { text: checkpoint });
              setCheckpoint("");
            }}
          >
            Add
          </button>
        </div>
        <div className="checkpoints">
          {loom.checkpoints.map((item) => (
            <button
              className={item.done ? "checkpoint done" : "checkpoint"}
              key={item.id}
              onClick={() => send("loom.checkpoint.toggle", { id: item.id })}
            >
              {item.text}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

export default App;

import { useEffect, useState, type FormEvent } from "react";
import { api, type Session } from "./api";
import { Photographs } from "./components/Photographs";
import { PhotoPaths } from "./components/PhotoPaths";
import { Album } from "./components/Album";
import { OrganizerJobs } from "./components/OrganizerJobs";
import "./App.css";

type View = "photographs" | "paths" | "album" | "organizer";

function App() {
  const [currentView, setCurrentView] = useState<View>("photographs");
  const [session, setSession] = useState<Session | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getSession()
      .then(setSession)
      .catch(() =>
        setSession({ authenticated: false, username: null, operator: false })
      );
  }, []);

  const handleLogin = async (event: FormEvent) => {
    event.preventDefault();
    try {
      setSession(await api.login(username, password));
      setPassword("");
      setAuthError(null);
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Login failed");
    }
  };

  const handleLogout = async () => {
    setSession(await api.logout());
    setCurrentView("photographs");
  };

  if (session === null) {
    return <div className="app-main">Loading session...</div>;
  }

  if (!session.authenticated) {
    return (
      <main className="app-main">
        <form onSubmit={handleLogin}>
          <h1>PhotoChart</h1>
          <label>
            Username
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          <button type="submit">Sign in</button>
          {authError && <div className="error">{authError}</div>}
        </form>
      </main>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>PhotoChart</h1>
        <div>
          <span>{session.username}</span>{" "}
          <button onClick={handleLogout}>Sign out</button>
        </div>
        <nav className="app-nav">
          <button
            className={currentView === "photographs" ? "active" : ""}
            onClick={() => setCurrentView("photographs")}
          >
            Photographs
          </button>
          <button
            className={currentView === "paths" ? "active" : ""}
            onClick={() => setCurrentView("paths")}
          >
            Photo Paths
          </button>
          <button
            className={currentView === "album" ? "active" : ""}
            onClick={() => setCurrentView("album")}
          >
            Album
          </button>
          <button
            className={currentView === "organizer" ? "active" : ""}
            onClick={() => setCurrentView("organizer")}
          >
            Organizer
          </button>
        </nav>
      </header>
      <main className="app-main">
        {currentView === "photographs" && <Photographs />}
        {currentView === "paths" && <PhotoPaths />}
        {currentView === "album" && <Album />}
        {currentView === "organizer" && <OrganizerJobs />}
      </main>
    </div>
  );
}

export default App;

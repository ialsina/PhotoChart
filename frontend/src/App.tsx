import { useState } from "react";
import { Photographs } from "./components/Photographs";
import { PhotoPaths } from "./components/PhotoPaths";
import { Album } from "./components/Album";
import "./App.css";

type View = "photographs" | "paths" | "album";

function App() {
  const [currentView, setCurrentView] = useState<View>("photographs");

  return (
    <div className="app">
      <header className="app-header">
        <h1>PhotoChart</h1>
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
        </nav>
      </header>
      <main className="app-main">
        {currentView === "photographs" && <Photographs />}
        {currentView === "paths" && <PhotoPaths />}
        {currentView === "album" && <Album />}
      </main>
    </div>
  );
}

export default App;

import { useState } from "react";
import { Photographs } from "./components/Photographs";
import { PhotoPaths } from "./components/PhotoPaths";
import { Catalog } from "./components/Catalog";
import "./App.css";

type View = "photographs" | "paths" | "catalog";

function App() {
  const [currentView, setCurrentView] = useState<View>("photographs");

  return (
    <div className="app">
      <header className="app-header">
        <h1>PhotoFinder</h1>
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
            className={currentView === "catalog" ? "active" : ""}
            onClick={() => setCurrentView("catalog")}
          >
            Catalog
          </button>
        </nav>
      </header>
      <main className="app-main">
        {currentView === "photographs" && <Photographs />}
        {currentView === "paths" && <PhotoPaths />}
        {currentView === "catalog" && <Catalog />}
      </main>
    </div>
  );
}

export default App;

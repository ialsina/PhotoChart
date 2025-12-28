import { useState, useEffect } from "react";
import { api } from "../api";
import type { Hash, Directory, DirKind, Location, TimeLoc } from "../types";

type Tab = "hashes" | "directories" | "locations" | "timelocs";

export function Catalog() {
  const [activeTab, setActiveTab] = useState<Tab>("hashes");
  const [hashes, setHashes] = useState<Hash[]>([]);
  const [directories, setDirectories] = useState<Directory[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [timeLocs, setTimeLocs] = useState<TimeLoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      switch (activeTab) {
        case "hashes":
          const hashResponse = await api.getHashes();
          setHashes(hashResponse.results);
          break;
        case "directories":
          const dirResponse = await api.getDirectories();
          setDirectories(dirResponse.results);
          break;
        case "locations":
          const locResponse = await api.getLocations();
          setLocations(locResponse.results);
          break;
        case "timelocs":
          const tlResponse = await api.getTimeLocs();
          setTimeLocs(tlResponse.results);
          break;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="catalog">
      <h2>Catalog</h2>
      <div className="tabs">
        <button
          className={activeTab === "hashes" ? "active" : ""}
          onClick={() => setActiveTab("hashes")}
        >
          Hashes ({hashes.length})
        </button>
        <button
          className={activeTab === "directories" ? "active" : ""}
          onClick={() => setActiveTab("directories")}
        >
          Directories ({directories.length})
        </button>
        <button
          className={activeTab === "locations" ? "active" : ""}
          onClick={() => setActiveTab("locations")}
        >
          Locations ({locations.length})
        </button>
        <button
          className={activeTab === "timelocs" ? "active" : ""}
          onClick={() => setActiveTab("timelocs")}
        >
          Time Locations ({timeLocs.length})
        </button>
      </div>

      {loading ? (
        <div className="loading">Loading...</div>
      ) : error ? (
        <div className="error">Error: {error}</div>
      ) : (
        <div className="tab-content">
          {activeTab === "hashes" && (
            <div className="hashes-list">
              {hashes.length === 0 ? (
                <p className="empty-state">No hashes found.</p>
              ) : (
                hashes.map((hash) => (
                  <div key={hash.id} className="hash-card">
                    <div className="hash-value">
                      <code>{hash.hash}</code>
                    </div>
                    <div className="hash-path">{hash.path}</div>
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === "directories" && (
            <div className="directories-list">
              {directories.length === 0 ? (
                <p className="empty-state">No directories found.</p>
              ) : (
                directories.map((dir) => (
                  <div key={dir.id} className="directory-card">
                    <div className="directory-header">
                      <span className="directory-path">{dir.path}</span>
                      <span className="directory-kind">{dir.kind_name}</span>
                    </div>
                    <div className="directory-footer">
                      <span>Last modified: {new Date(dir.last_modified).toLocaleString()}</span>
                      <span>Mirror: {dir.mirror}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === "locations" && (
            <div className="locations-list">
              {locations.length === 0 ? (
                <p className="empty-state">No locations found.</p>
              ) : (
                locations.map((loc) => (
                  <div key={loc.id} className="location-card">
                    {loc.name}
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === "timelocs" && (
            <div className="timelocs-list">
              {timeLocs.length === 0 ? (
                <p className="empty-state">No time locations found.</p>
              ) : (
                timeLocs.map((tl) => (
                  <div key={tl.id} className="timeloc-card">
                    <div className="timeloc-header">
                      <span className="timeloc-directory">{tl.directory_path}</span>
                      <span className="timeloc-location">{tl.location_name}</span>
                    </div>
                    <div className="timeloc-timestamp">
                      {new Date(tl.timestamp).toLocaleString()}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

import { useState, useEffect } from "react";
import { api } from "../api";
import type { PhotoPath } from "../types";

export function PhotoPaths() {
  const [paths, setPaths] = useState<PhotoPath[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadPaths();
  }, []);

  const loadPaths = async () => {
    try {
      setLoading(true);
      const response = await api.getPhotoPaths();
      setPaths(response.results);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load photo paths");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading photo paths...</div>;
  }

  if (error) {
    return <div className="error">Error: {error}</div>;
  }

  return (
    <div className="photo-paths">
      <h2>Photo Paths ({paths.length})</h2>
      {paths.length === 0 ? (
        <p className="empty-state">No photo paths found.</p>
      ) : (
        <div className="paths-list">
          {paths.map((path) => (
            <div key={path.id} className="path-card">
              <div className="path-header">
                <span className="path-id">ID: {path.id}</span>
                <span className="path-device">
                  <span className="field-label">Device:</span> {path.device}
                </span>
              </div>
              <div className="path-value">
                <span className="field-label">Path:</span> {path.path}
              </div>
              <div className="path-photograph-link">
                {path.photograph ? (
                  <span className="path-photograph">
                    <span className="field-label">Linked to Photograph:</span> #{path.photograph}
                  </span>
                ) : (
                  <span className="path-no-photograph">
                    <span className="field-label">Photograph:</span> No photograph linked
                  </span>
                )}
              </div>
              <div className="path-footer">
                <div className="path-date">
                  <span className="field-label">Created:</span>{" "}
                  {new Date(path.created_at).toLocaleString()}
                </div>
                <div className="path-date">
                  <span className="field-label">Updated:</span>{" "}
                  {new Date(path.updated_at).toLocaleString()}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

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
                <span className="path-id">#{path.id}</span>
                <span className="path-device">{path.device}</span>
              </div>
              <div className="path-value">{path.path}</div>
              <div className="path-footer">
                {path.photograph ? (
                  <span className="path-photograph">
                    Linked to photograph #{path.photograph}
                  </span>
                ) : (
                  <span className="path-no-photograph">No photograph linked</span>
                )}
                <span className="path-date">
                  {new Date(path.created_at).toLocaleString()}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

import { useState, useEffect } from "react";
import { api } from "../api";
import type { Photograph } from "../types";

export function Photographs() {
  const [photographs, setPhotographs] = useState<Photograph[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadPhotographs();
  }, []);

  const loadPhotographs = async () => {
    try {
      setLoading(true);
      const response = await api.getPhotographs();
      setPhotographs(response.results);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load photographs");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading photographs...</div>;
  }

  if (error) {
    return <div className="error">Error: {error}</div>;
  }

  return (
    <div className="photographs">
      <h2>Photographs ({photographs.length})</h2>
      {photographs.length === 0 ? (
        <p className="empty-state">No photographs found.</p>
      ) : (
        <div className="photographs-grid">
          {photographs.map((photo) => (
            <div key={photo.id} className="photograph-card">
              {photo.image_url ? (
                <img
                  src={photo.image_url}
                  alt={photo.hash || `Photo ${photo.id}`}
                  className="photograph-image"
                />
              ) : (
                <div className="photograph-placeholder">
                  No Image
                </div>
              )}
              <div className="photograph-info">
                <div className="photograph-hash">
                  {photo.hash ? (
                    <code>{photo.hash.substring(0, 16)}...</code>
                  ) : (
                    <span className="no-hash">No hash</span>
                  )}
                </div>
                <div className="photograph-paths">
                  {photo.paths.length > 0 ? (
                    <span className="paths-count">
                      {photo.paths.length} path{photo.paths.length !== 1 ? "s" : ""}
                    </span>
                  ) : (
                    <span className="no-paths">No paths</span>
                  )}
                </div>
                <div className="photograph-date">
                  Created: {new Date(photo.created_at).toLocaleDateString()}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

import { useState, useEffect } from "react";
import { api } from "../api";
import type { Photograph } from "../types";

type SortMode = "id" | "date";

export function Photographs() {
  const [photographs, setPhotographs] = useState<Photograph[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>("id");
  const [ascending, setAscending] = useState<boolean>(true);

  useEffect(() => {
    loadPhotographs();
  }, []);

  const loadPhotographs = async () => {
    try {
      setLoading(true);
      const response = await api.getPhotographs();
      setPhotographs(response.results);
      // Debug: log first photo to check time field
      if (response.results.length > 0) {
        console.log("Sample photo data:", response.results[0]);
        console.log("Time field value:", response.results[0].time);
        console.log("Time field type:", typeof response.results[0].time);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load photographs");
    } finally {
      setLoading(false);
    }
  };

  const toggleSort = () => {
    setSortMode((prev) => (prev === "id" ? "date" : "id"));
  };

  const toggleOrder = () => {
    setAscending((prev) => !prev);
  };

  const sortedPhotographs = [...photographs].sort((a, b) => {
    let comparison = 0;
    if (sortMode === "id") {
      comparison = a.id - b.id;
    } else {
      // Sort by date - use photo time if available, otherwise use created_at
      const dateA = a.time ? new Date(a.time).getTime() : new Date(a.created_at).getTime();
      const dateB = b.time ? new Date(b.time).getTime() : new Date(b.created_at).getTime();
      comparison = dateA - dateB;
    }
    return ascending ? comparison : -comparison;
  });

  const formatTime = (timeValue: string | null | undefined): string | null => {
    // Check if timeValue exists and is not empty
    if (timeValue === null || timeValue === undefined || timeValue === "") {
      return null;
    }
    // Try to parse as date
    try {
      const date = new Date(timeValue);
      // Check if date is valid
      if (isNaN(date.getTime())) {
        // If not a valid date, return the raw value so user can see it
        return timeValue;
      }
      return date.toLocaleString();
    } catch (e) {
      // If parsing fails, return raw value
      return timeValue;
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
      <div className="photographs-header">
        <h2>Photographs ({photographs.length})</h2>
        <div className="sort-controls">
          <button className="sort-toggle" onClick={toggleSort}>
            Sort by: {sortMode === "id" ? "ID" : "Date"}
          </button>
          <button className="sort-order" onClick={toggleOrder} title={ascending ? "Ascending" : "Descending"}>
            {ascending ? "▲" : "▼"}
          </button>
        </div>
      </div>
      {photographs.length === 0 ? (
        <p className="empty-state">No photographs found.</p>
      ) : (
        <div className="photographs-grid">
          {sortedPhotographs.map((photo) => (
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
                <div className="photograph-id">ID: {photo.id}</div>
                {(() => {
                  // Check if time exists - be very permissive
                  if (photo.time != null && photo.time !== "") {
                    const formattedTime = formatTime(photo.time);
                    if (formattedTime) {
                      return (
                        <div className="photograph-time">
                          <span className="field-label">Photo Time:</span>{" "}
                          <span className="time-value">{formattedTime}</span>
                        </div>
                      );
                    }
                  }
                  return (
                    <div className="photograph-time no-time">
                      <span className="field-label">Photo Time:</span>{" "}
                      <span className="no-time-value">Not available</span>
                    </div>
                  );
                })()}
                <div className="photograph-hash">
                  {photo.hash ? (
                    <div>
                      <span className="field-label">Hash:</span>{" "}
                      <code>{photo.hash.substring(0, 16)}...</code>
                    </div>
                  ) : (
                    <div>
                      <span className="field-label">Hash:</span>{" "}
                      <span className="no-hash">No hash</span>
                    </div>
                  )}
                </div>
                <div className="photograph-paths">
                  <span className="field-label">Paths:</span>{" "}
                  {photo.paths.length > 0 ? (
                    <span className="paths-count">
                      {photo.paths.length} path{photo.paths.length !== 1 ? "s" : ""}
                    </span>
                  ) : (
                    <span className="no-paths">No paths</span>
                  )}
                </div>
                <div className="photograph-dates">
                  <div className="photograph-date">
                    <span className="field-label">Created:</span>{" "}
                    {new Date(photo.created_at).toLocaleString()}
                  </div>
                  <div className="photograph-date">
                    <span className="field-label">Updated:</span>{" "}
                    {new Date(photo.updated_at).toLocaleString()}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

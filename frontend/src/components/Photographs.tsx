import { useState, useEffect, useMemo } from "react";
import { api } from "../api";
import type { Photograph } from "../types";

type SortMode = "id" | "date";
type NavigationPath = {
  type: "year" | "month" | "day";
  value: string;
  label: string;
};

export function Photographs() {
  const [photographs, setPhotographs] = useState<Photograph[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>("id");
  const [ascending, setAscending] = useState<boolean>(true);
  const [navigationPath, setNavigationPath] = useState<NavigationPath[]>([]);

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

  const toggleSort = () => {
    setSortMode((prev) => (prev === "id" ? "date" : "id"));
  };

  const toggleOrder = () => {
    setAscending((prev) => !prev);
  };

  // Build hierarchical structure: Year > Month > Day, with "Unknown" for photos without time
  const hierarchy = useMemo(() => {
    const structure: Record<string, Record<string, Record<string, Photograph[]>>> = {};
    const unknownPhotos: Photograph[] = [];

    photographs.forEach((photo) => {
      // Check if photo has a valid time
      if (!photo.time || photo.time === null || photo.time === "") {
        unknownPhotos.push(photo);
        return;
      }

      const date = new Date(photo.time);
      if (isNaN(date.getTime())) {
        unknownPhotos.push(photo);
        return;
      }

      const year = date.getFullYear().toString();
      const month = (date.getMonth() + 1).toString().padStart(2, "0");
      const day = date.getDate().toString().padStart(2, "0");

      if (!structure[year]) structure[year] = {};
      if (!structure[year][month]) structure[year][month] = {};
      if (!structure[year][month][day]) structure[year][month][day] = [];

      structure[year][month][day].push(photo);
    });

    // Add "Unknown" category if there are photos without time
    if (unknownPhotos.length > 0) {
      structure["Unknown"] = {
        "": {
          "": unknownPhotos
        }
      };
    }

    return structure;
  }, [photographs]);

  // Get current view based on navigation path
  const currentView = useMemo(() => {
    if (navigationPath.length === 0) {
      // Show years (including "Unknown")
      const years = Object.keys(hierarchy).filter(key => key !== "Unknown");
      const sortedYears = years.sort((a, b) => {
        if (a === "Unknown" || b === "Unknown") return 0;
        return parseInt(b) - parseInt(a);
      });
      // Add "Unknown" at the end
      if (hierarchy["Unknown"]) {
        sortedYears.push("Unknown");
      }
      return {
        type: "years" as const,
        items: sortedYears,
      };
    } else if (navigationPath.length === 1) {
      // Show months for selected year, or go directly to photos if "Unknown"
      const year = navigationPath[0].value;
      if (year === "Unknown") {
        return {
          type: "photographs" as const,
          items: hierarchy["Unknown"]?.[""]?.[""] || [],
        };
      }
      return {
        type: "months" as const,
        items: Object.keys(hierarchy[year] || {}).sort((a, b) => parseInt(b) - parseInt(a)),
        year,
      };
    } else if (navigationPath.length === 2) {
      // Show days for selected year/month
      const year = navigationPath[0].value;
      const month = navigationPath[1].value;
      return {
        type: "days" as const,
        items: Object.keys(hierarchy[year]?.[month] || {}).sort((a, b) => parseInt(b) - parseInt(a)),
        year,
        month,
      };
    } else {
      // Show photographs for selected year/month/day
      const year = navigationPath[0].value;
      const month = navigationPath[1].value;
      const day = navigationPath[2].value;
      return {
        type: "photographs" as const,
        items: hierarchy[year]?.[month]?.[day] || [],
      };
    }
  }, [navigationPath, hierarchy]);

  const navigateTo = (type: "year" | "month" | "day", value: string, label: string) => {
    if (type === "year") {
      setNavigationPath([{ type, value, label }]);
    } else if (type === "month") {
      setNavigationPath([
        { type: "year", value: navigationPath[0].value, label: navigationPath[0].label },
        { type, value, label },
      ]);
    } else if (type === "day") {
      setNavigationPath([
        { type: "year", value: navigationPath[0].value, label: navigationPath[0].label },
        { type: "month", value: navigationPath[1].value, label: navigationPath[1].label },
        { type, value, label },
      ]);
    }
  };

  const navigateToUnknown = () => {
    setNavigationPath([{ type: "year" as const, value: "Unknown", label: "Unknown" }]);
  };

  const navigateUp = (level: number) => {
    setNavigationPath(navigationPath.slice(0, level));
  };

  const getMonthName = (month: string) => {
    const monthNames = [
      "January", "February", "March", "April", "May", "June",
      "July", "August", "September", "October", "November", "December"
    ];
    return monthNames[parseInt(month) - 1];
  };

  const sortedPhotographs = useMemo(() => {
    if (currentView.type !== "photographs") return [];

    const photos = [...currentView.items];
    return photos.sort((a, b) => {
      let comparison = 0;
      if (sortMode === "id") {
        comparison = a.id - b.id;
      } else {
        const dateA = a.time ? new Date(a.time).getTime() : new Date(a.created_at).getTime();
        const dateB = b.time ? new Date(b.time).getTime() : new Date(b.created_at).getTime();
        comparison = dateA - dateB;
      }
      return ascending ? comparison : -comparison;
    });
  }, [currentView, sortMode, ascending]);

  const formatTime = (timeValue: string | null | undefined): string | null => {
    if (timeValue === null || timeValue === undefined || timeValue === "") {
      return null;
    }
    try {
      const date = new Date(timeValue);
      if (isNaN(date.getTime())) {
        return timeValue;
      }
      return date.toLocaleString();
    } catch (e) {
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
        {currentView.type === "photographs" && (
          <div className="sort-controls">
            <button className="sort-toggle" onClick={toggleSort}>
              Sort by: {sortMode === "id" ? "ID" : "Date"}
            </button>
            <button className="sort-order" onClick={toggleOrder} title={ascending ? "Ascending" : "Descending"}>
              {ascending ? "▲" : "▼"}
            </button>
          </div>
        )}
      </div>

      {/* Breadcrumb Navigation */}
      <div className="breadcrumb">
        <button
          className="breadcrumb-item"
          onClick={() => setNavigationPath([])}
        >
          All Photographs
        </button>
        {navigationPath.map((item, index) => (
          <span key={index}>
            <span className="breadcrumb-separator">›</span>
            <button
              className="breadcrumb-item"
              onClick={() => navigateUp(index + 1)}
            >
              {item.label}
            </button>
          </span>
        ))}
      </div>

      {/* Current View */}
      {currentView.type === "years" && (
        <div className="hierarchy-grid">
          {currentView.items.map((year) => {
            let yearPhotos: Photograph[] = [];
            if (year === "Unknown") {
              yearPhotos = hierarchy["Unknown"]?.[""]?.[""] || [];
            } else {
              yearPhotos = Object.values(hierarchy[year] || {})
                .flatMap(months => Object.values(months))
                .flat();
            }
            return (
              <div
                key={year}
                className="hierarchy-item"
                onClick={() => year === "Unknown" ? navigateToUnknown() : navigateTo("year", year, year)}
              >
                <div className="hierarchy-item-name">{year}</div>
                <div className="hierarchy-item-count">{yearPhotos.length} photos</div>
              </div>
            );
          })}
        </div>
      )}

      {currentView.type === "months" && (
        <div className="hierarchy-grid">
          {currentView.items.map((month) => {
            const monthPhotos = Object.values(hierarchy[currentView.year!]?.[month] || {})
              .flat();
            return (
              <div
                key={month}
                className="hierarchy-item"
                onClick={() => navigateTo("month", month, getMonthName(month))}
              >
                <div className="hierarchy-item-name">{getMonthName(month)}</div>
                <div className="hierarchy-item-count">{monthPhotos.length} photos</div>
              </div>
            );
          })}
        </div>
      )}

      {currentView.type === "days" && (
        <div className="hierarchy-grid">
          {currentView.items.map((day) => {
            const dayPhotos = hierarchy[currentView.year!]?.[currentView.month!]?.[day] || [];
            return (
              <div
                key={day}
                className="hierarchy-item"
                onClick={() => navigateTo("day", day, day)}
              >
                <div className="hierarchy-item-name">Day {day}</div>
                <div className="hierarchy-item-count">{dayPhotos.length} photos</div>
              </div>
            );
          })}
        </div>
      )}

      {currentView.type === "photographs" && (
        sortedPhotographs.length === 0 ? (
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
        )
      )}
    </div>
  );
}

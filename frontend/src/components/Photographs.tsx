import { useState, useEffect, useMemo, useRef } from "react";
import { api } from "../api";
import type { Photograph, Album } from "../types";

type SortMode = "id" | "date";
type NavigationPath = {
  type: "year" | "month" | "day";
  value: string;
  label: string;
};

export function Photographs() {
  const [photographs, setPhotographs] = useState<Photograph[]>([]);
  const [loading, setLoading] = useState(false); // Start as false, only set true when actually fetching
  const [error, setError] = useState<string | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>("id");
  const [ascending, setAscending] = useState<boolean>(true);
  const [navigationPath, setNavigationPath] = useState<NavigationPath[]>([]);
  const [selectedPhotos, setSelectedPhotos] = useState<Set<number>>(new Set());
  const [albums, setAlbums] = useState<Album[]>([]);
  const [showAddToAlbumDropdown, setShowAddToAlbumDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowAddToAlbumDropdown(false);
      }
    };

    if (showAddToAlbumDropdown) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => {
        document.removeEventListener("mousedown", handleClickOutside);
      };
    }
  }, [showAddToAlbumDropdown]);

  // Load albums on mount
  useEffect(() => {
    const loadAlbums = async () => {
      try {
        const allAlbums = await api.getAllAlbums();
        setAlbums(allAlbums);
      } catch (err) {
        console.error("Failed to load albums:", err);
      }
    };
    loadAlbums();
  }, []);

  // Only fetch photographs when at leaf level (day or Unknown)
  // For hierarchy navigation (year/month), use summary endpoints instead
  useEffect(() => {
    const shouldFetchPhotos =
      navigationPath.length === 3 || // At day level
      (navigationPath.length === 1 && navigationPath[0].value === "Unknown"); // At Unknown level

    if (shouldFetchPhotos) {
      loadPhotographs();
    } else {
      // Clear photos when not at leaf level to save memory
      setPhotographs([]);
      setSelectedPhotos(new Set()); // Clear selection when navigating away
    }
  }, [navigationPath]);

  const loadPhotographs = async () => {
    try {
      setLoading(true);

      // Only fetch photos when at leaf level (day or Unknown)
      // This prevents pagination through thousands of photos when just navigating
      const shouldFetch =
        navigationPath.length === 3 || // At day level
        (navigationPath.length === 1 && navigationPath[0].value === "Unknown"); // At Unknown level

      if (!shouldFetch) {
        setPhotographs([]);
        setLoading(false);
        return;
      }

      // Build filter parameters based on navigation path
      const params: { year?: string; month?: string; day?: string } = {};

      if (navigationPath.length > 0) {
        params.year = navigationPath[0].value;
      }
      if (navigationPath.length > 1) {
        params.month = navigationPath[1].value;
      }
      if (navigationPath.length > 2) {
        params.day = navigationPath[2].value;
      }

      // Ensure we have at least one filter parameter
      if (Object.keys(params).length === 0) {
        console.warn("loadPhotographs called without filters, skipping");
        setPhotographs([]);
        setLoading(false);
        return;
      }

      const allPhotographs = await api.getAllPhotographs(params);
      setPhotographs(allPhotographs);

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

  // Selection management
  const togglePhotoSelection = (photoId: number) => {
    setSelectedPhotos((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(photoId)) {
        newSet.delete(photoId);
      } else {
        newSet.add(photoId);
      }
      return newSet;
    });
  };

  const selectAll = () => {
    if (currentView.type === "photographs") {
      const allIds = new Set(sortedPhotographs.map((p) => p.id));
      setSelectedPhotos(allIds);
    }
  };

  const unselectAll = () => {
    setSelectedPhotos(new Set());
  };

  const isAllSelected = () => {
    if (currentView.type !== "photographs") return false;
    return sortedPhotographs.length > 0 && selectedPhotos.size === sortedPhotographs.length;
  };

  // Action handlers
  const handleDelete = async () => {
    if (selectedPhotos.size === 0) return;

    try {
      const photoIds = Array.from(selectedPhotos);
      for (const photoId of photoIds) {
        await api.createPlannedAction({
          action_type: "DELETE",
          photograph: photoId,
        });
      }
      setSelectedPhotos(new Set());
      setError(null);
      // Optionally reload photos to show updated state
      // loadPhotographs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to schedule deletion");
    }
  };

  const handleAddToAlbum = async (albumId: number) => {
    if (selectedPhotos.size === 0) return;

    try {
      const photoIds = Array.from(selectedPhotos);
      await api.addPhotosToAlbum(albumId, photoIds);
      setShowAddToAlbumDropdown(false);
      setSelectedPhotos(new Set());
      // Reload photos to get updated album information
      await loadPhotographs();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add photos to album");
    }
  };

  const handleRemoveFromAlbum = async (albumId: number) => {
    if (selectedPhotos.size === 0) return;

    try {
      const photoIds = Array.from(selectedPhotos);
      await api.removePhotosFromAlbum(albumId, photoIds);
      setSelectedPhotos(new Set());
      // Reload photos to get updated album information
      await loadPhotographs();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove photos from album");
    }
  };

  // Get common albums for selected photos
  const getCommonAlbums = (): Album[] => {
    if (selectedPhotos.size === 0) return [];

    const selectedPhotoObjects = photographs.filter((p) => selectedPhotos.has(p.id));
    if (selectedPhotoObjects.length === 0) return [];

    // Get albums that ALL selected photos belong to
    const albumIds = selectedPhotoObjects[0].albums.map((a) => a.id);
    const commonAlbums = albumIds.filter((albumId) =>
      selectedPhotoObjects.every((photo) =>
        photo.albums.some((a) => a.id === albumId)
      )
    );

    return albums.filter((album) => commonAlbums.includes(album.id));
  };

  // Build hierarchical structure: Year > Month > Day, with "Unknown" for photos without time
  // This is now only used when we have actual photo data (at leaf levels)
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

  // Fetch hierarchy summary data (years/months/days) without loading all photos
  const [hierarchyData, setHierarchyData] = useState<{
    years?: Array<{ year: string; count: number }>;
    months?: Array<{ month: string; count: number }>;
    days?: Array<{ day: string; count: number }>;
  }>({});

  useEffect(() => {
    const loadHierarchyData = async () => {
      try {
        if (navigationPath.length === 0) {
          // Load years
          const years = await api.getPhotographYears();
          setHierarchyData({ years });
        } else if (navigationPath.length === 1 && navigationPath[0].value !== "Unknown") {
          // Load months for selected year
          const months = await api.getPhotographMonths(navigationPath[0].value);
          setHierarchyData({ months });
        } else if (navigationPath.length === 2) {
          // Load days for selected year/month
          const days = await api.getPhotographDays(navigationPath[0].value, navigationPath[1].value);
          setHierarchyData({ days });
        } else {
          setHierarchyData({});
        }
      } catch (err) {
        console.error("Failed to load hierarchy data:", err);
      }
    };

    loadHierarchyData();
  }, [navigationPath]);

  // Get current view based on navigation path
  // Use hierarchyData (from summary endpoints) for navigation, hierarchy (from photos) only for leaf display
  const currentView = useMemo(() => {
    if (navigationPath.length === 0) {
      // Show years from summary data - sorted ascending
      const years = hierarchyData.years || [];
      const sortedYears = years
        .map(y => y.year)
        .sort((a, b) => {
          if (a === "Unknown" || b === "Unknown") return 0;
          return parseInt(a) - parseInt(b); // Ascending
        });
      return {
        type: "years" as const,
        items: sortedYears,
        counts: Object.fromEntries(years.map(y => [y.year, y.count])),
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
      const months = hierarchyData.months || [];
      const sortedMonths = months
        .map(m => m.month)
        .sort((a, b) => parseInt(a) - parseInt(b)); // Ascending
      return {
        type: "months" as const,
        items: sortedMonths,
        year,
        counts: Object.fromEntries(months.map(m => [m.month, m.count])),
      };
    } else if (navigationPath.length === 2) {
      // Show days for selected year/month
      const year = navigationPath[0].value;
      const month = navigationPath[1].value;
      const days = hierarchyData.days || [];
      const sortedDays = days
        .map(d => d.day)
        .sort((a, b) => parseInt(a) - parseInt(b)); // Ascending
      return {
        type: "days" as const,
        items: sortedDays,
        year,
        month,
        counts: Object.fromEntries(days.map(d => [d.day, d.count])),
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
  }, [navigationPath, hierarchy, hierarchyData]);

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

  // Show loading only when actually fetching data
  const isActuallyLoading = loading && (
    navigationPath.length === 3 ||
    (navigationPath.length === 1 && navigationPath[0].value === "Unknown") ||
    (navigationPath.length === 0 && !hierarchyData.years) ||
    (navigationPath.length === 1 && navigationPath[0].value !== "Unknown" && !hierarchyData.months) ||
    (navigationPath.length === 2 && !hierarchyData.days)
  );

  if (isActuallyLoading) {
    return <div className="loading">Loading...</div>;
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
            const count = currentView.counts?.[year] ??
              (year === "Unknown"
                ? (hierarchy["Unknown"]?.[""]?.[""] || []).length
                : Object.values(hierarchy[year] || {})
                    .flatMap(months => Object.values(months))
                    .flat().length);
            return (
              <div
                key={year}
                className="hierarchy-item"
                onClick={() => year === "Unknown" ? navigateToUnknown() : navigateTo("year", year, year)}
              >
                <div className="hierarchy-item-name">{year}</div>
                <div className="hierarchy-item-count">{count} photos</div>
              </div>
            );
          })}
        </div>
      )}

      {currentView.type === "months" && (
        <div className="hierarchy-grid">
          {currentView.items.map((month) => {
            const count = currentView.counts?.[month] ??
              Object.values(hierarchy[currentView.year!]?.[month] || {}).flat().length;
            return (
              <div
                key={month}
                className="hierarchy-item"
                onClick={() => navigateTo("month", month, getMonthName(month))}
              >
                <div className="hierarchy-item-name">{getMonthName(month)}</div>
                <div className="hierarchy-item-count">{count} photos</div>
              </div>
            );
          })}
        </div>
      )}

      {currentView.type === "days" && (
        <div className="hierarchy-grid">
          {currentView.items.map((day) => {
            const count = currentView.counts?.[day] ??
              (hierarchy[currentView.year!]?.[currentView.month!]?.[day] || []).length;
            return (
              <div
                key={day}
                className="hierarchy-item"
                onClick={() => navigateTo("day", day, day)}
              >
                <div className="hierarchy-item-name">Day {day}</div>
                <div className="hierarchy-item-count">{count} photos</div>
              </div>
            );
          })}
        </div>
      )}

      {currentView.type === "photographs" && (
        <>
          {/* Action Bar */}
          {sortedPhotographs.length > 0 && (
            <div className="action-bar">
              <div className="action-bar-left">
                <button
                  className="action-button"
                  onClick={isAllSelected() ? unselectAll : selectAll}
                >
                  {isAllSelected() ? "Unselect All" : "Select All"}
                </button>
                {selectedPhotos.size > 0 && (
                  <span className="selection-count">
                    {selectedPhotos.size} selected
                  </span>
                )}
              </div>
              {selectedPhotos.size > 0 && (
                <div className="action-bar-right">
                  <button
                    className="action-button delete-button"
                    onClick={handleDelete}
                  >
                    Delete
                  </button>
                  <div className="dropdown-container" ref={dropdownRef}>
                    <button
                      className="action-button"
                      onClick={() => setShowAddToAlbumDropdown(!showAddToAlbumDropdown)}
                    >
                      Add to Album ▼
                    </button>
                    {showAddToAlbumDropdown && (
                      <div className="dropdown-menu">
                        {albums.length === 0 ? (
                          <div className="dropdown-item disabled">No albums available</div>
                        ) : (
                          albums.map((album) => (
                            <div
                              key={album.id}
                              className="dropdown-item"
                              onClick={() => handleAddToAlbum(album.id)}
                            >
                              {album.name}
                            </div>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                  {getCommonAlbums().map((album) => (
                    <button
                      key={album.id}
                      className="action-button remove-button"
                      onClick={() => handleRemoveFromAlbum(album.id)}
                    >
                      Remove from {album.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          {sortedPhotographs.length === 0 ? (
            <p className="empty-state">No photographs found.</p>
          ) : (
            <div className="photographs-grid">
              {sortedPhotographs.map((photo) => (
                <div
                  key={photo.id}
                  className={`photograph-card ${selectedPhotos.has(photo.id) ? "selected" : ""}`}
                  onClick={() => togglePhotoSelection(photo.id)}
                >
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
                  <div className={`photograph-id ${photo.has_errors ? 'has-errors' : ''}`}>
                    ID: {photo.id}
                  </div>
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
                  {photo.model && (
                    <div className="photograph-model">
                      <span className="field-label">Camera Model:</span>{" "}
                      <span className="model-value">{photo.model}</span>
                    </div>
                  )}
                  <div className="photograph-hash">
                    {photo.hash ? (
                      <div>
                        <span className="field-label">Hash:</span>{" "}
                        <code className={photo.has_errors ? 'has-errors' : ''}>
                          {photo.hash.substring(0, 16)}...
                        </code>
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
                  {photo.albums && photo.albums.length > 0 && (
                    <div className="photograph-albums">
                      <span className="field-label">Albums:</span>{" "}
                      <div className="albums-tags">
                        {photo.albums.map((album) => (
                          <span key={album.id} className="album-tag-bubble">
                            {album.name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
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
        </>
      )}
    </div>
  );
}

import { useState, useEffect, useMemo } from "react";
import { api } from "../api";
import type { PhotoPath } from "../types";

type NavigationPath = {
  type: "segment";
  value: string;
  label: string;
  fullPath: string;
};

type SortMode = "id" | "path" | "device" | "date";

export function PhotoPaths() {
  const [paths, setPaths] = useState<PhotoPath[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [navigationPath, setNavigationPath] = useState<NavigationPath[]>([]);
  const [sortMode, setSortMode] = useState<SortMode>("id");
  const [ascending, setAscending] = useState<boolean>(true);

  useEffect(() => {
    loadPaths();
  }, [navigationPath]);

  useEffect(() => {
    // Only fetch paths when directory structure indicates there are files at this level
    // This prevents unnecessary pagination requests when only directories are present
    const hasFiles = directoryStructure.some(item => !item.is_directory);
    if (hasFiles) {
      loadPaths();
    } else if (directoryStructure.length > 0) {
      // Only directories, no need to fetch paths yet
      setPaths([]);
    }
  }, [navigationPath, directoryStructure]);

  const loadPaths = async () => {
    try {
      setLoading(true);

      const pathPrefix = navigationPath.length > 0
        ? navigationPath.map(n => n.value).join("/")
        : undefined;

      // Fetch paths for the current directory level
      // Use only_direct=true to only get files at this level, not in subdirectories
      // This prevents fetching thousands of paths when navigating directories
      const allPaths = await api.getAllPhotoPaths(pathPrefix, true);
      setPaths(allPaths);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load photo paths");
    } finally {
      setLoading(false);
    }
  };

  // Fetch directory structure summary
  const [directoryStructure, setDirectoryStructure] = useState<Array<{
    name: string;
    is_directory: boolean;
    count: number;
  }>>([]);

  useEffect(() => {
    const loadDirectoryStructure = async () => {
      try {
        const pathPrefix = navigationPath.length > 0
          ? navigationPath.map(n => n.value).join("/")
          : undefined;
        const directories = await api.getPhotoPathDirectories(pathPrefix);
        setDirectoryStructure(directories);
      } catch (err) {
        console.error("Failed to load directory structure:", err);
      }
    };

    loadDirectoryStructure();
  }, [navigationPath]);

  // Parse paths and build hierarchy (only used when we have actual path data)
  const pathHierarchy = useMemo(() => {
    const hierarchy: Record<string, { children: Record<string, any>; paths: PhotoPath[] }> = {};

    paths.forEach((path) => {
      const pathParts = path.path.split(/[/\\]/).filter(p => p.length > 0);

      let current = hierarchy;
      pathParts.forEach((part, index) => {
        if (!current[part]) {
          current[part] = { children: {}, paths: [] };
        }
        if (index === pathParts.length - 1) {
          // This is the file, add the path
          current[part].paths.push(path);
        }
        current = current[part].children;
      });
    });

    return hierarchy;
  }, [paths]);

  // Get current view based on navigation path
  const currentView = useMemo(() => {
    // Use directory structure from API when available (for hierarchy levels)
    if (directoryStructure.length > 0) {
      const segments = directoryStructure
        .filter(item => item.is_directory)
        .map(item => item.name)
        .sort();
      const fileItems = directoryStructure.filter(item => !item.is_directory);

      return {
        type: "mixed" as const,
        segments,
        paths: [], // Files will be loaded when user navigates deeper or we have path data
        directoryStructure,
      };
    }

    // Fallback to path hierarchy when we have actual path data
    if (navigationPath.length === 0) {
      // Show root segments - only directories, not files
      const rootSegments = Object.keys(pathHierarchy).filter(key =>
        Object.keys(pathHierarchy[key].children).length > 0
      );
      const rootFiles = Object.values(pathHierarchy)
        .filter(node => Object.keys(node.children).length === 0)
        .flatMap(node => node.paths);

      return {
        type: "root" as const,
        segments: rootSegments.sort(),
        paths: rootFiles,
      };
    } else {
      // Navigate through hierarchy
      let current = pathHierarchy;
      for (const nav of navigationPath) {
        if (!current[nav.value]) {
          return { type: "paths" as const, items: [] };
        }
        current = current[nav.value].children;
      }

      // Get items at current level
      // Only include segments that have children (directories), not just files
      const segments = Object.keys(current).filter(key =>
        Object.keys(current[key].children).length > 0
      );

      // Get paths at current level (files only, not directories)
      const pathsAtLevel: PhotoPath[] = [];
      Object.values(current).forEach(node => {
        // Only add paths if this node has no children (it's a file, not a directory)
        if (Object.keys(node.children).length === 0) {
          pathsAtLevel.push(...node.paths);
        }
      });

      return {
        type: "mixed" as const,
        segments: segments.sort(),
        paths: pathsAtLevel,
      };
    }
  }, [navigationPath, pathHierarchy, directoryStructure, paths]);

  const navigateTo = (segment: string) => {
    const fullPath = navigationPath.length === 0
      ? segment
      : `${navigationPath.map(n => n.value).join("/")}/${segment}`;

    setNavigationPath([
      ...navigationPath,
      { type: "segment", value: segment, label: segment, fullPath },
    ]);
  };

  const navigateUp = (level: number) => {
    setNavigationPath(navigationPath.slice(0, level));
  };

  const toggleSort = () => {
    const modes: SortMode[] = ["id", "path", "device", "date"];
    const currentIndex = modes.indexOf(sortMode);
    const nextIndex = (currentIndex + 1) % modes.length;
    setSortMode(modes[nextIndex]);
  };

  const toggleOrder = () => {
    setAscending((prev) => !prev);
  };

  // Sort paths based on current sort mode and order
  const sortPaths = (pathsToSort: PhotoPath[]): PhotoPath[] => {
    const sorted = [...pathsToSort].sort((a, b) => {
      let comparison = 0;

      switch (sortMode) {
        case "id":
          comparison = a.id - b.id;
          break;
        case "path":
          comparison = a.path.localeCompare(b.path);
          break;
        case "device":
          comparison = a.device.localeCompare(b.device);
          break;
        case "date":
          comparison = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
          break;
      }

      return ascending ? comparison : -comparison;
    });

    return sorted;
  };

  // Get paths that match the current navigation path
  const getFilteredPaths = () => {
    if (navigationPath.length === 0) {
      return paths;
    }

    const prefix = navigationPath.map(n => n.value).join("/");
    return paths.filter(path => {
      const normalizedPath = path.path.replace(/\\/g, "/");
      return normalizedPath.startsWith(prefix + "/") || normalizedPath === prefix;
    });
  };

  if (loading) {
    return <div className="loading">Loading photo paths...</div>;
  }

  if (error) {
    return <div className="error">Error: {error}</div>;
  }

  const getSortModeLabel = () => {
    switch (sortMode) {
      case "id":
        return "ID";
      case "path":
        return "Path";
      case "device":
        return "Device";
      case "date":
        return "Date";
    }
  };

  return (
    <div className="photo-paths">
      <div className="photo-paths-header">
        <h2>Photo Paths ({paths.length})</h2>
        {(currentView.type === "root" || currentView.type === "mixed") &&
         (currentView.paths.length > 0 || (currentView.type === "root" && currentView.segments.length === 0)) && (
          <div className="sort-controls">
            <button className="sort-toggle" onClick={toggleSort}>
              Sort by: {getSortModeLabel()}
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
          All Paths
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
      {currentView.type === "root" && (
        <>
          {currentView.segments.length > 0 && (
            <div className="hierarchy-section">
              <h3>Directories</h3>
              <div className="hierarchy-grid">
                {currentView.segments.map((segment) => {
                  const node = pathHierarchy[segment];
                  const totalPaths = countPathsInNode(node);
                  return (
                    <div
                      key={segment}
                      className="hierarchy-item"
                      onClick={() => navigateTo(segment)}
                    >
                      <div className="hierarchy-item-name">{segment}</div>
                      <div className="hierarchy-item-count">{totalPaths} path{totalPaths !== 1 ? "s" : ""}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {currentView.paths.length > 0 && (
            <div className="paths-section">
              <h3>Files ({currentView.paths.length})</h3>
              <div className="paths-list">
                {sortPaths(currentView.paths).map((path) => (
                  <div key={path.id} className="path-card">
                    {path.photograph_image_url && (
                      <div className="path-image-container">
                        <img
                          src={path.photograph_image_url}
                          alt={`Photo for path ${path.id}`}
                          className="path-image"
                        />
                      </div>
                    )}
                    <div className="path-content">
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
                          <div>
                            <span className="path-photograph">
                              <span className="field-label">Linked to Photograph:</span> #{path.photograph}
                            </span>
                            {path.photograph_paths_count > 1 && (
                              <div className="path-other-paths">
                                <span className="field-label">Other paths ({path.photograph_paths_count - 1}):</span>
                                <div className="other-paths-list">
                                  {path.other_paths.map((otherPath) => (
                                    <div key={otherPath.id} className="other-path-item">
                                      <span className="other-path-device">{otherPath.device}</span>
                                      <span className="other-path-value">{otherPath.path}</span>
                                    </div>
                                  ))}
                                  {path.photograph_paths_count - 1 > path.other_paths.length && (
                                    <div className="other-path-more">
                                      ... and {path.photograph_paths_count - 1 - path.other_paths.length} more
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
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
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {currentView.type === "mixed" && (
        <>
          {(currentView.segments.length > 0 || (currentView as any).directoryStructure) && (
            <div className="hierarchy-section">
              <h3>Directories</h3>
              <div className="hierarchy-grid">
                {((currentView as any).directoryStructure?.filter((item: any) => item.is_directory) || currentView.segments.map(name => ({ name, is_directory: true, count: 0 }))).map((item: any) => {
                  const segment = typeof item === 'string' ? item : item.name;
                  let count = 0;
                  if (typeof item === 'object' && item.count !== undefined) {
                    count = item.count;
                  } else {
                    // Fallback to counting from hierarchy
                    let current = pathHierarchy;
                    for (const nav of navigationPath) {
                      current = current[nav.value]?.children || {};
                    }
                    const node = current[segment];
                    if (node) {
                      count = countPathsInNode(node);
                    }
                  }
                  return (
                    <div
                      key={segment}
                      className="hierarchy-item"
                      onClick={() => navigateTo(segment)}
                    >
                      <div className="hierarchy-item-name">{segment}</div>
                      <div className="hierarchy-item-count">{count} path{count !== 1 ? "s" : ""}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {currentView.paths.length > 0 && (
            <div className="paths-section">
              <h3>Files ({currentView.paths.length})</h3>
              <div className="paths-list">
                {sortPaths(currentView.paths).map((path) => (
                  <div key={path.id} className="path-card">
                    {path.photograph_image_url && (
                      <div className="path-image-container">
                        <img
                          src={path.photograph_image_url}
                          alt={`Photo for path ${path.id}`}
                          className="path-image"
                        />
                      </div>
                    )}
                    <div className="path-content">
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
                          <div>
                            <span className="path-photograph">
                              <span className="field-label">Linked to Photograph:</span> #{path.photograph}
                            </span>
                            {path.photograph_paths_count > 1 && (
                              <div className="path-other-paths">
                                <span className="field-label">Other paths ({path.photograph_paths_count - 1}):</span>
                                <div className="other-paths-list">
                                  {path.other_paths.map((otherPath) => (
                                    <div key={otherPath.id} className="other-path-item">
                                      <span className="other-path-device">{otherPath.device}</span>
                                      <span className="other-path-value">{otherPath.path}</span>
                                    </div>
                                  ))}
                                  {path.photograph_paths_count - 1 > path.other_paths.length && (
                                    <div className="other-path-more">
                                      ... and {path.photograph_paths_count - 1 - path.other_paths.length} more
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
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
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// Helper function to count all paths in a node and its children
function countPathsInNode(node: { children: Record<string, any>; paths: PhotoPath[] }): number {
  let count = node.paths.length;
  for (const child of Object.values(node.children)) {
    count += countPathsInNode(child);
  }
  return count;
}

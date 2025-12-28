import { useState, useEffect, useMemo } from "react";
import { api } from "../api";
import type { PhotoPath } from "../types";

type NavigationPath = {
  type: "segment";
  value: string;
  label: string;
  fullPath: string;
};

export function PhotoPaths() {
  const [paths, setPaths] = useState<PhotoPath[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [navigationPath, setNavigationPath] = useState<NavigationPath[]>([]);

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

  // Parse paths and build hierarchy
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
  }, [navigationPath, pathHierarchy]);

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

  return (
    <div className="photo-paths">
      <h2>Photo Paths ({paths.length})</h2>

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
                {currentView.paths.map((path) => (
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
            </div>
          )}
        </>
      )}

      {currentView.type === "mixed" && (
        <>
          {currentView.segments.length > 0 && (
            <div className="hierarchy-section">
              <h3>Directories</h3>
              <div className="hierarchy-grid">
                {currentView.segments.map((segment) => {
                  let current = pathHierarchy;
                  for (const nav of navigationPath) {
                    current = current[nav.value].children;
                  }
                  const node = current[segment];
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
                {currentView.paths.map((path) => (
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

import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { api } from "../api";
import type { PhotoPath, PhotoPathDeviceSummary } from "../types";
import { LazyThumbnail } from "./LazyThumbnail";

type NavigationPath = {
  type: "device" | "segment";
  value: string;
  label: string;
  fullPath: string;
};

type SortMode = "id" | "path" | "device" | "date";

type PathNode = {
  children: Record<string, PathNode>;
  paths: PhotoPath[];
};

export function PhotoPaths() {
  const [paths, setPaths] = useState<PhotoPath[]>([]);
  const [loadingDevices, setLoadingDevices] = useState(true);
  const [loadingDirectories, setLoadingDirectories] = useState(false);
  const [loadingPaths, setLoadingPaths] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [navigationPath, setNavigationPath] = useState<NavigationPath[]>([]);
  const [sortMode, setSortMode] = useState<SortMode>("id");
  const [ascending, setAscending] = useState<boolean>(true);
  const [devices, setDevices] = useState<PhotoPathDeviceSummary[]>([]);

  const formatDeviceMeta = (d: PhotoPathDeviceSummary): string | null => {
    const parts: string[] = [];
    if (d.vendor || d.model) {
      parts.push([d.vendor, d.model].filter(Boolean).join(" "));
    }
    if (d.serial) {
      parts.push(`S/N ${d.serial}`);
    }
    const uuid = d.filesystem_uuid;
    if (uuid && !uuid.startsWith("photchart:")) {
      parts.push(uuid.slice(0, 8) + "…");
    } else if (d.fstype) {
      parts.push(d.fstype);
    }
    if (d.capacity_bytes != null && d.capacity_bytes > 0) {
      const gb = d.capacity_bytes / (1024 ** 3);
      parts.push(`${gb.toFixed(1)} GB`);
    }
    return parts.length > 0 ? parts.join(" · ") : null;
  };

  // Pagination state
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);

  // Total count state (fetched from API, doesn't flicker)
  const [totalCount, setTotalCount] = useState<number | null>(null);

  // Ref for scroll detection
  const loadMoreTriggerRef = useRef<HTMLDivElement>(null);
  const nextPageUrlRef = useRef<string | null>(null);
  const pathsLoadedForLevelRef = useRef<string | null>(null);
  const directoriesAbortRef = useRef<AbortController | null>(null);

  // Fetch directory structure summary
  const [directoryStructure, setDirectoryStructure] = useState<Array<{
    name: string;
    is_directory: boolean;
    count: number;
  }>>([]);

  // Get current device from navigation path
  const currentDevice = useMemo(() => {
    const deviceItem = navigationPath.find(item => item.type === "device");
    return deviceItem ? deviceItem.value : undefined;
  }, [navigationPath]);

  // Get path segments (excluding device)
  const pathSegments = useMemo(() => {
    return navigationPath.filter(item => item.type === "segment");
  }, [navigationPath]);

  const pathPrefix = useMemo(
    () =>
      pathSegments.length > 0
        ? pathSegments.map((n) => n.value).join("/")
        : undefined,
    [pathSegments]
  );

  const levelKey = useMemo(
    () => (currentDevice ? `${currentDevice}|${pathPrefix ?? ""}` : ""),
    [currentDevice, pathPrefix]
  );

  const fetchPathsPage = useCallback(
    async (reset: boolean) => {
      if (!currentDevice) {
        return;
      }

      try {
        if (reset) {
          setLoadingPaths(true);
          setPaths([]);
          nextPageUrlRef.current = null;
          setHasMore(false);
        } else {
          setLoadingMore(true);
        }

        const pageUrl = reset
          ? undefined
          : nextPageUrlRef.current || undefined;
        const response = await api.getPhotoPathsPage(
          pathPrefix,
          true,
          currentDevice,
          pageUrl
        );

        if (reset) {
          setPaths(response.results);
        } else {
          setPaths((prev) => [...prev, ...response.results]);
        }

        nextPageUrlRef.current = response.next;
        setHasMore(response.next !== null);
        setError(null);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load photo paths"
        );
      } finally {
        if (reset) {
          setLoadingPaths(false);
        } else {
          setLoadingMore(false);
        }
      }
    },
    [currentDevice, pathPrefix]
  );

  const loadMorePaths = useCallback(() => {
    if (!loadingMore && hasMore && nextPageUrlRef.current) {
      fetchPathsPage(false);
    }
  }, [fetchPathsPage, loadingMore, hasMore]);

  // Fetch paths once per level when directory structure indicates files at this level
  useEffect(() => {
    if (!currentDevice) {
      setPaths([]);
      nextPageUrlRef.current = null;
      setHasMore(false);
      pathsLoadedForLevelRef.current = null;
      return;
    }

    if (loadingDirectories) {
      return;
    }

    if (directoryStructure.length === 0) {
      setPaths([]);
      nextPageUrlRef.current = null;
      setHasMore(false);
      pathsLoadedForLevelRef.current = levelKey;
      return;
    }

    const hasFiles = directoryStructure.some((item) => !item.is_directory);
    if (!hasFiles) {
      setPaths([]);
      nextPageUrlRef.current = null;
      setHasMore(false);
      pathsLoadedForLevelRef.current = levelKey;
      return;
    }

    if (pathsLoadedForLevelRef.current === levelKey) {
      return;
    }

    pathsLoadedForLevelRef.current = levelKey;
    fetchPathsPage(true);
  }, [
    currentDevice,
    directoryStructure,
    loadingDirectories,
    levelKey,
    fetchPathsPage,
  ]);

  // Load devices at root level
  useEffect(() => {
    const loadDevices = async () => {
      try {
        setLoadingDevices(true);
        setError(null);
        const devicesList = await api.getPhotoPathDevices();
        setDevices(devicesList);
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "Failed to load devices";
        console.error("Failed to load devices:", err);
        setError(errorMessage);
        setDevices([]);
      } finally {
        setLoadingDevices(false);
      }
    };

    if (navigationPath.length === 0) {
      loadDevices();
    } else {
      // If we navigate away from root, clear devices to free memory
      setDevices([]);
    }
  }, [navigationPath]);

  useEffect(() => {
    if (!currentDevice) {
      directoriesAbortRef.current?.abort();
      directoriesAbortRef.current = null;
      setDirectoryStructure([]);
      setPaths([]);
      setLoadingDirectories(false);
      return;
    }

    directoriesAbortRef.current?.abort();
    const controller = new AbortController();
    directoriesAbortRef.current = controller;

    setDirectoryStructure([]);
    setPaths([]);
    nextPageUrlRef.current = null;
    setHasMore(false);
    pathsLoadedForLevelRef.current = null;
    setLoadingDirectories(true);
    setError(null);

    const loadDirectoryStructure = async () => {
      try {
        const directories = await api.getPhotoPathDirectories(
          pathPrefix,
          currentDevice
        );
        if (controller.signal.aborted) {
          return;
        }
        setDirectoryStructure(directories);
      } catch (err) {
        if (controller.signal.aborted) {
          return;
        }
        const errorMessage =
          err instanceof Error
            ? err.message
            : "Failed to load directory structure";
        console.error("Failed to load directory structure:", err);
        setError(errorMessage);
        setDirectoryStructure([]);
      } finally {
        if (!controller.signal.aborted) {
          setLoadingDirectories(false);
        }
      }
    };

    loadDirectoryStructure();

    return () => {
      controller.abort();
    };
  }, [pathPrefix, currentDevice]);

  // Parse paths and build hierarchy (only used when we have actual path data)
  const pathHierarchy = useMemo(() => {
    const hierarchy: Record<string, PathNode> = {};

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
    // If no device selected, show devices
    if (!currentDevice) {
      return {
        type: "devices" as const,
        devices: devices,
      };
    }

    // Device selected: directory tree comes from the API (including while loading)
    const segments = directoryStructure
      .filter((item) => item.is_directory)
      .map((item) => item.name)
      .sort();

    return {
      type: "mixed" as const,
      segments,
      paths,
      directoryStructure,
    };
  }, [currentDevice, devices, directoryStructure, paths]);

  const navigateToDevice = (device: string) => {
    setNavigationPath([
      { type: "device", value: device, label: device, fullPath: device },
    ]);
  };

  const navigateTo = (segment: string) => {
    const fullPath = pathSegments.length === 0
      ? segment
      : `${pathSegments.map(n => n.value).join("/")}/${segment}`;

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

  // Fetch total count when breadcrumb path changes
  useEffect(() => {
    const fetchCount = async () => {
      if (!currentDevice) {
        // At root level, use sum of device counts
        const sum = devices.reduce((s, d) => s + d.count, 0);
        setTotalCount(sum);
        return;
      }

      try {
        const pathPrefix = pathSegments.length > 0
          ? pathSegments.map(n => n.value).join("/")
          : undefined;
        const response = await api.getPhotoPathCount(pathPrefix, true, currentDevice);
        setTotalCount(response.count);
      } catch (err) {
        console.error("Failed to load path count:", err);
        // Don't set fallback here - let it use the previous value or default
      }
    };

    fetchCount();
  }, [currentDevice, pathSegments, devices]);

  // Calculate total path count for display
  // IMPORTANT: This hook must be called before any early returns
  const totalPathCount = useMemo(() => {
    // Use totalCount from API if available, otherwise fallback
    if (totalCount !== null) {
      return totalCount;
    }
    if (!currentDevice) {
      return devices.reduce((sum, d) => sum + d.count, 0);
    }
    return paths.length;
  }, [totalCount, currentDevice, devices, paths.length]);

  // Scroll detection for infinite scrolling
  useEffect(() => {
    if (!hasMore || loadingMore || !loadMoreTriggerRef.current) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        if (entry.isIntersecting) {
          loadMorePaths();
        }
      },
      {
        root: null,
        rootMargin: '100px', // Start loading when 100px before the trigger
        threshold: 0.1,
      }
    );

    const triggerElement = loadMoreTriggerRef.current;
    if (triggerElement) {
      observer.observe(triggerElement);
    }

    return () => {
      if (triggerElement) {
        observer.unobserve(triggerElement);
      }
    };
  }, [hasMore, loadingMore, loadMorePaths]);

  // Early returns must come AFTER all hooks
  // Don't return early for loading - show header and breadcrumb always
  // Only show error early return if it's a critical error
  const anyLoading =
    loadingDevices || loadingDirectories || loadingPaths;

  if (error && !anyLoading) {
    return (
      <div className="photo-paths">
        <div className="photo-paths-header">
          <h2>Photo Paths</h2>
        </div>
        <div className="breadcrumb">
          <button
            className="breadcrumb-item"
            onClick={() => setNavigationPath([])}
          >
            Device
          </button>
        </div>
        <div className="error">Error: {error}</div>
      </div>
    );
  }

  return (
    <div className="photo-paths">
      <div className="photo-paths-header">
        <h2>Photo Paths ({totalPathCount})</h2>
        {currentView.type === "mixed" && paths.length > 0 && (
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
          Device
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
      {loadingDevices && !currentDevice && (
        <div className="loading-content">
          <div className="loading">Loading devices...</div>
        </div>
      )}

      {!loadingDevices && currentView.type === "devices" && (
        <div className="hierarchy-section">
          <h3>Devices</h3>
          <div className="hierarchy-grid">
            {currentView.devices.map((device) => {
              const meta = formatDeviceMeta(device);
              return (
              <div
                key={device.filesystem_uuid}
                className="hierarchy-item"
                onClick={() => navigateToDevice(device.device)}
              >
                <div className="hierarchy-item-name">{device.device}</div>
                {meta && <div className="hierarchy-item-meta">{meta}</div>}
                <div className="hierarchy-item-count">{device.count} path{device.count !== 1 ? "s" : ""}</div>
              </div>
            );
            })}
          </div>
        </div>
      )}

      {currentView.type === "mixed" && (
        <>
          <div className="hierarchy-section">
            <h3>Directories</h3>
            {loadingDirectories ? (
              <div className="loading-content">
                <div className="loading">Loading directories...</div>
              </div>
            ) : (
              (currentView.segments.length > 0 ||
                currentView.directoryStructure.length > 0) && (
              <div className="hierarchy-grid">
                {(currentView.directoryStructure.length > 0
                  ? currentView.directoryStructure.filter((item) => item.is_directory)
                  : currentView.segments.map((name) => ({
                      name,
                      is_directory: true,
                      count: 0,
                    }))
                ).map((item) => {
                  const segment = item.name;
                  let count = item.count;
                  if (count === 0) {
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
              )
            )}
          </div>

          {(loadingPaths || paths.length > 0) && (
            <div className="paths-section">
              <h3>Files ({paths.length})</h3>
              {loadingPaths ? (
                <div className="loading-content">
                  <div className="loading">Loading files...</div>
                </div>
              ) : (
              <div className="paths-list">
                {sortPaths(paths).map((path) => (
                  <div key={path.id} className="path-card">
                    {path.photograph_image_url && (
                      <div className="path-image-container">
                        <LazyThumbnail
                          src={path.photograph_image_url}
                          alt={`Photo for path ${path.id}`}
                          className="path-image"
                        />
                      </div>
                    )}
                    <div className="path-content">
                      <div className="path-header">
                        <span className={`path-id ${path.photograph_has_errors ? 'has-errors' : ''}`}>
                          ID: {path.id}
                        </span>
                        <span className="path-device">
                          <span className="field-label">Device:</span> {path.device}
                          {path.storage_device && (
                            <span className="path-device-meta">
                              {" "}
                              ({[path.storage_device.vendor, path.storage_device.model]
                                .filter(Boolean)
                                .join(" ") || path.filesystem_uuid.slice(0, 13)}
                              …)
                            </span>
                          )}
                        </span>
                      </div>
                      <div className="path-value">
                        <span className="field-label">Path:</span> {path.path}
                      </div>
                      <div className="path-photograph-link">
                        {path.photograph ? (
                          <div>
                            <span className="path-photograph">
                              <span className="field-label">Linked to Photograph:</span>{" "}
                              <span className={path.photograph_has_errors ? 'has-errors' : ''}>
                                #{path.photograph}
                              </span>
                            </span>
                            {path.photograph_model && (
                              <div className="path-photograph-model">
                                <span className="field-label">Camera Model:</span>{" "}
                                <span className="model-value">{path.photograph_model}</span>
                              </div>
                            )}
                            {path.photograph_albums && path.photograph_albums.length > 0 && (
                              <div className="path-photograph-albums">
                                <span className="field-label">Albums:</span>{" "}
                                <div className="albums-list">
                                  {path.photograph_albums.map((album) => (
                                    <span key={album.id} className="album-tag">
                                      {album.name}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
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
                {/* Loading more indicator */}
                {hasMore && (
                  <div ref={loadMoreTriggerRef} className="load-more-trigger" style={{ height: '1px' }} />
                )}
                {loadingMore && (
                  <div className="loading-more">
                    <div className="loading-more-text">Loading more results...</div>
                  </div>
                )}
              </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// Helper function to count all paths in a node and its children
function countPathsInNode(node: PathNode): number {
  let count = node.paths.length;
  for (const child of Object.values(node.children)) {
    count += countPathsInNode(child);
  }
  return count;
}

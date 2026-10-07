import { useState, useEffect, useRef, useCallback } from "react";
import type { PhotoPath } from "../types";
import { truncatePathMiddle } from "../utils/pathDisplay";

type PhotographPathsDropdownProps = {
  paths: PhotoPath[];
};

export function PhotographPathsDropdown({ paths }: PhotographPathsDropdownProps) {
  const [open, setOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [open]);

  useEffect(() => {
    if (!toast) {
      return;
    }
    const timer = window.setTimeout(() => setToast(null), 2000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const copyPath = useCallback(async (path: string) => {
    try {
      await navigator.clipboard.writeText(path);
      setToast("Copied to clipboard");
    } catch {
      setToast("Could not copy path");
    }
  }, []);

  if (paths.length === 0) {
    return <span className="no-paths">No paths</span>;
  }

  const countLabel = `${paths.length} path${paths.length !== 1 ? "s" : ""}`;

  return (
    <div className="photograph-paths-dropdown dropdown-container" ref={containerRef}>
      <button
        type="button"
        className="paths-count-toggle"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        <span className="paths-count">{countLabel}</span>
        <span className="paths-toggle-chevron" aria-hidden="true">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="dropdown-menu photograph-paths-menu" role="listbox">
          {paths.map((photoPath) => (
            <button
              key={photoPath.id}
              type="button"
              role="option"
              className="dropdown-item path-copy-button"
              title={photoPath.path}
              onClick={() => copyPath(photoPath.path)}
            >
              {truncatePathMiddle(photoPath.path)}
            </button>
          ))}
        </div>
      )}
      {toast && (
        <div className="path-copy-toast" role="status" aria-live="polite">
          {toast}
        </div>
      )}
    </div>
  );
}

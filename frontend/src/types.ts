/** TypeScript types for the PhotoChart API */

export interface Album {
  id: number;
  name: string;
  description: string;
  photos_count: number;
  created_at: string;
  updated_at: string;
}

export interface Photograph {
  id: number;
  checksum: string | null;
  image: string | null;
  image_url: string | null;
  time: string | null;
  model: string | null;
  has_errors: boolean;
  paths: PhotoPath[];
  albums: Album[];
  created_at: string;
  updated_at: string;
}

export interface PhotoPath {
  id: number;
  path: string;
  device: string;
  photograph: number | null;
  photograph_image_url: string | null;
  photograph_paths_count: number;
  photograph_has_errors: boolean | null;
  photograph_model: string | null;
  photograph_albums: Album[];
  other_paths: Array<{
    id: number;
    path: string;
    device: string;
  }>;
  created_at: string;
  updated_at: string;
}

export interface Checksum {
  id: number;
  path: string;
  checksum: string;
}

export interface DirKind {
  id: number;
  name: string;
}

export interface Location {
  id: number;
  name: string;
}

export interface Directory {
  id: number;
  path: string;
  last_modified: string;
  mirror: number;
  kind: number;
  kind_name: string;
}

export interface TimeLoc {
  id: number;
  path: number;
  directory_path: string;
  timestamp: string;
  location: number;
  location_name: string;
}

export interface PlannedAction {
  id: number;
  action_type: string;
  photograph: number;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
  error: string;
  created_at: string;
  updated_at: string;
}

export interface OrganizerConfiguration {
  id: number;
  name: string;
  adapter: string;
  source: string;
  destination: string;
  pattern: string;
  quarantine: string | null;
  mode: "copy" | "move";
  timezone: string;
  collision: "suffix" | "fail" | "quarantine";
  duplicate_detection: "size_then_hash";
  workers: 1;
  scan_interval_seconds: number;
  process_after: string | null;
  include_first: boolean;
  day_starts_at: number;
  media_extensions: string[];
  date_priority: string[];
  stability: { interval_seconds: number; checks: number };
  retry: { attempts: number; initial_seconds: number; multiplier: number };
  enabled: boolean;
}

export interface OrganizerOperation {
  id: number;
  status: string;
  source: string;
  destination: string | null;
  date_source: string;
  detail: string;
  verified: boolean;
  catalog_status: "not_applicable" | "cataloged" | "manual_required";
}

export interface OrganizerJob {
  id: number;
  configuration: number;
  status: string;
  dry_run: boolean;
  error: string;
  created_at: string;
  operation_count?: number;
  operations?: OrganizerOperation[];
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

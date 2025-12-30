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
  hash: string | null;
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

export interface Hash {
  id: number;
  path: string;
  hash: string;
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

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

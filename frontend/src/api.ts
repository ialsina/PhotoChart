/** API client for PhotoFinder backend */

import type {
  Photograph,
  PhotoPath,
  Hash,
  Directory,
  DirKind,
  Location,
  TimeLoc,
  PaginatedResponse,
} from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

async function fetchAPI<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`);
  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }
  return response.json();
}

export const api = {
  // Photographs
  getPhotographs: (): Promise<PaginatedResponse<Photograph>> =>
    fetchAPI("/photographs/"),

  getPhotograph: (id: number): Promise<Photograph> =>
    fetchAPI(`/photographs/${id}/`),

  // Photo Paths
  getPhotoPaths: (): Promise<PaginatedResponse<PhotoPath>> =>
    fetchAPI("/photo-paths/"),

  getPhotoPath: (id: number): Promise<PhotoPath> =>
    fetchAPI(`/photo-paths/${id}/`),

  // Hashes
  getHashes: (): Promise<PaginatedResponse<Hash>> => fetchAPI("/hashes/"),

  getHash: (id: number): Promise<Hash> => fetchAPI(`/hashes/${id}/`),

  // Directories
  getDirectories: (): Promise<PaginatedResponse<Directory>> =>
    fetchAPI("/directories/"),

  getDirectory: (id: number): Promise<Directory> =>
    fetchAPI(`/directories/${id}/`),

  // Dir Kinds
  getDirKinds: (): Promise<PaginatedResponse<DirKind>> =>
    fetchAPI("/dir-kinds/"),

  // Locations
  getLocations: (): Promise<PaginatedResponse<Location>> =>
    fetchAPI("/locations/"),

  // Time Locs
  getTimeLocs: (): Promise<PaginatedResponse<TimeLoc>> =>
    fetchAPI("/time-locs/"),
};

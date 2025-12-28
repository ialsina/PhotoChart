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

async function fetchAllPages<T>(
  endpoint: string,
  params?: Record<string, string>
): Promise<T[]> {
  const allItems: T[] = [];
  let url = `${API_BASE_URL}${endpoint}`;

  // Add query parameters if provided
  if (params) {
    const searchParams = new URLSearchParams(params);
    url += `?${searchParams.toString()}`;
  }

  let nextUrl: string | null = url;

  while (nextUrl) {
    const response = await fetch(nextUrl);
    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }
    const data: PaginatedResponse<T> = await response.json();
    allItems.push(...data.results);
    nextUrl = data.next;
  }

  return allItems;
}

export const api = {
  // Photographs
  getPhotographs: (): Promise<PaginatedResponse<Photograph>> =>
    fetchAPI("/photographs/"),

  getAllPhotographs: (params?: { year?: string; month?: string; day?: string }): Promise<Photograph[]> => {
    const queryParams: Record<string, string> = {};
    if (params?.year) queryParams.year = params.year;
    if (params?.month) queryParams.month = params.month;
    if (params?.day) queryParams.day = params.day;
    return fetchAllPages<Photograph>("/photographs/", Object.keys(queryParams).length > 0 ? queryParams : undefined);
  },

  getPhotograph: (id: number): Promise<Photograph> =>
    fetchAPI(`/photographs/${id}/`),

  // Photo Paths
  getPhotoPaths: (): Promise<PaginatedResponse<PhotoPath>> =>
    fetchAPI("/photo-paths/"),

  getAllPhotoPaths: (pathPrefix?: string): Promise<PhotoPath[]> => {
    const params = pathPrefix ? { path_prefix: pathPrefix } : undefined;
    return fetchAllPages<PhotoPath>("/photo-paths/", params);
  },

  getPhotoPath: (id: number): Promise<PhotoPath> =>
    fetchAPI(`/photo-paths/${id}/`),

  // Hashes
  getHashes: (): Promise<PaginatedResponse<Hash>> => fetchAPI("/hashes/"),

  getAllHashes: (): Promise<Hash[]> => fetchAllPages<Hash>("/hashes/"),

  getHash: (id: number): Promise<Hash> => fetchAPI(`/hashes/${id}/`),

  // Directories
  getDirectories: (): Promise<PaginatedResponse<Directory>> =>
    fetchAPI("/directories/"),

  getAllDirectories: (): Promise<Directory[]> =>
    fetchAllPages<Directory>("/directories/"),

  getDirectory: (id: number): Promise<Directory> =>
    fetchAPI(`/directories/${id}/`),

  // Dir Kinds
  getDirKinds: (): Promise<PaginatedResponse<DirKind>> =>
    fetchAPI("/dir-kinds/"),

  getAllDirKinds: (): Promise<DirKind[]> =>
    fetchAllPages<DirKind>("/dir-kinds/"),

  // Locations
  getLocations: (): Promise<PaginatedResponse<Location>> =>
    fetchAPI("/locations/"),

  getAllLocations: (): Promise<Location[]> =>
    fetchAllPages<Location>("/locations/"),

  // Time Locs
  getTimeLocs: (): Promise<PaginatedResponse<TimeLoc>> =>
    fetchAPI("/time-locs/"),

  getAllTimeLocs: (): Promise<TimeLoc[]> =>
    fetchAllPages<TimeLoc>("/time-locs/"),
};

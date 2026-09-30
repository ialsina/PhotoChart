/** API client for PhotoChart backend */

import type {
  Photograph,
  PhotoPath,
  Checksum,
  Directory,
  DirKind,
  Location,
  TimeLoc,
  Album,
  PlannedAction,
  OrganizerConfiguration,
  OrganizerJob,
  PaginatedResponse,
} from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "/api";

export interface Session {
  authenticated: boolean;
  username: string | null;
  operator: boolean;
}

function getCookie(name: string): string | undefined {
  return document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith(`${name}=`))
    ?.slice(name.length + 1);
}

async function fetchAPI<T>(endpoint: string): Promise<T> {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      credentials: "same-origin",
    });
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    return response.json();
  } catch (err) {
    if (err instanceof TypeError && err.message.includes('fetch')) {
      throw new Error(`Network error: Unable to connect to backend at ${API_BASE_URL}. Is the server running?`);
    }
    throw err;
  }
}

async function fetchAPIMethod<T>(
  endpoint: string,
  method: string,
  body?: unknown
): Promise<T> {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method,
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        ...(getCookie("csrftoken")
          ? { "X-CSRFToken": decodeURIComponent(getCookie("csrftoken")!) }
          : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    // Handle 204 No Content responses
    if (response.status === 204) {
      return undefined as T;
    }
    return response.json();
  } catch (err) {
    if (err instanceof TypeError && err.message.includes('fetch')) {
      throw new Error(`Network error: Unable to connect to backend at ${API_BASE_URL}. Is the server running?`);
    }
    throw err;
  }
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

  try {
    while (nextUrl) {
      const response = await fetch(nextUrl, { credentials: "same-origin" });
      if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
      }
      const data: PaginatedResponse<T> = await response.json();
      allItems.push(...data.results);
      nextUrl = data.next;
    }
  } catch (err) {
    if (err instanceof TypeError && err.message.includes('fetch')) {
      throw new Error(`Network error: Unable to connect to backend at ${API_BASE_URL}. Is the server running?`);
    }
    throw err;
  }

  return allItems;
}

export const api = {
  getSession: (): Promise<Session> => fetchAPI("/session/"),

  login: (username: string, password: string): Promise<Session> =>
    fetchAPIMethod<Session>("/session/login/", "POST", {
      username,
      password,
    }),

  logout: (): Promise<Session> =>
    fetchAPIMethod<Session>("/session/logout/", "POST"),

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

  getPhotographYears: (): Promise<Array<{ year: string; count: number }>> =>
    fetchAPI("/photographs/years/"),

  getPhotographMonths: (year: string): Promise<Array<{ month: string; count: number }>> =>
    fetchAPI(`/photographs/months/?year=${year}`),

  getPhotographDays: (year: string, month: string): Promise<Array<{ day: string; count: number }>> =>
    fetchAPI(`/photographs/days/?year=${year}&month=${month}`),

  getPhotograph: (id: number): Promise<Photograph> =>
    fetchAPI(`/photographs/${id}/`),

  // Photo Paths
  getPhotoPaths: (): Promise<PaginatedResponse<PhotoPath>> =>
    fetchAPI("/photo-paths/"),

  getAllPhotoPaths: (pathPrefix?: string, onlyDirect?: boolean, device?: string): Promise<PhotoPath[]> => {
    const params: Record<string, string> = {};
    if (pathPrefix) {
      params.path_prefix = pathPrefix;
    }
    if (onlyDirect) {
      params.only_direct = "true";
    }
    if (device) {
      params.device = device;
    }
    return fetchAllPages<PhotoPath>("/photo-paths/", Object.keys(params).length > 0 ? params : undefined);
  },

  getPhotoPathsPage: (pathPrefix?: string, onlyDirect?: boolean, device?: string, pageUrl?: string): Promise<PaginatedResponse<PhotoPath>> => {
    if (pageUrl) {
      // If pageUrl is provided, use it directly (it's already a full URL from the API)
      // Extract the path from the full URL
      try {
        const url = new URL(pageUrl);
        const path = url.pathname + url.search;
        return fetchAPI<PaginatedResponse<PhotoPath>>(path);
      } catch {
        // If URL parsing fails, try using it as-is (might be relative)
        return fetchAPI<PaginatedResponse<PhotoPath>>(pageUrl.startsWith('/') ? pageUrl : `/${pageUrl}`);
      }
    }

    // Build initial request URL
    const params: Record<string, string> = {};
    if (pathPrefix) {
      params.path_prefix = pathPrefix;
    }
    if (onlyDirect) {
      params.only_direct = "true";
    }
    if (device) {
      params.device = device;
    }

    const queryString = Object.keys(params).length > 0
      ? `?${new URLSearchParams(params).toString()}`
      : "";
    return fetchAPI<PaginatedResponse<PhotoPath>>(`/photo-paths/${queryString}`);
  },

  getPhotoPathDirectories: (pathPrefix?: string, device?: string): Promise<Array<{ name: string; is_directory: boolean; count: number }>> => {
    const params: Record<string, string> = {};
    if (pathPrefix) {
      params.path_prefix = pathPrefix;
    }
    if (device) {
      params.device = device;
    }
    const queryString = Object.keys(params).length > 0
      ? `?${new URLSearchParams(params).toString()}`
      : "";
    return fetchAPI(`/photo-paths/directories/${queryString}`);
  },

  getPhotoPathDevices: (): Promise<Array<{ device: string; count: number }>> => {
    return fetchAPI("/photo-paths/devices/");
  },

  getPhotoPathCount: (pathPrefix?: string, onlyDirect?: boolean, device?: string): Promise<{ count: number }> => {
    const params: Record<string, string> = {};
    if (pathPrefix) {
      params.path_prefix = pathPrefix;
    }
    if (onlyDirect) {
      params.only_direct = "true";
    }
    if (device) {
      params.device = device;
    }
    const queryString = Object.keys(params).length > 0
      ? `?${new URLSearchParams(params).toString()}`
      : "";
    return fetchAPI(`/photo-paths/count/${queryString}`);
  },

  getPhotoPath: (id: number): Promise<PhotoPath> =>
    fetchAPI(`/photo-paths/${id}/`),

  // Checksums
  getChecksums: (): Promise<PaginatedResponse<Checksum>> => fetchAPI("/checksums/"),

  getAllChecksums: (): Promise<Checksum[]> => fetchAllPages<Checksum>("/checksums/"),

  getChecksum: (id: number): Promise<Checksum> => fetchAPI(`/checksums/${id}/`),

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

  // Albums
  getAlbums: (): Promise<PaginatedResponse<Album>> =>
    fetchAPI("/albums/"),

  getAllAlbums: (): Promise<Album[]> =>
    fetchAllPages<Album>("/albums/"),

  getAlbum: (id: number): Promise<Album> =>
    fetchAPI(`/albums/${id}/`),

  createAlbum: (data: { name: string; description?: string }): Promise<Album> =>
    fetchAPIMethod<Album>("/albums/", "POST", data),

  updateAlbum: (
    id: number,
    data: { name?: string; description?: string }
  ): Promise<Album> =>
    fetchAPIMethod<Album>(`/albums/${id}/`, "PATCH", data),

  deleteAlbum: (id: number): Promise<void> =>
    fetchAPIMethod<void>(`/albums/${id}/`, "DELETE"),

  // Album photo management
  addPhotosToAlbum: (albumId: number, photoIds: number[]): Promise<{ status: string; added_count: number }> =>
    fetchAPIMethod<{ status: string; added_count: number }>(`/albums/${albumId}/add_photos/`, "POST", { photo_ids: photoIds }),

  removePhotosFromAlbum: (albumId: number, photoIds: number[]): Promise<{ status: string; removed_count: number }> =>
    fetchAPIMethod<{ status: string; removed_count: number }>(`/albums/${albumId}/remove_photos/`, "POST", { photo_ids: photoIds }),

  // Planned Actions
  createPlannedAction: (data: { action_type: string; photograph: number }): Promise<PlannedAction> =>
    fetchAPIMethod<PlannedAction>("/planned-actions/", "POST", data),

  getOrganizerConfigurations: (): Promise<OrganizerConfiguration[]> =>
    fetchAllPages<OrganizerConfiguration>("/organizer-configurations/"),

  getOrganizerJobs: (): Promise<OrganizerJob[]> =>
    fetchAllPages<OrganizerJob>("/organizer-jobs/"),

  runOrganizer: (configurationId: number, dryRun = true): Promise<OrganizerJob> =>
    fetchAPIMethod<OrganizerJob>(
      `/organizer-configurations/${configurationId}/run/`,
      "POST",
      { dry_run: dryRun }
    ),

  retryOrganizerJob: (jobId: number): Promise<OrganizerJob> =>
    fetchAPIMethod<OrganizerJob>(`/organizer-jobs/${jobId}/retry/`, "POST"),
};

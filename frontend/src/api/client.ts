import type {
  InvitationConfig,
  RSVPApiResult,
  RSVPAdminItem,
  RSVPListResponse,
  RSVPRequest,
  RSVPUpdateRequest,
} from "../types/config";

const BASE_API = "/birthday/api";

export async function fetchConfig(): Promise<InvitationConfig> {
  const res = await fetch(`${BASE_API}/config`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to load config: HTTP ${res.status}`);
  }
  return res.json();
}

export async function submitRsvp(data: RSVPRequest): Promise<RSVPApiResult> {
  try {
    const res = await fetch(`${BASE_API}/rsvp`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(data),
    });

    const json = await res.json();
    return json as RSVPApiResult;
  } catch {
    return { result: "ERROR" };
  }
}

export async function fetchAdminRsvps(search?: string): Promise<RSVPListResponse> {
  const url = new URL(`${BASE_API}/admin/rsvps`, window.location.origin);
  if (search?.trim()) {
    url.searchParams.set("search", search.trim());
  }

  const res = await fetch(url.toString(), {
    headers: { Accept: "application/json" },
  });

  if (!res.ok) {
    throw new Error(`Error fetching admin RSVPs: HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchAdminConfig(): Promise<InvitationConfig> {
  const res = await fetch(`${BASE_API}/admin/config`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Error fetching admin config: HTTP ${res.status}`);
  }
  return res.json();
}

export async function updateAdminConfig(
  config: Omit<InvitationConfig, "id" | "updated_at">,
): Promise<InvitationConfig> {
  const res = await fetch(`${BASE_API}/admin/config`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(config),
  });

  if (!res.ok) {
    const errorJson = await res.json().catch(() => null);
    const msg = errorJson?.errors
      ? Object.values(errorJson.errors).join(", ")
      : `HTTP ${res.status}`;
    throw new Error(`Error saving configuration: ${msg}`);
  }
  return res.json();
}

export function getExportCsvUrl(): string {
  return `${BASE_API}/admin/export`;
}

export interface GenerateMapPreviewResponse {
  map_preview_url: string;
  lat: number;
  lng: number;
  message: string;
}

export async function regenerateMapPreview(
  mapUrl?: string,
): Promise<GenerateMapPreviewResponse> {
  const res = await fetch(`${BASE_API}/admin/map-preview/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ map_url: mapUrl }),
  });

  if (!res.ok) {
    const errorJson = await res.json().catch(() => null);
    const msg =
      errorJson?.detail ||
      (errorJson?.errors
        ? Object.values(errorJson.errors).join(", ")
        : `HTTP ${res.status}`);
    throw new Error(msg || "Error al regenerar vista previa del mapa.");
  }
  return res.json();
}

export async function deleteAdminRsvp(rsvpId: number): Promise<void> {
  const res = await fetch(`${BASE_API}/admin/rsvps/${rsvpId}`, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });

  if (!res.ok && res.status !== 204) {
    const errorJson = await res.json().catch(() => null);
    const msg = errorJson?.detail || `HTTP ${res.status}`;
    throw new Error(`Error al eliminar asistente: ${msg}`);
  }
}

export async function updateAdminRsvp(
  rsvpId: number,
  data: RSVPUpdateRequest,
): Promise<RSVPAdminItem> {
  const res = await fetch(`${BASE_API}/admin/rsvps/${rsvpId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    const errorJson = await res.json().catch(() => null);
    const msg =
      errorJson?.detail ||
      (errorJson?.errors
        ? Object.values(errorJson.errors).join(", ")
        : `HTTP ${res.status}`);
    throw new Error(msg || "Error al actualizar asistente.");
  }
  return res.json();
}

export interface CurrentUser {
  subject: string;
  email: string;
  name: string | null;
  groups: string[];
}

export async function fetchCurrentUser(): Promise<CurrentUser> {
  const res = await fetch(`${BASE_API}/auth/me`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Unauthenticated: HTTP ${res.status}`);
  }
  return res.json();
}

export async function logoutUser(): Promise<void> {
  await fetch(`${BASE_API}/auth/logout`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
}


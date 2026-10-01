import type {
  InvitationConfig,
  RSVPApiResult,
  RSVPListResponse,
  RSVPRequest,
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

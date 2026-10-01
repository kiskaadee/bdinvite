export interface InvitationConfig {
  id: number;
  title: string;
  invitation_text: string;
  honoree_name: string;
  event_date: string; // "YYYY-MM-DD"
  event_time: string; // "HH:MM"
  event_timezone: string; // "America/Bogota"
  address_name: string;
  address_lines: string;
  map_preview_url: string;
  map_url: string;
  rsvp_heading: string;
  rsvp_cta: string;
  submit_label: string;
  msg_success: string;
  msg_success_greeting: string;
  msg_duplicate: string;
  msg_error: string;
  msg_config_error: string;
  countdown_label: string;
  countdown_in_progress: string;
  countdown_finished: string;
  updated_at?: string;
}

export interface RSVPRequest {
  name: string;
  phone: string;
  email?: string | null;
}

export interface RSVPUpdateRequest {
  name?: string;
  phone?: string;
  email?: string | null;
}


export type RSVPApiResult =
  | { result: "SUCCESS"; name: string }
  | { result: "DUPLICATE" }
  | { result: "VALIDATION_ERROR"; errors: Record<string, string> }
  | { result: "ERROR" };

export interface RSVPAdminItem {
  id: number;
  name: string;
  phone: string;
  email: string | null;
  created_at: string;
}

export interface RSVPListResponse {
  count: number;
  rsvps: RSVPAdminItem[];
}

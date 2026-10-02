export type Coordinates = { lat: number; lon: number };

export type LocationValue = {
  label: string;
  coordinates: Coordinates;
  region?: string | null;
  locality?: string | null;
  country_code?: string;
};

export type ApiError = {
  code: string;
  message: string;
  field_errors?: Record<string, string[]>;
  retryable?: boolean;
  request_id?: string;
};

export type TripPlan = {
  id: string;
  created_at: string;
  access_token?: string;
  schema_version: string;
  rule_version: string;
  input: Record<string, unknown>;
  route: {
    legs: Array<{
      leg_id: string;
      from_label: string;
      to_label: string;
      distance_m: number;
      duration_s: number;
      geometry: [number, number][];
      steps: Array<{
        distance_m: number;
        duration_s: number;
        instruction: string;
        geometry: [number, number][];
      }>;
      provider: string;
      profile: string;
    }>;
    profile: string;
    note: string;
  };
  timeline: TimelineEvent[];
  daily_logs: DailyLog[];
  diagnostics: Record<string, unknown>;
  validation: {
    ok: boolean;
    errors: string[];
    warnings: string[];
    label: string;
  };
  assumptions: Record<string, unknown>;
  map: { tile_url: string; attribution: string };
  provider: Record<string, unknown>;
};

export type TimelineEvent = {
  event_id: string;
  event_type: string;
  status: "OFF" | "SB" | "D" | "ON";
  start_utc: string;
  end_utc: string;
  duration_s: number;
  reason_codes: string[];
  clocks_at_start: ClockSnapshot;
  clocks_at_end: ClockSnapshot;
  start_progress_m: number;
  end_progress_m: number;
  distance_m: number;
  start_coord: Coordinates | null;
  end_coord: Coordinates | null;
  location_label: string | null;
  location_provenance: string | null;
  leg_id: string | null;
  explanation: string;
};

export type ClockSnapshot = {
  shift_driving_s: number;
  shift_elapsed_s: number;
  driving_since_break_s: number;
  cycle_used_s: number;
  miles_since_fuel_m: number;
  continuous_rest_s: number;
};

export type DailyLog = {
  date_local: string;
  from_label: string;
  to_label: string;
  timezone: string;
  utc_offset: string;
  driving_miles: number;
  total_miles: number;
  segments: Array<{
    status: "OFF" | "SB" | "D" | "ON";
    start_s: number;
    end_s: number;
    event_id: string;
    is_planning_filler: boolean;
  }>;
  totals_s: Record<string, number>;
  remarks: Array<{
    time_local: string;
    text: string;
    location_label: string | null;
    event_id: string | null;
    estimated: boolean;
  }>;
  recap: Record<string, unknown>;
  page_number: number;
  total_pages: number;
  carrier_name?: string | null;
  main_office?: string | null;
  home_terminal?: string | null;
  tractor_trailer?: string | null;
  driver_name?: string | null;
  co_driver?: string | null;
  shipping_document?: string | null;
  shipper_commodity?: string | null;
  planned_banner: string;
  signature: null;
};

export class ApiRequestError extends Error {
  body: ApiError;
  status: number;
  constructor(status: number, body: ApiError) {
    super(body.message);
    this.status = status;
    this.body = body;
  }
}

async function parseError(res: Response): Promise<ApiError> {
  try {
    return (await res.json()) as ApiError;
  } catch {
    return {
      code: "NETWORK_ERROR",
      message: res.statusText || "Request failed",
      retryable: true,
    };
  }
}

export async function searchLocations(q: string, signal?: AbortSignal) {
  const res = await fetch(`/api/locations/search/?q=${encodeURIComponent(q)}`, {
    signal,
  });
  if (!res.ok) throw new ApiRequestError(res.status, await parseError(res));
  return (await res.json()) as {
    results: Array<LocationValue & { confidence: number }>;
  };
}

export async function createTrip(payload: Record<string, unknown>) {
  const res = await fetch("/api/trips/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new ApiRequestError(res.status, await parseError(res));
  return (await res.json()) as TripPlan;
}

export async function getTrip(id: string, token: string) {
  const res = await fetch(`/api/trips/${id}/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new ApiRequestError(res.status, await parseError(res));
  return (await res.json()) as TripPlan;
}

export function storeTripAccess(id: string, token: string) {
  sessionStorage.setItem(`trip:${id}:token`, token);
}

export function loadTripAccess(id: string): string | null {
  return sessionStorage.getItem(`trip:${id}:token`);
}

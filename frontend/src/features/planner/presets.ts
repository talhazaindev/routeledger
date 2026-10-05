import { DateTime } from "luxon";
import type { LocationValue } from "../../api/client";

export type PlannerFormState = {
  current: LocationValue | null;
  pickup: LocationValue | null;
  dropoff: LocationValue | null;
  cycleUsedHours: string;
  departureLocal: string;
  homeTerminalTz: string;
  milesSinceFuel: string;
  fuelDurationMinutes: string;
  includePretrip: boolean;
  restStatus: "OFF" | "SB";
  sleeperEquipped: boolean;
  splitSleeper: boolean;
  /** Oldest-first daily on-duty hours for rolling 8-day mode; empty = conservative. */
  cycleDailyHistoryHours: string;
  driverName: string;
  carrierName: string;
  mainOffice: string;
  homeTerminal: string;
  tractorTrailer: string;
  coDriver: string;
  shippingDocument: string;
  shipperCommodity: string;
};

export function defaultFormState(): PlannerFormState {
  const tz = "America/Chicago";
  const tomorrow = DateTime.now().setZone(tz).plus({ days: 1 }).startOf("day").set({ hour: 8 });
  return {
    current: null,
    pickup: null,
    dropoff: null,
    cycleUsedHours: "0",
    departureLocal: tomorrow.toISO({ suppressMilliseconds: true, includeOffset: true }) || "",
    homeTerminalTz: tz,
    milesSinceFuel: "0",
    fuelDurationMinutes: "30",
    includePretrip: false,
    restStatus: "OFF",
    sleeperEquipped: false,
    splitSleeper: false,
    cycleDailyHistoryHours: "",
    driverName: "",
    carrierName: "",
    mainOffice: "",
    homeTerminal: "",
    tractorTrailer: "",
    coDriver: "",
    shippingDocument: "",
    shipperCommodity: "",
  };
}

export const PRESETS: Array<{ id: string; label: string; description: string; apply: () => Partial<PlannerFormState> }> = [
  {
    id: "short",
    label: "Short route",
    description: "Chicago → Joliet → Bloomington, cycle 0",
    apply: () => ({
      current: {
        label: "Chicago, Illinois, United States",
        coordinates: { lat: 41.8781, lon: -87.6298 },
        region: "IL",
        country_code: "US",
      },
      pickup: {
        label: "Joliet, Illinois, United States",
        coordinates: { lat: 41.525, lon: -88.0817 },
        region: "IL",
        country_code: "US",
      },
      dropoff: {
        label: "Bloomington, Illinois, United States",
        coordinates: { lat: 40.4842, lon: -88.9937 },
        region: "IL",
        country_code: "US",
      },
      cycleUsedHours: "0",
    }),
  },
  {
    id: "multiday",
    label: "Multi-day route",
    description: "Chicago → Denver via Kansas City pickup",
    apply: () => ({
      current: {
        label: "Chicago, Illinois, United States",
        coordinates: { lat: 41.8781, lon: -87.6298 },
        region: "IL",
        country_code: "US",
      },
      pickup: {
        label: "Kansas City, Missouri, United States",
        coordinates: { lat: 39.0997, lon: -94.5786 },
        region: "MO",
        country_code: "US",
      },
      dropoff: {
        label: "Denver, Colorado, United States",
        coordinates: { lat: 39.7392, lon: -104.9903 },
        region: "CO",
        country_code: "US",
      },
      cycleUsedHours: "10",
    }),
  },
  {
    id: "near-cycle",
    label: "Near-exhausted cycle",
    description: "Chicago → Indianapolis, cycle 68",
    apply: () => ({
      current: {
        label: "Chicago, Illinois, United States",
        coordinates: { lat: 41.8781, lon: -87.6298 },
        region: "IL",
        country_code: "US",
      },
      pickup: {
        label: "Chicago, Illinois, United States",
        coordinates: { lat: 41.8781, lon: -87.6298 },
        region: "IL",
        country_code: "US",
      },
      dropoff: {
        label: "Indianapolis, Indiana, United States",
        coordinates: { lat: 39.7684, lon: -86.1581 },
        region: "IN",
        country_code: "US",
      },
      cycleUsedHours: "68",
    }),
  },
];

export function formToPayload(form: PlannerFormState) {
  const historyRaw = form.cycleDailyHistoryHours.trim();
  const history = historyRaw
    ? historyRaw.split(/[,\s]+/).filter(Boolean).map((v) => Number(v))
    : null;
  return {
    current_location: form.current,
    pickup_location: form.pickup,
    dropoff_location: form.dropoff,
    cycle_used_hours: form.cycleUsedHours,
    departure_local: form.departureLocal,
    home_terminal_tz: form.homeTerminalTz,
    miles_since_fuel: Number(form.milesSinceFuel),
    fuel_duration_minutes: Number(form.fuelDurationMinutes),
    include_pretrip_inspection: form.includePretrip,
    rest_status: form.restStatus,
    sleeper_equipped: form.sleeperEquipped,
    split_sleeper: form.splitSleeper,
    cycle_daily_history_hours: history,
    driver_name: form.driverName || null,
    carrier_name: form.carrierName || null,
    main_office: form.mainOffice || null,
    home_terminal: form.homeTerminal || null,
    tractor_trailer: form.tractorTrailer || null,
    co_driver: form.coDriver || null,
    shipping_document: form.shippingDocument || null,
    shipper_commodity: form.shipperCommodity || null,
  };
}

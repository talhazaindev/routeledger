import { useMemo, useState } from "react";
import { DateTime } from "luxon";
import {
  ChevronDown,
  Download,
  Loader2,
  Map as MapIcon,
  PanelLeftClose,
  PanelLeftOpen,
  Printer,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  ApiRequestError,
  createTrip,
  storeTripAccess,
  type TripPlan,
} from "../../api/client";
import { cn, formatDuration, metersToMiles } from "../../lib/utils";
import { LocationCombobox } from "./LocationCombobox";
import {
  PRESETS,
  defaultFormState,
  formToPayload,
  type PlannerFormState,
} from "./presets";
import { TripMap } from "../map/TripMap";
import { TripTimelineScrubber } from "../map/TripTimelineScrubber";
import { ItineraryPanel } from "../itinerary/ItineraryPanel";
import { DailyLogSheet } from "../logs/DailyLogSheet";
import { downloadLogsPdf } from "../logs/exportPdf";
import { AppHeader } from "../../components/AppHeader";
import { BrandEmptyState } from "../../components/BrandEmptyState";
import { RouteSpine } from "../../components/RouteSpine";

type Tab = "itinerary" | "directions" | "logs" | "insights";

const TABS: Array<[Tab, string]> = [
  ["itinerary", "Itinerary"],
  ["directions", "Directions"],
  ["logs", "Daily logs"],
  ["insights", "Plan insights"],
];

export function PlannerPage() {
  const reduce = useReducedMotion();
  const [form, setForm] = useState<PlannerFormState>(defaultFormState);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [plan, setPlan] = useState<TripPlan | null>(null);
  const [planFingerprint, setPlanFingerprint] = useState("");
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [selectedDayIndex, setSelectedDayIndex] = useState(0);
  const [tab, setTab] = useState<Tab>("itinerary");
  const [mobileView, setMobileView] = useState<"overview" | "map" | "logs">("overview");
  const [mapFocus, setMapFocus] = useState(false);
  const [dayFilterAll, setDayFilterAll] = useState(true);

  const currentFingerprint = useMemo(() => JSON.stringify(formToPayload(form)), [form]);
  const stale = !!plan && planFingerprint !== currentFingerprint;

  function patch(p: Partial<PlannerFormState>) {
    setForm((f) => ({ ...f, ...p }));
  }

  async function generate() {
    setError(null);
    setFieldErrors({});
    const errs: Record<string, string> = {};
    if (!form.current) errs.current = "Select a current location from search results";
    if (!form.pickup) errs.pickup = "Select a pickup location from search results";
    if (!form.dropoff) errs.dropoff = "Select a dropoff location from search results";
    const cycle = Number(form.cycleUsedHours);
    if (form.cycleUsedHours === "" || !Number.isFinite(cycle) || cycle < 0 || cycle > 70) {
      errs.cycle = "Enter a finite value from 0 through 70";
    }
    if (Object.keys(errs).length) {
      setFieldErrors(errs);
      setError("Fix the highlighted fields, then try again.");
      return;
    }
    setLoading(true);
    setStage("Finding route and building schedule…");
    try {
      const result = await createTrip(formToPayload(form));
      if (result.access_token) storeTripAccess(result.id, result.access_token);
      setPlan(result);
      setPlanFingerprint(currentFingerprint);
      setSelectedEventId(result.timeline[0]?.event_id ?? null);
      setSelectedDayIndex(0);
      setTab("itinerary");
      setMobileView("overview");
      setDayFilterAll(true);
      setMapFocus(false);
    } catch (e) {
      if (e instanceof ApiRequestError) {
        setError(e.body.message);
        const fe: Record<string, string> = {};
        for (const [k, v] of Object.entries(e.body.field_errors || {})) {
          fe[k] = Array.isArray(v) ? v.join(", ") : String(v);
        }
        setFieldErrors(fe);
      } else {
        setError("Network failure. Check that the API is reachable, then retry.");
      }
    } finally {
      setLoading(false);
      setStage("");
    }
  }

  function applyPreset(id: string) {
    const preset = PRESETS.find((p) => p.id === id);
    if (!preset) return;
    setForm((f) => ({ ...f, ...preset.apply() }));
  }

  const summary = useMemo(() => {
    if (!plan) return null;
    const distance = plan.route.legs.reduce((s, l) => s + l.distance_m, 0);
    const driving = Number(plan.diagnostics.total_driving_s || 0);
    const first = plan.timeline[0];
    const last = plan.timeline[plan.timeline.length - 1];
    const elapsed =
      first && last
        ? (DateTime.fromISO(last.end_utc).toMillis() - DateTime.fromISO(first.start_utc).toMillis()) / 1000
        : 0;
    const dropoff = plan.timeline.find((e) => e.event_type === "DROPOFF");
    return { distance, driving, elapsed, dropoff, last };
  }, [plan]);

  const selectedEvent = plan?.timeline.find((e) => e.event_id === selectedEventId) || null;
  const homeTz = form.homeTerminalTz;
  const remainingCycle = Math.max(0, 70 - (Number(form.cycleUsedHours) || 0)).toFixed(2);

  function selectEvent(id: string, fromPlan: TripPlan = plan!) {
    setSelectedEventId(id);
    const ev = fromPlan.timeline.find((e) => e.event_id === id);
    if (ev) {
      const day = DateTime.fromISO(ev.start_utc).setZone(homeTz).toISODate();
      const idx = fromPlan.daily_logs.findIndex((d) => d.date_local === day);
      if (idx >= 0) {
        setSelectedDayIndex(idx);
        setDayFilterAll(false);
      }
    }
  }

  const activeDay = dayFilterAll ? null : plan?.daily_logs[selectedDayIndex]?.date_local || null;

  return (
    <div className="min-h-screen overflow-x-hidden text-text">
      <AppHeader
        hasPlan={!!plan}
        onLogsClick={() => {
          setTab("logs");
          setMobileView("logs");
        }}
      />

      <main
        className={cn(
          "mx-auto grid max-w-[1440px] gap-5 overflow-x-hidden px-4 py-5 sm:px-6 lg:items-start",
          mapFocus
            ? "lg:grid-cols-1"
            : "lg:grid-cols-[340px_minmax(0,1fr)] xl:grid-cols-[360px_minmax(0,1fr)]",
        )}
      >
        <motion.aside
          className={cn(
            "no-print space-y-4 lg:sticky lg:top-[4.75rem] lg:max-h-[calc(100vh-5.25rem)] lg:overflow-y-auto lg:pr-1",
            mapFocus && "hidden",
          )}
          initial={reduce ? false : { opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: 0.05, ease: [0.22, 1, 0.36, 1] }}
        >
          <section className="panel p-5">
            <div className="mb-5">
              <h1 className="font-display text-xl font-semibold tracking-tight text-ink">Plan a trip</h1>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">
                Enter locations and cycle hours. Returns a routed map, stops, and planned daily logs.
              </p>
            </div>

            <RouteSpine
              items={[
                {
                  number: 1,
                  children: (
                    <LocationCombobox
                      id="current"
                      hideNumber
                      label="Current location"
                      value={form.current}
                      onChange={(v) => patch({ current: v })}
                      error={fieldErrors.current || fieldErrors.current_location}
                    />
                  ),
                },
                {
                  number: 2,
                  children: (
                    <LocationCombobox
                      id="pickup"
                      hideNumber
                      label="Pickup location"
                      value={form.pickup}
                      onChange={(v) => patch({ pickup: v })}
                      error={fieldErrors.pickup || fieldErrors.pickup_location}
                    />
                  ),
                },
                {
                  number: 3,
                  children: (
                    <LocationCombobox
                      id="dropoff"
                      hideNumber
                      label="Dropoff location"
                      value={form.dropoff}
                      onChange={(v) => patch({ dropoff: v })}
                      error={fieldErrors.dropoff || fieldErrors.dropoff_location}
                    />
                  ),
                },
              ]}
            />

            <div className="mt-2 border-t border-border pt-4">
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <label htmlFor="cycle" className="text-sm font-medium">
                  4. Current Cycle Used (Hrs)
                </label>
                <span className="rounded-full bg-action/10 px-2.5 py-0.5 text-[11px] font-semibold text-action">
                  {remainingCycle}h left
                </span>
              </div>
              <input
                id="cycle"
                type="number"
                min={0}
                max={70}
                step="0.01"
                value={form.cycleUsedHours}
                onChange={(e) => patch({ cycleUsedHours: e.target.value })}
                className="w-full rounded-xl border border-border bg-surface px-3 py-2.5 text-sm outline-none transition focus:border-action focus:ring-2 focus:ring-action/15"
                aria-invalid={!!fieldErrors.cycle}
              />
              <p className="mt-1.5 text-xs leading-relaxed text-muted">
                Total on-duty time already used in your current 8-day cycle, including driving.
              </p>
              {fieldErrors.cycle && <p className="mt-1 text-xs text-red-600">{fieldErrors.cycle}</p>}
            </div>

            <div
              id="assumptions"
              className="mt-4 rounded-xl border border-border/80 bg-surface-elevated px-3 py-2.5 text-[11px] leading-relaxed text-muted"
            >
              Property-carrying · 70h/8d · fuel ≥ every 1,000 mi · pickup/dropoff 1h each · fresh shift at
              departure · Conservative cycle estimate · not a certified ELD
            </div>

            <button
              type="button"
              className="mt-3 flex w-full items-center justify-between rounded-xl border border-border bg-surface px-3 py-2.5 text-sm font-medium transition hover:bg-surface-elevated"
              onClick={() => setSettingsOpen((o) => !o)}
              aria-expanded={settingsOpen}
            >
              Planning settings
              <ChevronDown className={cn("h-4 w-4 text-muted transition", settingsOpen && "rotate-180")} />
            </button>
            <AnimatePresence initial={false}>
              {settingsOpen && (
                <motion.div
                  key="settings"
                  initial={reduce ? false : { height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={reduce ? undefined : { height: 0, opacity: 0 }}
                  transition={{ duration: 0.25 }}
                  className="overflow-hidden"
                >
                  <div className="mt-3 space-y-3 border-t border-border pt-3 text-sm">
                    <div>
                      <label htmlFor="departure" className="font-medium">
                        Departure date and time
                      </label>
                      <input
                        id="departure"
                        type="datetime-local"
                        className="mt-1 w-full rounded-xl border border-border px-3 py-2"
                        value={DateTime.fromISO(form.departureLocal).toFormat("yyyy-LL-dd'T'HH:mm")}
                        onChange={(e) => {
                          const dt = DateTime.fromISO(e.target.value, { zone: form.homeTerminalTz });
                          patch({
                            departureLocal:
                              dt.toISO({ suppressMilliseconds: true, includeOffset: true }) || "",
                          });
                        }}
                      />
                    </div>
                    <div>
                      <label htmlFor="tz" className="font-medium">
                        Home-terminal timezone
                      </label>
                      <select
                        id="tz"
                        className="mt-1 w-full rounded-xl border border-border px-3 py-2"
                        value={form.homeTerminalTz}
                        onChange={(e) => patch({ homeTerminalTz: e.target.value })}
                      >
                        {[
                          "America/Chicago",
                          "America/New_York",
                          "America/Denver",
                          "America/Los_Angeles",
                          "America/Phoenix",
                        ].map((z) => (
                          <option key={z} value={z}>
                            {z}
                          </option>
                        ))}
                      </select>
                      <p className="mt-1 text-xs text-muted">All log times use this zone, not the browser zone.</p>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <label className="text-xs">
                        Miles since fuel
                        <input
                          type="number"
                          min={0}
                          max={1000}
                          className="mt-1 w-full rounded-xl border border-border px-2 py-2"
                          value={form.milesSinceFuel}
                          onChange={(e) => patch({ milesSinceFuel: e.target.value })}
                        />
                      </label>
                      <label className="text-xs">
                        Fuel stop (min)
                        <input
                          type="number"
                          min={1}
                          className="mt-1 w-full rounded-xl border border-border px-2 py-2"
                          value={form.fuelDurationMinutes}
                          onChange={(e) => patch({ fuelDurationMinutes: e.target.value })}
                        />
                      </label>
                    </div>
                    <label className="flex items-center gap-2 text-xs">
                      <input
                        type="checkbox"
                        checked={form.includePretrip}
                        onChange={(e) => patch({ includePretrip: e.target.checked })}
                      />
                      Optional 15-minute pre-trip inspection
                    </label>
                    <label className="flex items-center gap-2 text-xs">
                      <input
                        type="checkbox"
                        checked={form.sleeperEquipped}
                        onChange={(e) =>
                          patch({
                            sleeperEquipped: e.target.checked,
                            restStatus: e.target.checked ? form.restStatus : "OFF",
                            splitSleeper: e.target.checked ? form.splitSleeper : false,
                          })
                        }
                      />
                      Equipped sleeper berth
                    </label>
                    <label className="text-xs">
                      Rest status
                      <select
                        className="mt-1 w-full rounded-xl border border-border px-2 py-2"
                        value={form.restStatus}
                        disabled={!form.sleeperEquipped}
                        onChange={(e) =>
                          patch({
                            restStatus: e.target.value as "OFF" | "SB",
                            splitSleeper:
                              e.target.value === "SB" ? form.splitSleeper : false,
                          })
                        }
                      >
                        <option value="OFF">OFF</option>
                        <option value="SB">SB</option>
                      </select>
                    </label>
                    <label className="flex items-center gap-2 text-xs">
                      <input
                        type="checkbox"
                        checked={form.splitSleeper}
                        disabled={!form.sleeperEquipped || form.restStatus !== "SB"}
                        onChange={(e) => patch({ splitSleeper: e.target.checked })}
                      />
                      Split sleeper (7h SB + 3h companion per §395.1(g))
                    </label>
                    <label className="text-xs">
                      Cycle daily history (hours, oldest→newest, optional)
                      <input
                        className="mt-1 w-full rounded-xl border border-border px-2 py-2"
                        placeholder="e.g. 10,10,10,10,10,8,5,2"
                        value={form.cycleDailyHistoryHours}
                        onChange={(e) => patch({ cycleDailyHistoryHours: e.target.value })}
                      />
                      <p className="mt-1 text-xs text-muted">
                        1–8 values that sum to Current Cycle Used. Enables rolling 8-day
                        drop-off; leave blank for conservative estimate.
                      </p>
                    </label>
                    <div className="grid gap-2">
                      {(
                        [
                          ["driverName", "Driver"],
                          ["carrierName", "Carrier"],
                          ["mainOffice", "Main office"],
                          ["homeTerminal", "Home terminal"],
                          ["tractorTrailer", "Tractor / trailer"],
                          ["coDriver", "Co-driver"],
                          ["shippingDocument", "Shipping document"],
                          ["shipperCommodity", "Shipper / commodity"],
                        ] as const
                      ).map(([key, label]) => (
                        <label key={key} className="text-xs">
                          {label}
                          <input
                            className="mt-1 w-full rounded-xl border border-border px-2 py-2"
                            value={form[key]}
                            onChange={(e) => patch({ [key]: e.target.value })}
                          />
                        </label>
                      ))}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <motion.button
              type="button"
              onClick={generate}
              disabled={loading}
              whileTap={reduce ? undefined : { scale: 0.985 }}
              className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-action px-4 py-3.5 text-sm font-semibold text-white shadow-[0_8px_20px_rgba(15,118,110,0.28)] transition hover:bg-action-hover disabled:opacity-60"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <MapIcon className="h-4 w-4" />}
              Generate trip plan
            </motion.button>
            <div aria-live="polite" className="mt-2 min-h-[1.25rem] text-xs text-muted">
              {stage}
            </div>
            {error && (
              <div
                role="alert"
                className="mt-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800"
              >
                {error}
                <div className="mt-2 flex gap-2">
                  <button
                    type="button"
                    className="rounded-lg border border-red-300 px-2 py-1 text-xs"
                    onClick={generate}
                  >
                    Retry
                  </button>
                </div>
              </div>
            )}
          </section>

          <section className="panel p-4">
            <div className="mb-3 font-display text-sm font-semibold text-ink">Sample trips</div>
            <div className="space-y-2">
              {PRESETS.map((p) => (
                <motion.button
                  key={p.id}
                  type="button"
                  onClick={() => applyPreset(p.id)}
                  whileHover={reduce ? undefined : { y: -1 }}
                  className="w-full rounded-xl border border-border bg-surface-elevated/60 px-3 py-2.5 text-left transition hover:border-action/40 hover:bg-white hover:shadow-sm"
                >
                  <div className="text-sm font-medium">{p.label}</div>
                  <div className="mt-0.5 text-xs leading-relaxed text-muted">{p.description}</div>
                </motion.button>
              ))}
            </div>
          </section>
        </motion.aside>

        <section className="min-w-0 space-y-4">
          <AnimatePresence mode="wait">
            {!plan && !loading && (
              <motion.div
                key="empty"
                initial={reduce ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={reduce ? undefined : { opacity: 0 }}
              >
                <BrandEmptyState />
              </motion.div>
            )}

            {loading && !plan && (
              <motion.div
                key="loading"
                initial={reduce ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduce ? undefined : { opacity: 0 }}
                className="panel flex min-h-[280px] flex-col items-center justify-center px-6 py-12 text-center"
              >
                <Loader2 className="mb-3 h-8 w-8 animate-spin text-action" aria-hidden />
                <p className="font-display text-lg font-semibold text-ink">
                  {stage || "Building trip plan…"}
                </p>
              </motion.div>
            )}

            {plan && (
              <motion.div
                key="results"
                initial={reduce ? false : { opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                className="space-y-4"
              >
                {stale && (
                  <div
                    role="status"
                    className="no-print rounded-xl border border-amber-300 bg-amber-50 px-3.5 py-2.5 text-sm text-amber-900"
                  >
                    Inputs changed — regenerate. Export is disabled until you recalculate.
                  </div>
                )}

                <div className="no-print grid grid-cols-3 gap-1 rounded-2xl border border-border bg-surface p-1 shadow-sm md:hidden">
                  {(["overview", "map", "logs"] as const).map((v) => (
                    <button
                      key={v}
                      type="button"
                      onClick={() => setMobileView(v)}
                      className={cn(
                        "rounded-xl px-2 py-2 text-sm font-medium capitalize transition",
                        mobileView === v ? "bg-action text-white shadow-sm" : "text-muted hover:text-text",
                      )}
                    >
                      {v}
                    </button>
                  ))}
                </div>

                <div
                  className={cn(
                    "panel overflow-hidden",
                    mobileView !== "overview" && "max-md:hidden",
                  )}
                >
                  <div className="grid gap-0 sm:grid-cols-[1.15fr_repeat(5,minmax(0,1fr))]">
                    <div className="border-b border-border bg-gradient-to-br from-ink to-[#1a3350] p-4 text-white sm:border-b-0 sm:border-r">
                      <div className="text-[11px] font-medium uppercase tracking-[0.06em] text-white/65">
                        Distance
                      </div>
                      <div className="font-display mt-1 text-3xl font-semibold tracking-tight">
                        {metersToMiles(summary!.distance).toFixed(1)}
                        <span className="ml-1 text-base font-medium text-white/70">mi</span>
                      </div>
                    </div>
                    <Stat label="Driving time" value={formatDuration(summary!.driving)} />
                    <Stat label="Elapsed trip" value={formatDuration(summary!.elapsed)} />
                    <Stat
                      label="Arrival at dropoff"
                      value={
                        summary!.dropoff
                          ? DateTime.fromISO(summary!.dropoff.start_utc)
                              .setZone(homeTz)
                              .toFormat("ccc LLL d, HH:mm")
                          : "—"
                      }
                    />
                    <Stat
                      label="Completion"
                      value={
                        summary!.last
                          ? DateTime.fromISO(summary!.last.end_utc)
                              .setZone(homeTz)
                              .toFormat("ccc LLL d, HH:mm")
                          : "—"
                      }
                    />
                    <Stat label="Log days" value={String(plan.daily_logs.length)} last />
                  </div>
                  <div className="flex flex-wrap items-center gap-2 border-t border-border px-4 py-3 text-xs">
                    <span className="rounded-md bg-action/10 px-2 py-1 font-medium text-action">
                      {plan.validation.label}
                    </span>
                    <span className="text-muted">{String(plan.assumptions.cycle_mode)}</span>
                    <span className="hidden text-border sm:inline">·</span>
                    <span className="text-muted">{plan.route.note}</span>
                  </div>
                </div>

                <div className={cn("space-y-3", mobileView === "logs" && "max-md:hidden")}>
                  <div className="no-print flex flex-wrap items-center gap-2">
                    <div className="flex flex-wrap items-center gap-1.5 rounded-xl border border-border bg-surface p-1 shadow-sm">
                      <button
                        type="button"
                        onClick={() => setDayFilterAll(true)}
                        className={cn(
                          "rounded-lg px-2.5 py-1.5 text-xs font-medium transition",
                          dayFilterAll ? "bg-ink text-white" : "text-muted hover:text-text",
                        )}
                      >
                        All days
                      </button>
                      {plan.daily_logs.map((d, i) => (
                        <button
                          key={d.date_local}
                          type="button"
                          onClick={() => {
                            setDayFilterAll(false);
                            setSelectedDayIndex(i);
                            const first = plan.timeline.find(
                              (e) =>
                                DateTime.fromISO(e.start_utc).setZone(homeTz).toISODate() === d.date_local,
                            );
                            if (first) setSelectedEventId(first.event_id);
                          }}
                          className={cn(
                            "rounded-lg px-2.5 py-1.5 text-xs font-medium tabular-nums transition",
                            !dayFilterAll && selectedDayIndex === i
                              ? "bg-action text-white"
                              : "text-muted hover:text-text",
                          )}
                        >
                          {DateTime.fromISO(d.date_local).toFormat("LLL d")}
                        </button>
                      ))}
                    </div>
                    <button
                      type="button"
                      onClick={() => setMapFocus((v) => !v)}
                      className="ml-auto inline-flex items-center gap-1.5 rounded-xl border border-border bg-surface px-3 py-1.5 text-xs font-medium text-muted shadow-sm transition hover:border-action/40 hover:text-text"
                    >
                      {mapFocus ? (
                        <>
                          <PanelLeftOpen className="h-3.5 w-3.5" /> Show planner
                        </>
                      ) : (
                        <>
                          <PanelLeftClose className="h-3.5 w-3.5" /> Map focus
                        </>
                      )}
                    </button>
                  </div>

                  <TripMap
                    plan={plan}
                    selectedEventId={selectedEventId}
                    selectedDay={activeDay}
                    homeTz={homeTz}
                    expanded={mapFocus}
                    onSelectEvent={(id) => selectEvent(id, plan)}
                  />

                  <TripTimelineScrubber
                    plan={plan}
                    selectedEventId={selectedEventId}
                    onSelectEvent={(id) => selectEvent(id, plan)}
                    homeTz={homeTz}
                  />
                </div>

                {selectedEvent && (
                  <div className="no-print panel px-4 py-3.5">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.05em] text-muted">
                      Planned clocks · not live telemetry
                    </div>
                    <div className="mt-2.5 grid grid-cols-2 gap-3 sm:grid-cols-4">
                      <ClockCell
                        label="Driving since break"
                        value={formatDuration(selectedEvent.clocks_at_end.driving_since_break_s)}
                      />
                      <ClockCell
                        label="Shift driving"
                        value={formatDuration(selectedEvent.clocks_at_end.shift_driving_s)}
                      />
                      <ClockCell
                        label="Cycle used"
                        value={formatDuration(selectedEvent.clocks_at_end.cycle_used_s)}
                      />
                      <ClockCell
                        label="Remaining cycle"
                        value={formatDuration(
                          Math.max(0, 70 * 3600 - selectedEvent.clocks_at_end.cycle_used_s),
                        )}
                      />
                    </div>
                  </div>
                )}

                <div
                  className={cn(
                    "panel",
                    mobileView === "map" && "max-md:hidden",
                  )}
                >
                  <div className="no-print flex flex-col gap-3 border-b border-border px-4 pt-2 sm:flex-row sm:items-end sm:justify-between sm:px-5">
                    <div className="relative flex gap-1 overflow-x-auto" role="tablist" aria-label="Plan details">
                      {TABS.map(([id, label]) => (
                        <button
                          key={id}
                          type="button"
                          role="tab"
                          aria-selected={tab === id}
                          onClick={() => setTab(id)}
                          className={cn(
                            "relative -mb-px px-3 py-3 text-sm font-medium whitespace-nowrap transition",
                            tab === id ? "text-action" : "text-muted hover:text-text",
                          )}
                        >
                          {tab === id && (
                            <motion.span
                              layoutId="detail-tab"
                              className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-action"
                              transition={{ type: "spring", stiffness: 450, damping: 36 }}
                            />
                          )}
                          {label}
                        </button>
                      ))}
                    </div>
                    <div className="flex shrink-0 gap-2 pb-3">
                      <button
                        type="button"
                        disabled={stale}
                        onClick={() => !stale && downloadLogsPdf(plan.daily_logs)}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-surface-elevated px-3 py-1.5 text-sm transition hover:bg-white disabled:opacity-40"
                      >
                        <Download className="h-4 w-4" />
                        <span className="hidden sm:inline">Download PDF</span>
                        <span className="sm:hidden">PDF</span>
                      </button>
                      <button
                        type="button"
                        disabled={stale}
                        onClick={() => window.print()}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-surface-elevated px-3 py-1.5 text-sm transition hover:bg-white disabled:opacity-40"
                      >
                        <Printer className="h-4 w-4" /> Print
                      </button>
                    </div>
                  </div>

                  <div className="p-4 sm:p-5">
                    {tab === "itinerary" && (
                      <ItineraryPanel
                        plan={plan}
                        selectedEventId={selectedEventId}
                        onSelectEvent={(id) => selectEvent(id, plan)}
                        homeTz={homeTz}
                      />
                    )}
                    {tab === "directions" && (
                      <ol className="list-decimal space-y-2 pl-5 text-sm">
                        {plan.route.legs.flatMap((leg) =>
                          leg.steps.map((s, i) => (
                            <li key={`${leg.leg_id}-${i}`}>
                              {s.instruction || "Continue"}{" "}
                              <span className="text-muted">
                                ({metersToMiles(s.distance_m).toFixed(1)} mi · {formatDuration(s.duration_s)})
                              </span>
                            </li>
                          )),
                        )}
                      </ol>
                    )}
                    {tab === "logs" && (
                      <div className="space-y-4">
                        <div className="no-print flex flex-wrap items-center gap-2">
                          <button
                            type="button"
                            className="rounded-lg border border-border px-3 py-1.5 text-sm disabled:opacity-40"
                            onClick={() => setSelectedDayIndex((i) => Math.max(0, i - 1))}
                            disabled={selectedDayIndex === 0}
                          >
                            Previous day
                          </button>
                          <span className="text-sm font-medium">
                            {plan.daily_logs[selectedDayIndex]?.date_local} ({selectedDayIndex + 1}/
                            {plan.daily_logs.length})
                          </span>
                          <button
                            type="button"
                            className="rounded-lg border border-border px-3 py-1.5 text-sm disabled:opacity-40"
                            onClick={() =>
                              setSelectedDayIndex((i) => Math.min(plan.daily_logs.length - 1, i + 1))
                            }
                            disabled={selectedDayIndex >= plan.daily_logs.length - 1}
                          >
                            Next day
                          </button>
                        </div>
                        {plan.daily_logs[selectedDayIndex] && (
                          <DailyLogSheet
                            sheet={plan.daily_logs[selectedDayIndex]}
                            highlightEventId={selectedEventId}
                          />
                        )}
                      </div>
                    )}
                    {tab === "insights" && (
                      <div className="space-y-3 text-sm">
                        <p>
                          Deterministic explanations are attached to each itinerary stop (“Why this stop?”).
                          Optional LLM insights are disabled (`AI_INSIGHTS_ENABLED=false`).
                        </p>
                        <ul className="list-disc space-y-1 pl-5 text-muted">
                          <li>Cycle mode: Conservative cycle estimate</li>
                          <li>Rule version: {plan.rule_version}</li>
                          <li>
                            Provider: {String(plan.provider.provider)} / {String(plan.provider.profile)}
                          </li>
                          <li>Events: {plan.timeline.length}</li>
                        </ul>
                      </div>
                    )}
                  </div>
                </div>

                <div className="print-only space-y-8" aria-hidden="true">
                  {plan.daily_logs.map((sheet) => (
                    <DailyLogSheet key={sheet.date_local} sheet={sheet} />
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </section>
      </main>
    </div>
  );
}

function Stat({ label, value, last }: { label: string; value: string; last?: boolean }) {
  return (
    <div className={cn("border-b border-border p-3.5 sm:border-b-0", !last && "sm:border-r")}>
      <div className="text-[10px] font-medium uppercase tracking-[0.05em] text-muted">{label}</div>
      <div className="mt-1 truncate text-sm font-semibold tracking-tight text-text">{value}</div>
    </div>
  );
}

function ClockCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-surface-elevated px-3 py-2.5">
      <div className="text-[10px] font-medium uppercase tracking-[0.04em] text-muted">{label}</div>
      <div className="mt-0.5 text-sm font-semibold text-ink">{value}</div>
    </div>
  );
}

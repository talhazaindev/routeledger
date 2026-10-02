import { useMemo, useState } from "react";
import { DateTime } from "luxon";
import {
  ChevronDown,
  Download,
  HelpCircle,
  Loader2,
  Map as MapIcon,
  Printer,
  Route,
} from "lucide-react";
import {
  ApiRequestError,
  createTrip,
  storeTripAccess,
  type TripPlan,
} from "../../api/client";
import { formatDuration, metersToMiles } from "../../lib/utils";
import { LocationCombobox } from "./LocationCombobox";
import {
  PRESETS,
  defaultFormState,
  formToPayload,
  type PlannerFormState,
} from "./presets";
import { TripMap } from "../map/TripMap";
import { ItineraryPanel } from "../itinerary/ItineraryPanel";
import { DailyLogSheet } from "../logs/DailyLogSheet";
import { downloadLogsPdf } from "../logs/exportPdf";

type Tab = "itinerary" | "directions" | "logs" | "insights";

export function PlannerPage() {
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

  return (
    <div className="min-h-screen overflow-x-hidden bg-bg text-text">
      <header className="no-print border-b border-border bg-surface">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-4 px-4 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-[#14263D] text-white">
              <Route className="h-5 w-5" aria-hidden />
            </div>
            <div className="min-w-0">
              <div className="text-base font-semibold tracking-tight">RouteLedger</div>
              <div className="truncate text-xs text-muted">Planned trip & driver log simulator</div>
            </div>
          </div>
          <nav className="flex shrink-0 items-center gap-3 text-sm sm:gap-4">
            <span className="font-medium text-action">Planner</span>
            {plan && (
              <button type="button" className="text-muted hover:text-text" onClick={() => setTab("logs")}>
                Logs
              </button>
            )}
            <a href="#assumptions" className="inline-flex items-center gap-1 text-muted hover:text-text">
              <HelpCircle className="h-4 w-4" /> <span className="hidden sm:inline">Assumptions</span>
            </a>
          </nav>
        </div>
      </header>

      <main className="mx-auto grid max-w-[1440px] gap-4 overflow-x-hidden px-4 py-4 lg:grid-cols-[360px_1fr]">
        <aside className="no-print space-y-4">
          <section className="rounded-[12px] border border-border bg-surface p-4 shadow-sm">
            <h1 className="text-lg font-semibold">Plan a trip</h1>
            <p className="mt-1 text-sm text-muted">
              Enter locations and cycle hours. Returns a routed map, stops, and planned daily logs.
            </p>

            <div className="mt-4 space-y-3">
              <LocationCombobox
                id="current"
                number={1}
                label="Current location"
                value={form.current}
                onChange={(v) => patch({ current: v })}
                error={fieldErrors.current || fieldErrors.current_location}
              />
              <LocationCombobox
                id="pickup"
                number={2}
                label="Pickup location"
                value={form.pickup}
                onChange={(v) => patch({ pickup: v })}
                error={fieldErrors.pickup || fieldErrors.pickup_location}
              />
              <LocationCombobox
                id="dropoff"
                number={3}
                label="Dropoff location"
                value={form.dropoff}
                onChange={(v) => patch({ dropoff: v })}
                error={fieldErrors.dropoff || fieldErrors.dropoff_location}
              />
              <div>
                <label htmlFor="cycle" className="text-sm font-medium">
                  4. Current Cycle Used (Hrs)
                </label>
                <input
                  id="cycle"
                  type="number"
                  min={0}
                  max={70}
                  step="0.01"
                  value={form.cycleUsedHours}
                  onChange={(e) => patch({ cycleUsedHours: e.target.value })}
                  className="mt-1.5 w-full rounded-[10px] border border-border bg-surface px-3 py-2.5 text-sm"
                  aria-invalid={!!fieldErrors.cycle}
                />
                <p className="mt-1 text-xs text-muted">
                  Total on-duty time already used in your current 8-day cycle, including driving. Remaining modeled:{" "}
                  {Math.max(0, 70 - (Number(form.cycleUsedHours) || 0)).toFixed(2)}h
                </p>
                {fieldErrors.cycle && <p className="text-xs text-red-600">{fieldErrors.cycle}</p>}
              </div>
            </div>

            <div id="assumptions" className="mt-4 rounded-[10px] bg-bg p-3 text-xs text-muted">
              Property-carrying · 70h/8d · fuel ≥ every 1,000 mi · pickup/dropoff 1h each · fresh shift at departure ·
              Conservative cycle estimate · not a certified ELD
            </div>

            <button
              type="button"
              className="mt-3 flex w-full items-center justify-between rounded-[10px] border border-border px-3 py-2 text-sm"
              onClick={() => setSettingsOpen((o) => !o)}
              aria-expanded={settingsOpen}
            >
              Planning settings
              <ChevronDown className={`h-4 w-4 transition ${settingsOpen ? "rotate-180" : ""}`} />
            </button>
            {settingsOpen && (
              <div className="mt-3 space-y-3 border-t border-border pt-3 text-sm">
                <div>
                  <label htmlFor="departure" className="font-medium">
                    Departure date and time
                  </label>
                  <input
                    id="departure"
                    type="datetime-local"
                    className="mt-1 w-full rounded-[10px] border border-border px-3 py-2"
                    value={DateTime.fromISO(form.departureLocal).toFormat("yyyy-LL-dd'T'HH:mm")}
                    onChange={(e) => {
                      const dt = DateTime.fromISO(e.target.value, { zone: form.homeTerminalTz });
                      patch({
                        departureLocal: dt.toISO({ suppressMilliseconds: true, includeOffset: true }) || "",
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
                    className="mt-1 w-full rounded-[10px] border border-border px-3 py-2"
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
                      className="mt-1 w-full rounded-[10px] border border-border px-2 py-2"
                      value={form.milesSinceFuel}
                      onChange={(e) => patch({ milesSinceFuel: e.target.value })}
                    />
                  </label>
                  <label className="text-xs">
                    Fuel stop (min)
                    <input
                      type="number"
                      min={1}
                      className="mt-1 w-full rounded-[10px] border border-border px-2 py-2"
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
                      })
                    }
                  />
                  Equipped sleeper berth
                </label>
                <label className="text-xs">
                  Rest status
                  <select
                    className="mt-1 w-full rounded-[10px] border border-border px-2 py-2"
                    value={form.restStatus}
                    disabled={!form.sleeperEquipped}
                    onChange={(e) => patch({ restStatus: e.target.value as "OFF" | "SB" })}
                  >
                    <option value="OFF">OFF</option>
                    <option value="SB">SB</option>
                  </select>
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
                        className="mt-1 w-full rounded-[10px] border border-border px-2 py-2"
                        value={form[key]}
                        onChange={(e) => patch({ [key]: e.target.value })}
                      />
                    </label>
                  ))}
                </div>
              </div>
            )}

            <button
              type="button"
              onClick={generate}
              disabled={loading}
              className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-[10px] bg-action px-4 py-3 text-sm font-semibold text-white hover:bg-action-hover disabled:opacity-60"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <MapIcon className="h-4 w-4" />}
              Generate trip plan
            </button>
            <div aria-live="polite" className="mt-2 min-h-[1.25rem] text-xs text-muted">
              {stage}
            </div>
            {error && (
              <div role="alert" className="mt-2 rounded-[10px] border border-red-200 bg-red-50 p-3 text-sm text-red-800">
                {error}
                <div className="mt-2 flex gap-2">
                  <button type="button" className="rounded-md border border-red-300 px-2 py-1 text-xs" onClick={generate}>
                    Retry
                  </button>
                </div>
              </div>
            )}

            <div className="mt-4 space-y-2">
              <div className="text-xs font-semibold uppercase tracking-wide text-muted">Sample trips</div>
              {PRESETS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => applyPreset(p.id)}
                  className="w-full rounded-[10px] border border-border px-3 py-2 text-left text-sm hover:border-action"
                >
                  <div className="font-medium">{p.label}</div>
                  <div className="text-xs text-muted">{p.description}</div>
                </button>
              ))}
            </div>
          </section>
        </aside>

        <section className="min-w-0 space-y-4">
          {!plan && !loading && (
            <div className="rounded-[12px] border border-dashed border-border bg-surface p-10 text-center text-muted">
              Generate a trip plan to see the map, itinerary, and daily logs.
            </div>
          )}

          {plan && (
            <>
              {stale && (
                <div role="status" className="no-print rounded-[10px] border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                  Inputs changed — regenerate. Export is disabled until you recalculate.
                </div>
              )}

              <div className="no-print flex gap-2 md:hidden">
                {(["overview", "map", "logs"] as const).map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => setMobileView(v)}
                    className={`rounded-full px-3 py-1.5 text-sm ${mobileView === v ? "bg-action text-white" : "bg-surface border border-border"}`}
                  >
                    {v}
                  </button>
                ))}
              </div>

              <div className={`rounded-[12px] border border-border bg-surface p-4 shadow-sm ${mobileView !== "overview" ? "max-md:hidden" : ""}`}>
                <div className="flex flex-wrap gap-4 text-sm">
                  <Stat label="Distance" value={`${metersToMiles(summary!.distance).toFixed(1)} mi`} />
                  <Stat label="Driving time" value={formatDuration(summary!.driving)} />
                  <Stat label="Elapsed trip" value={formatDuration(summary!.elapsed)} />
                  <Stat
                    label="Arrival at dropoff"
                    value={
                      summary!.dropoff
                        ? DateTime.fromISO(summary!.dropoff.start_utc).setZone(homeTz).toFormat("ccc LLL d, HH:mm")
                        : "—"
                    }
                  />
                  <Stat
                    label="Completion"
                    value={
                      summary!.last
                        ? DateTime.fromISO(summary!.last.end_utc).setZone(homeTz).toFormat("ccc LLL d, HH:mm")
                        : "—"
                    }
                  />
                  <Stat label="Log days" value={String(plan.daily_logs.length)} />
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-full bg-teal-50 px-2 py-1 font-medium text-action">
                    {plan.validation.label}
                  </span>
                  <span className="text-muted">{String(plan.assumptions.cycle_mode)}</span>
                  <span className="text-muted">{plan.route.note}</span>
                </div>
              </div>

              <div className={mobileView === "logs" ? "max-md:hidden" : ""}>
                <TripMap
                  plan={plan}
                  selectedEventId={selectedEventId}
                  selectedDay={plan.daily_logs[selectedDayIndex]?.date_local || null}
                  onSelectEvent={(id) => {
                    setSelectedEventId(id);
                    const ev = plan.timeline.find((e) => e.event_id === id);
                    if (ev) {
                      const day = DateTime.fromISO(ev.start_utc).setZone(homeTz).toISODate();
                      const idx = plan.daily_logs.findIndex((d) => d.date_local === day);
                      if (idx >= 0) setSelectedDayIndex(idx);
                    }
                  }}
                />
              </div>

              {selectedEvent && (
                <div className="no-print rounded-[10px] border border-border bg-surface p-3 text-xs text-muted">
                  Planned clocks at selected event — not live telemetry: driving since break{" "}
                  {formatDuration(selectedEvent.clocks_at_end.driving_since_break_s)} · shift driving{" "}
                  {formatDuration(selectedEvent.clocks_at_end.shift_driving_s)} · cycle used{" "}
                  {formatDuration(selectedEvent.clocks_at_end.cycle_used_s)} · remaining cycle{" "}
                  {formatDuration(Math.max(0, 70 * 3600 - selectedEvent.clocks_at_end.cycle_used_s))}
                </div>
              )}

              <div className={`rounded-[12px] border border-border bg-surface p-4 shadow-sm ${mobileView === "map" ? "max-md:hidden" : ""}`}>
                <div className="no-print mb-3 flex flex-wrap items-center gap-2 border-b border-border pb-3">
                  {(
                    [
                      ["itinerary", "Itinerary"],
                      ["directions", "Directions"],
                      ["logs", "Daily logs"],
                      ["insights", "Plan insights"],
                    ] as const
                  ).map(([id, label]) => (
                    <button
                      key={id}
                      type="button"
                      onClick={() => setTab(id)}
                      className={`rounded-full px-3 py-1.5 text-sm ${tab === id ? "bg-action text-white" : "bg-bg text-muted"}`}
                    >
                      {label}
                    </button>
                  ))}
                  <div className="ml-auto flex gap-2">
                    <button
                      type="button"
                      disabled={stale}
                      onClick={() => !stale && downloadLogsPdf(plan.daily_logs)}
                      className="inline-flex items-center gap-1 rounded-[10px] border border-border px-3 py-1.5 text-sm disabled:opacity-40"
                    >
                      <Download className="h-4 w-4" /> Download all logs PDF
                    </button>
                    <button
                      type="button"
                      disabled={stale}
                      onClick={() => window.print()}
                      className="inline-flex items-center gap-1 rounded-[10px] border border-border px-3 py-1.5 text-sm disabled:opacity-40"
                    >
                      <Printer className="h-4 w-4" /> Print
                    </button>
                  </div>
                </div>

                {tab === "itinerary" && (
                  <ItineraryPanel
                    plan={plan}
                    selectedEventId={selectedEventId}
                    onSelectEvent={setSelectedEventId}
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
                    <div className="no-print flex items-center gap-2">
                      <button
                        type="button"
                        className="rounded-md border border-border px-2 py-1 text-sm"
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
                        className="rounded-md border border-border px-2 py-1 text-sm"
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
                      Deterministic explanations are attached to each itinerary stop (“Why this stop?”). Optional LLM
                      insights are disabled (`AI_INSIGHTS_ENABLED=false`).
                    </p>
                    <ul className="list-disc space-y-1 pl-5 text-muted">
                      <li>Cycle mode: Conservative cycle estimate</li>
                      <li>Rule version: {plan.rule_version}</li>
                      <li>Provider: {String(plan.provider.provider)} / {String(plan.provider.profile)}</li>
                      <li>Events: {plan.timeline.length}</li>
                    </ul>
                  </div>
                )}
              </div>

              <div className="print-only space-y-8" aria-hidden="true">
                {plan.daily_logs.map((sheet) => (
                  <DailyLogSheet key={sheet.date_local} sheet={sheet} />
                ))}
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  );
}

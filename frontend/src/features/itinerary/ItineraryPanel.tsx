import { DateTime } from "luxon";
import type { TimelineEvent, TripPlan } from "../../api/client";
import { formatDuration, metersToMiles } from "../../lib/utils";
import { cn } from "../../lib/utils";

type Props = {
  plan: TripPlan;
  selectedEventId: string | null;
  onSelectEvent: (id: string) => void;
  homeTz: string;
};

const STATUS_STYLE: Record<string, string> = {
  OFF: "bg-slate-100 text-slate-700",
  SB: "bg-violet-100 text-violet-800",
  D: "bg-blue-100 text-blue-800",
  ON: "bg-amber-100 text-amber-900",
};

export function ItineraryPanel({ plan, selectedEventId, onSelectEvent, homeTz }: Props) {
  const byDay = new Map<string, TimelineEvent[]>();
  for (const ev of plan.timeline) {
    const day = DateTime.fromISO(ev.start_utc, { zone: "utc" }).setZone(homeTz).toISODate() || "unknown";
    if (!byDay.has(day)) byDay.set(day, []);
    byDay.get(day)!.push(ev);
  }

  return (
    <div className="space-y-4" role="list" aria-label="Trip itinerary">
      {[...byDay.entries()].map(([day, events]) => (
        <section key={day}>
          <h3 className="mb-2 text-sm font-semibold text-text">{day}</h3>
          <ul className="space-y-2">
            {events.map((ev) => {
              const start = DateTime.fromISO(ev.start_utc, { zone: "utc" }).setZone(homeTz);
              const end = DateTime.fromISO(ev.end_utc, { zone: "utc" }).setZone(homeTz);
              const selected = ev.event_id === selectedEventId;
              return (
                <li key={ev.event_id} role="listitem">
                  <button
                    type="button"
                    onClick={() => onSelectEvent(ev.event_id)}
                    className={cn(
                      "w-full rounded-[10px] border p-3 text-left transition",
                      selected ? "border-action bg-teal-50" : "border-border bg-surface hover:border-action/40",
                    )}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", STATUS_STYLE[ev.status])}>
                        {ev.status}
                      </span>
                      <span className="text-sm font-semibold">{ev.event_type.replaceAll("_", " ")}</span>
                      <span className="text-xs text-muted">
                        {start.toFormat("HH:mm")}–{end.toFormat("HH:mm")} · {formatDuration(ev.duration_s)}
                      </span>
                      {ev.distance_m > 0 && (
                        <span className="text-xs text-muted">{metersToMiles(ev.distance_m).toFixed(1)} mi</span>
                      )}
                    </div>
                    {ev.location_label && <p className="mt-1 text-sm text-muted">{ev.location_label}</p>}
                    <details className="mt-2">
                      <summary className="cursor-pointer text-xs font-medium text-action">Why this stop?</summary>
                      <p className="mt-1 text-xs text-muted">{ev.explanation}</p>
                    </details>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}

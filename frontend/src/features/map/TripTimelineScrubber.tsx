import { useMemo, useRef, useEffect } from "react";
import { DateTime } from "luxon";
import type { TimelineEvent, TripPlan } from "../../api/client";
import { cn, formatDuration } from "../../lib/utils";

const EVENT_COLOR: Record<string, string> = {
  PICKUP: "#0F766E",
  DROPOFF: "#C2410C",
  FUEL: "#CA8A04",
  REST: "#7C3AED",
  RESTART: "#6D28D9",
  BREAK: "#64748B",
  INSPECTION: "#2563EB",
  DRIVING: "#1D4ED8",
  ASSUMED_OFF: "#94A3B8",
};

type Props = {
  plan: TripPlan;
  selectedEventId: string | null;
  onSelectEvent: (id: string) => void;
  homeTz: string;
};

/** Horizontal trip timeline scrubber — click a segment to select that event. */
export function TripTimelineScrubber({ plan, selectedEventId, onSelectEvent, homeTz }: Props) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const selectedRef = useRef<HTMLButtonElement>(null);

  const events = plan.timeline;
  const totalMs = useMemo(() => {
    if (events.length === 0) return 1;
    const start = DateTime.fromISO(events[0].start_utc).toMillis();
    const end = DateTime.fromISO(events[events.length - 1].end_utc).toMillis();
    return Math.max(1, end - start);
  }, [events]);

  useEffect(() => {
    selectedRef.current?.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
  }, [selectedEventId]);

  if (events.length === 0) return null;

  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-2.5">
        <div>
          <div className="font-display text-sm font-semibold text-ink">Trip timeline</div>
          <div className="text-[11px] text-muted">Scrub to select a stop — map and itinerary stay in sync</div>
        </div>
        <div className="hidden text-[11px] text-muted sm:block">
          {DateTime.fromISO(events[0].start_utc).setZone(homeTz).toFormat("ccc LLL d")}
          {" → "}
          {DateTime.fromISO(events[events.length - 1].end_utc).setZone(homeTz).toFormat("ccc LLL d")}
        </div>
      </div>

      <div ref={scrollerRef} className="overflow-x-auto px-3 py-3">
        <div className="relative flex min-w-[640px] gap-1" role="listbox" aria-label="Trip timeline events">
          {/* continuous track */}
          <div className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-border/80" aria-hidden />
          {events.map((ev) => {
            const start = DateTime.fromISO(ev.start_utc).toMillis();
            const end = DateTime.fromISO(ev.end_utc).toMillis();
            const flex = Math.max(0.08, (end - start) / totalMs);
            const color = EVENT_COLOR[ev.event_type] || EVENT_COLOR[ev.status] || "#526174";
            const selected = ev.event_id === selectedEventId;
            const label = shortLabel(ev);
            const startLocal = DateTime.fromISO(ev.start_utc).setZone(homeTz);

            return (
              <button
                key={ev.event_id}
                ref={selected ? selectedRef : undefined}
                type="button"
                role="option"
                aria-selected={selected}
                onClick={() => onSelectEvent(ev.event_id)}
                style={{ flex }}
                title={`${ev.event_type} · ${startLocal.toFormat("HH:mm")} · ${formatDuration(ev.duration_s)}`}
                className={cn(
                  "group relative z-10 flex min-w-[2.5rem] flex-col items-center gap-1.5 rounded-lg px-0.5 py-1 transition",
                  selected ? "scale-[1.02]" : "hover:opacity-100",
                )}
              >
                <span
                  className={cn(
                    "h-2.5 w-full rounded-full transition",
                    selected ? "ring-2 ring-offset-1 ring-action" : "opacity-90 group-hover:opacity-100",
                  )}
                  style={{ background: color }}
                />
                <span
                  className={cn(
                    "max-w-full truncate text-[10px] font-semibold",
                    selected ? "text-ink" : "text-muted",
                  )}
                >
                  {label}
                </span>
                <span className="text-[9px] tabular-nums text-muted">{startLocal.toFormat("HH:mm")}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function shortLabel(ev: TimelineEvent): string {
  switch (ev.event_type) {
    case "DRIVING":
      return "Drive";
    case "PICKUP":
      return "Pickup";
    case "DROPOFF":
      return "Drop";
    case "FUEL":
      return "Fuel";
    case "REST":
      return "Rest";
    case "RESTART":
      return "34h";
    case "BREAK":
      return "Break";
    case "INSPECTION":
      return "Insp.";
    default:
      return ev.event_type.slice(0, 6);
  }
}

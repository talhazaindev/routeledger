import { useEffect, useMemo, useState } from "react";
import {
  MapContainer,
  TileLayer,
  Polyline,
  Marker,
  Popup,
  useMap,
  CircleMarker,
} from "react-leaflet";
import L from "leaflet";
import { DateTime } from "luxon";
import { Crosshair, Maximize2, Minus, Plus } from "lucide-react";
import type { TimelineEvent, TripPlan } from "../../api/client";
import { cn } from "../../lib/utils";

type Props = {
  plan: TripPlan;
  selectedEventId: string | null;
  onSelectEvent: (id: string) => void;
  selectedDay: string | null;
  homeTz: string;
  expanded?: boolean;
};

type StopMeta = {
  label: string;
  color: string;
  name: string;
};

const STOP_META: Record<string, StopMeta> = {
  PICKUP: { label: "P", color: "#0F766E", name: "Pickup" },
  DROPOFF: { label: "D", color: "#C2410C", name: "Dropoff" },
  FUEL: { label: "F", color: "#CA8A04", name: "Fuel" },
  REST: { label: "Z", color: "#7C3AED", name: "Rest" },
  RESTART: { label: "R", color: "#6D28D9", name: "34h restart" },
  BREAK: { label: "B", color: "#64748B", name: "Break" },
  INSPECTION: { label: "I", color: "#2563EB", name: "Inspection" },
};

const LEGEND_ITEMS: Array<{ label: string; color: string; name: string }> = [
  { label: "S", color: "#14263D", name: "Start" },
  { label: "P", color: "#0F766E", name: "Pickup" },
  { label: "D", color: "#C2410C", name: "Dropoff" },
  { label: "F", color: "#CA8A04", name: "Fuel" },
  { label: "Z", color: "#7C3AED", name: "Rest" },
  { label: "R", color: "#6D28D9", name: "Restart" },
  { label: "B", color: "#64748B", name: "Break" },
  { label: "I", color: "#2563EB", name: "Inspection" },
];

const MIN_ZOOM = 4;
const MAX_ZOOM = 14;

function FitBounds({
  positions,
  trigger,
  requestKey,
}: {
  positions: [number, number][];
  trigger: string;
  requestKey: number;
}) {
  const map = useMap();
  useEffect(() => {
    if (positions.length < 2) return;
    map.fitBounds(positions, { padding: [48, 48] });
  }, [map, trigger, requestKey]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

function PanToSelected({ event, pulse }: { event: TimelineEvent | null; pulse: number }) {
  const map = useMap();
  useEffect(() => {
    const c = event?.end_coord || event?.start_coord;
    if (c) map.panTo([c.lat, c.lon], { animate: true });
  }, [event, map, pulse]);
  return null;
}

function MapZoomBridge({
  zoom,
  onZoomChange,
}: {
  zoom: number;
  onZoomChange: (z: number) => void;
}) {
  const map = useMap();

  useEffect(() => {
    const sync = () => onZoomChange(map.getZoom());
    sync();
    map.on("zoomend", sync);
    return () => {
      map.off("zoomend", sync);
    };
  }, [map, onZoomChange]);

  useEffect(() => {
    if (Math.abs(map.getZoom() - zoom) > 0.05) {
      map.setZoom(zoom, { animate: true });
    }
  }, [map, zoom]);

  return null;
}

function HideDefaultZoom() {
  const map = useMap();
  useEffect(() => {
    map.zoomControl?.remove();
  }, [map]);
  return null;
}

function stopIcon(meta: StopMeta, selected: boolean, dimmed: boolean) {
  const size = selected ? 30 : 24;
  const opacity = dimmed && !selected ? 0.35 : 1;
  const ring = selected ? "0 0 0 3px rgba(15,118,110,0.4)" : "0 1px 4px rgba(0,0,0,.28)";
  return L.divIcon({
    className: "rl-stop-marker",
    html: `<div style="
      background:${meta.color};
      color:#fff;
      border-radius:999px;
      width:${size}px;
      height:${size}px;
      opacity:${opacity};
      display:flex;
      align-items:center;
      justify-content:center;
      font:700 11px Inter,ui-sans-serif,system-ui,sans-serif;
      border:2px solid #fff;
      box-shadow:${ring};
    ">${meta.label}</div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function belongsToDay(ev: TimelineEvent, dayLocal: string, homeTz: string): boolean {
  const day = DateTime.fromISO(ev.start_utc, { zone: "utc" }).setZone(homeTz).toISODate();
  return day === dayLocal;
}

export function TripMap({
  plan,
  selectedEventId,
  onSelectEvent,
  selectedDay,
  homeTz,
  expanded = false,
}: Props) {
  const [zoom, setZoom] = useState(5);
  const [fitKey, setFitKey] = useState(0);
  const [focusPulse, setFocusPulse] = useState(0);

  const geometry = useMemo(() => {
    const pts: [number, number][] = [];
    for (const leg of plan.route.legs) {
      for (const [lon, lat] of leg.geometry) {
        pts.push([lat, lon]);
      }
    }
    return pts;
  }, [plan.route.legs]);

  const stops = useMemo(() => {
    return plan.timeline.filter((e) =>
      ["PICKUP", "DROPOFF", "FUEL", "REST", "RESTART", "BREAK", "INSPECTION"].includes(e.event_type),
    );
  }, [plan.timeline]);

  const presentTypes = useMemo(() => {
    const types = new Set(stops.map((s) => s.event_type));
    return LEGEND_ITEMS.filter(
      (item) =>
        item.label === "S" ||
        (item.label === "P" && types.has("PICKUP")) ||
        (item.label === "D" && types.has("DROPOFF")) ||
        (item.label === "F" && types.has("FUEL")) ||
        (item.label === "Z" && types.has("REST")) ||
        (item.label === "R" && types.has("RESTART")) ||
        (item.label === "B" && types.has("BREAK")) ||
        (item.label === "I" && types.has("INSPECTION")),
    );
  }, [stops]);

  const selected = plan.timeline.find((e) => e.event_id === selectedEventId) || null;

  return (
    <div
      className={cn(
        "panel relative w-full max-w-full overflow-hidden transition-[height] duration-300",
        expanded ? "h-[380px] sm:h-[480px] md:h-[560px]" : "h-[280px] sm:h-[360px] md:h-[440px]",
      )}
    >
      <MapContainer
        center={geometry[0] || [39.5, -98]}
        zoom={5}
        scrollWheelZoom={false}
        className="h-full w-full max-w-full"
        attributionControl
        zoomControl={false}
      >
        <HideDefaultZoom />
        <TileLayer url={plan.map.tile_url} attribution={plan.map.attribution} />
        <FitBounds positions={geometry} trigger={plan.id} requestKey={fitKey} />
        <PanToSelected event={selected} pulse={focusPulse} />
        <MapZoomBridge zoom={zoom} onZoomChange={setZoom} />
        {geometry.length > 1 && (
          <Polyline positions={geometry} pathOptions={{ color: "#0F766E", weight: 4, opacity: 0.85 }} />
        )}
        {stops.map((ev) => {
          const c = ev.end_coord || ev.start_coord;
          if (!c) return null;
          const meta = STOP_META[ev.event_type] || {
            label: "•",
            color: "#14263D",
            name: ev.event_type,
          };
          const selectedMark = ev.event_id === selectedEventId;
          const dimmed = !!selectedDay && !belongsToDay(ev, selectedDay, homeTz);
          return (
            <Marker
              key={ev.event_id}
              position={[c.lat, c.lon]}
              icon={stopIcon(meta, selectedMark, dimmed)}
              eventHandlers={{ click: () => onSelectEvent(ev.event_id) }}
            >
              <Popup>
                <div className="text-sm">
                  <strong style={{ color: meta.color }}>{meta.name}</strong>
                  <div>{ev.location_label || "Along route"}</div>
                  <div className="text-xs text-slate-600">{ev.explanation}</div>
                </div>
              </Popup>
            </Marker>
          );
        })}
        {plan.timeline[0]?.start_coord && (
          <CircleMarker
            center={[plan.timeline[0].start_coord.lat, plan.timeline[0].start_coord.lon]}
            radius={7}
            pathOptions={{
              color: "#fff",
              weight: 2,
              fillColor: "#14263D",
              fillOpacity: 1,
            }}
          >
            <Popup>
              <div className="text-sm">
                <strong>Start</strong>
                <div>{plan.timeline[0].location_label || "Current location"}</div>
              </div>
            </Popup>
          </CircleMarker>
        )}
      </MapContainer>

      <div className="absolute top-3 right-3 z-[1000] flex flex-col items-center gap-1.5 rounded-2xl border border-border/80 bg-white/95 p-2 shadow-[var(--shadow-soft)] backdrop-blur-sm">
        <button
          type="button"
          className="flex h-8 w-8 items-center justify-center rounded-xl text-text transition hover:bg-surface-elevated disabled:opacity-40"
          aria-label="Zoom in"
          disabled={zoom >= MAX_ZOOM}
          onClick={() => setZoom((z) => Math.min(MAX_ZOOM, z + 1))}
        >
          <Plus className="h-4 w-4" />
        </button>
        <input
          type="range"
          min={MIN_ZOOM}
          max={MAX_ZOOM}
          step={0.5}
          value={zoom}
          aria-valuemin={MIN_ZOOM}
          aria-valuemax={MAX_ZOOM}
          aria-valuenow={zoom}
          aria-label="Map zoom level"
          onChange={(e) => setZoom(Number(e.target.value))}
          className="rl-zoom-slider my-1"
        />
        <button
          type="button"
          className="flex h-8 w-8 items-center justify-center rounded-xl text-text transition hover:bg-surface-elevated disabled:opacity-40"
          aria-label="Zoom out"
          disabled={zoom <= MIN_ZOOM}
          onClick={() => setZoom((z) => Math.max(MIN_ZOOM, z - 1))}
        >
          <Minus className="h-4 w-4" />
        </button>
        <div className="my-0.5 h-px w-6 bg-border" aria-hidden />
        <button
          type="button"
          className="flex h-8 w-8 items-center justify-center rounded-xl text-text transition hover:bg-surface-elevated"
          aria-label="Fit entire route"
          title="Fit route"
          onClick={() => setFitKey((k) => k + 1)}
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          className="flex h-8 w-8 items-center justify-center rounded-xl text-text transition hover:bg-surface-elevated disabled:opacity-40"
          aria-label="Focus selected stop"
          title="Focus selected"
          disabled={!selectedEventId}
          onClick={() => setFocusPulse((k) => k + 1)}
        >
          <Crosshair className="h-3.5 w-3.5" />
        </button>
        <span className="pt-0.5 text-[9px] font-semibold tabular-nums text-muted">{zoom.toFixed(1)}</span>
      </div>

      <div className="pointer-events-none absolute bottom-3 left-3 right-14 z-[1000] flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-xl border border-border/80 bg-white/95 px-3 py-2 text-[11px] text-muted shadow-[var(--shadow-soft)] backdrop-blur-sm sm:right-auto">
        {presentTypes.map((item) => (
          <span key={item.label} className="inline-flex items-center gap-1.5">
            <span
              aria-hidden
              className="inline-flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold text-white"
              style={{ background: item.color }}
            >
              {item.label}
            </span>
            <span>{item.name}</span>
          </span>
        ))}
        <span className="basis-full text-[10px] text-muted/90 sm:basis-auto sm:border-l sm:border-border sm:pl-3">
          Planned pins · facility not verified
        </span>
      </div>
    </div>
  );
}

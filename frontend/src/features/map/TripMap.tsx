import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap, CircleMarker } from "react-leaflet";
import L from "leaflet";
import type { TimelineEvent, TripPlan } from "../../api/client";

type Props = {
  plan: TripPlan;
  selectedEventId: string | null;
  onSelectEvent: (id: string) => void;
  selectedDay: string | null;
};

function FitBounds({ positions, trigger }: { positions: [number, number][]; trigger: string }) {
  const map = useMap();
  useEffect(() => {
    if (positions.length < 2) return;
    map.fitBounds(positions, { padding: [40, 40] });
  }, [map, trigger]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

function PanToSelected({ event }: { event: TimelineEvent | null }) {
  const map = useMap();
  useEffect(() => {
    const c = event?.end_coord || event?.start_coord;
    if (c) map.panTo([c.lat, c.lon]);
  }, [event, map]);
  return null;
}

const stopIcon = (label: string, selected: boolean) =>
  L.divIcon({
    className: "",
    html: `<div style="background:${selected ? "#0F766E" : "#14263D"};color:#fff;border-radius:999px;min-width:22px;height:22px;display:flex;align-items:center;justify-content:center;font:600 11px Inter,sans-serif;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.25)">${label}</div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });

export function TripMap({ plan, selectedEventId, onSelectEvent, selectedDay }: Props) {
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
    const interesting = plan.timeline.filter((e) =>
      ["PICKUP", "DROPOFF", "FUEL", "REST", "RESTART", "BREAK", "INSPECTION"].includes(e.event_type),
    );
    // Group collocated
    return interesting;
  }, [plan.timeline]);

  const selected = plan.timeline.find((e) => e.event_id === selectedEventId) || null;

  const dayFilteredGeom = useMemo(() => {
    if (!selectedDay) return geometry;
    // Approximate: keep full geometry; day filter highlights via stops
    return geometry;
  }, [geometry, selectedDay]);

  return (
    <div className="relative h-[280px] w-full max-w-full overflow-hidden rounded-[12px] border border-border bg-surface sm:h-[360px] md:h-[440px]">
      <MapContainer
        center={geometry[0] || [39.5, -98]}
        zoom={5}
        scrollWheelZoom={false}
        className="h-full w-full max-w-full"
        attributionControl
      >
        <TileLayer url={plan.map.tile_url} attribution={plan.map.attribution} />
        <FitBounds positions={dayFilteredGeom} trigger={plan.id} />
        <PanToSelected event={selected} />
        {dayFilteredGeom.length > 1 && (
          <Polyline positions={dayFilteredGeom} pathOptions={{ color: "#0F766E", weight: 4, opacity: 0.85 }} />
        )}
        {stops.map((ev, i) => {
          const c = ev.end_coord || ev.start_coord;
          if (!c) return null;
          const selectedMark = ev.event_id === selectedEventId;
          const label =
            ev.event_type === "PICKUP"
              ? "P"
              : ev.event_type === "DROPOFF"
                ? "D"
                : ev.event_type === "FUEL"
                  ? "F"
                  : ev.event_type === "RESTART"
                    ? "R"
                    : String(i + 1);
          return (
            <Marker
              key={ev.event_id}
              position={[c.lat, c.lon]}
              icon={stopIcon(label, selectedMark)}
              eventHandlers={{ click: () => onSelectEvent(ev.event_id) }}
            >
              <Popup>
                <div className="text-sm">
                  <strong>{ev.event_type}</strong>
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
            radius={6}
            pathOptions={{ color: "#14263D", fillColor: "#14263D", fillOpacity: 1 }}
          />
        )}
      </MapContainer>
      <div className="pointer-events-none absolute bottom-3 left-3 rounded-md bg-white/95 px-2 py-1 text-[11px] text-muted shadow">
        Legend: P pickup · D dropoff · F fuel · R restart · pins are planned, facility not verified
      </div>
    </div>
  );
}

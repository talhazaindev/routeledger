import type { DailyLog } from "../../api/client";
import { formatHours } from "../../lib/utils";

const ROW_ORDER = ["OFF", "SB", "D", "ON"] as const;
const ROW_LABELS: Record<(typeof ROW_ORDER)[number], string> = {
  OFF: "Off Duty",
  SB: "Sleeper Berth",
  D: "Driving",
  ON: "On Duty (not driving)",
};

type Props = {
  sheet: DailyLog;
  width?: number;
  highlightEventId?: string | null;
};

export function DailyLogSheet({ sheet, width = 780, highlightEventId }: Props) {
  const height = 560;
  const pad = 16;
  const gridX = 130;
  const gridY = 120;
  const gridW = width - gridX - 90;
  const gridH = 160;
  const rowH = gridH / 4;

  function xAt(seconds: number) {
    return gridX + (seconds / 86400) * gridW;
  }

  function yFor(status: string) {
    const idx = ROW_ORDER.indexOf(status as (typeof ROW_ORDER)[number]);
    return gridY + idx * rowH + rowH / 2;
  }

  const hourMarks = Array.from({ length: 25 }, (_, i) => i);

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      role="img"
      aria-label={`Driver daily log for ${sheet.date_local}`}
      className="rounded-[10px] border border-border bg-white shadow-sm"
    >
      <rect x={0} y={0} width={width} height={height} fill="#fff" />
      <text x={pad} y={28} fontSize={14} fontWeight={700} fill="#14263D">
        Drivers Daily Log (24 hours)
      </text>
      <text x={width - pad} y={28} fontSize={11} fill="#526174" textAnchor="end">
        Date: {sheet.date_local}
      </text>
      <text x={pad} y={48} fontSize={10} fill="#526174">
        {sheet.planned_banner}
      </text>
      <text x={pad} y={68} fontSize={11} fill="#14263D">
        From: {sheet.from_label}
      </text>
      <text x={pad} y={84} fontSize={11} fill="#14263D">
        To: {sheet.to_label}
      </text>
      <text x={width - pad} y={68} fontSize={11} fill="#14263D" textAnchor="end">
        Total Miles Driving Today: {sheet.driving_miles.toFixed(1)}
      </text>
      <text x={width - pad} y={84} fontSize={11} fill="#14263D" textAnchor="end">
        Total Mileage Today: {sheet.total_miles.toFixed(1)}
      </text>
      <text x={pad} y={102} fontSize={10} fill="#526174">
        Carrier: {sheet.carrier_name || "Not provided"} · Terminal: {sheet.home_terminal || "Not provided"} · Truck:{" "}
        {sheet.tractor_trailer || "Not provided"}
      </text>
      <text x={width - pad} y={102} fontSize={10} fill="#526174" textAnchor="end">
        {sheet.timezone} ({sheet.utc_offset})
      </text>

      {/* Hour header */}
      <rect x={gridX} y={gridY - 18} width={gridW} height={18} fill="#14263D" />
      {hourMarks.map((h) => {
        const x = xAt(h * 3600);
        const label =
          h === 0 || h === 24 ? "Midnight" : h === 12 ? "Noon" : h > 12 ? String(h - 12) : String(h);
        return (
          <g key={h}>
            <line
              x1={x}
              y1={gridY - 18}
              x2={x}
              y2={gridY + gridH}
              stroke={h % 6 === 0 ? "#94a3b8" : "#e2e8f0"}
              strokeWidth={h % 6 === 0 ? 1 : 0.5}
            />
            {h < 24 && (
              <text x={x + 2} y={gridY - 5} fontSize={8} fill="#fff">
                {label}
              </text>
            )}
            {/* quarter-hour guides */}
            {h < 24 &&
              [1, 2, 3].map((q) => (
                <line
                  key={q}
                  x1={xAt(h * 3600 + q * 900)}
                  y1={gridY}
                  x2={xAt(h * 3600 + q * 900)}
                  y2={gridY + gridH}
                  stroke="#f1f5f9"
                  strokeWidth={0.5}
                />
              ))}
          </g>
        );
      })}
      <rect x={gridX} y={gridY} width={gridW} height={gridH} fill="none" stroke="#14263D" strokeWidth={1.2} />

      {ROW_ORDER.map((status, i) => (
        <g key={status}>
          <text x={gridX - 8} y={gridY + i * rowH + rowH / 2 + 4} fontSize={10} fill="#14263D" textAnchor="end">
            {ROW_LABELS[status]}
          </text>
          <line
            x1={gridX}
            y1={gridY + (i + 1) * rowH}
            x2={gridX + gridW}
            y2={gridY + (i + 1) * rowH}
            stroke="#cbd5e1"
          />
          <text x={gridX + gridW + 8} y={gridY + i * rowH + rowH / 2 + 4} fontSize={11} fill="#14263D">
            {formatHours(sheet.totals_s[status] || 0)}
          </text>
        </g>
      ))}
      <text x={gridX + gridW + 8} y={gridY - 6} fontSize={9} fill="#526174">
        Total Hours
      </text>

      {/* Status graph with vertical connectors */}
      {sheet.segments.map((seg, i) => {
        const y = yFor(seg.status);
        const x1 = xAt(seg.start_s);
        const x2 = xAt(seg.end_s);
        const highlighted = highlightEventId && seg.event_id === highlightEventId;
        const next = sheet.segments[i + 1];
        return (
          <g key={`${seg.event_id}-${seg.start_s}`}>
            <line
              x1={x1}
              y1={y}
              x2={x2}
              y2={y}
              stroke={highlighted ? "#0F766E" : "#0f172a"}
              strokeWidth={highlighted ? 3 : 2}
            />
            {next && (
              <line
                x1={x2}
                y1={y}
                x2={x2}
                y2={yFor(next.status)}
                stroke="#0f172a"
                strokeWidth={2}
              />
            )}
          </g>
        );
      })}

      {/* Remarks */}
      <text x={pad} y={gridY + gridH + 28} fontSize={12} fontWeight={600} fill="#14263D">
        Remarks
      </text>
      {sheet.remarks.slice(0, 8).map((r, i) => (
        <text key={i} x={pad} y={gridY + gridH + 46 + i * 14} fontSize={10} fill="#14263D">
          {new Date(r.time_local).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} — {r.text}
          {r.estimated ? " (estimated location)" : ""}
        </text>
      ))}
      {sheet.remarks.length > 8 && (
        <text x={pad} y={gridY + gridH + 46 + 8 * 14} fontSize={10} fill="#526174">
          +{sheet.remarks.length - 8} more remarks on continuation (see export)
        </text>
      )}

      {/* Recap */}
      <text x={pad} y={height - 70} fontSize={11} fontWeight={600} fill="#14263D">
        Recap: Complete at end of day (70h / 8 day)
      </text>
      <text x={pad} y={height - 54} fontSize={10} fill="#526174">
        On duty hours today (lines 3 & 4): {formatHours((sheet.totals_s.D || 0) + (sheet.totals_s.ON || 0))}
      </text>
      <text x={pad} y={height - 40} fontSize={10} fill="#526174">
        A–C history fields: History required (conservative cycle estimate)
      </text>
      <text x={pad} y={height - 26} fontSize={10} fill="#526174">
        60h / 7 day: Not applicable
      </text>
      <text x={width - pad} y={height - 40} fontSize={10} fill="#526174" textAnchor="end">
        Signature: ________________ (left blank — planned record)
      </text>
      <text x={width - pad} y={height - 24} fontSize={10} fill="#526174" textAnchor="end">
        Page {sheet.page_number} of {sheet.total_pages}
      </text>
    </svg>
  );
}

import { motion, useReducedMotion } from "framer-motion";

export function BrandEmptyState() {
  const reduce = useReducedMotion();

  return (
    <motion.div
      className="panel relative flex min-h-[460px] flex-col items-center justify-center overflow-hidden px-6 py-16 text-center app-route-grid"
      initial={reduce ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
    >
      <div
        className="pointer-events-none absolute inset-0 bg-gradient-to-br from-action/5 via-transparent to-ink/5"
        aria-hidden
      />
      <CorridorArt />
      <h2 className="font-display relative mt-6 text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
        Chart the corridor
      </h2>
      <p className="relative mt-3 max-w-md text-sm leading-relaxed text-muted">
        Set current, pickup, and dropoff — or load a sample trip — then generate a routed map,
        HOS-aware stops, and planned daily logs.
      </p>
      <div className="relative mt-6 inline-flex items-center gap-2 rounded-full border border-border bg-white/80 px-3 py-1.5 text-[11px] font-medium text-muted shadow-sm">
        <span className="h-1.5 w-1.5 rounded-full bg-action" aria-hidden />
        Waiting for trip inputs
      </div>
    </motion.div>
  );
}

function CorridorArt() {
  return (
    <svg
      viewBox="0 0 320 160"
      className="relative h-auto w-full max-w-[340px]"
      role="img"
      aria-label="Abstract route corridor illustration"
    >
      <defs>
        <linearGradient id="rl-ribbon" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#0F766E" stopOpacity="0.9" />
          <stop offset="55%" stopColor="#14263D" stopOpacity="0.85" />
          <stop offset="100%" stopColor="#C4A574" stopOpacity="0.9" />
        </linearGradient>
        <filter id="rl-soft" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="2" />
        </filter>
      </defs>
      <rect x="8" y="12" width="304" height="136" rx="20" fill="#F8FAFC" stroke="#D4DCE6" />
      {/* contour lines */}
      <path d="M24 120c40-28 70-20 110-36s70-30 120-18" stroke="#D4DCE6" strokeWidth="1" fill="none" />
      <path d="M28 96c36-18 68-10 104-22s66-24 112-12" stroke="#E2E8F0" strokeWidth="1" fill="none" />
      <path d="M32 72c32-12 60-8 92-16s58-18 104-8" stroke="#E8EEF4" strokeWidth="1" fill="none" />
      {/* main ribbon */}
      <path
        d="M36 118c48-36 78-44 118-52 42-8 72 4 110 22"
        stroke="url(#rl-ribbon)"
        strokeWidth="6"
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M36 118c48-36 78-44 118-52 42-8 72 4 110 22"
        stroke="#fff"
        strokeWidth="1.5"
        strokeLinecap="round"
        fill="none"
        opacity="0.35"
      />
      {/* pins */}
      <circle cx="36" cy="118" r="7" fill="#0B1524" stroke="#fff" strokeWidth="2" />
      <circle cx="154" cy="66" r="7" fill="#0F766E" stroke="#fff" strokeWidth="2" />
      <circle cx="264" cy="88" r="7" fill="#C2410C" stroke="#fff" strokeWidth="2" />
      {/* soft glow */}
      <ellipse cx="160" cy="130" rx="90" ry="10" fill="#0F766E" opacity="0.08" filter="url(#rl-soft)" />
      <text
        x="160"
        y="42"
        textAnchor="middle"
        fill="#14263D"
        fontFamily="Fraunces, serif"
        fontSize="14"
        fontWeight="600"
      >
        RouteLedger
      </text>
    </svg>
  );
}

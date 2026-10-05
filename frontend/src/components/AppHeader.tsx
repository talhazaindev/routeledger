import { FileText, HelpCircle } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { cn } from "../lib/utils";

type Props = {
  hasPlan: boolean;
  onLogsClick: () => void;
};

export function RouteGlyph({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <rect width="40" height="40" rx="11" fill="#0B1524" />
      <path
        d="M10 28c4-1 6-5 10-8s7-4 10-3"
        stroke="#0F766E"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
      <circle cx="10" cy="28" r="2.4" fill="#C4A574" />
      <circle cx="20" cy="20" r="2.2" fill="#fff" />
      <circle cx="30" cy="17" r="2.4" fill="#0F766E" />
    </svg>
  );
}

export function AppHeader({ hasPlan, onLogsClick }: Props) {
  const reduce = useReducedMotion();

  return (
    <motion.header
      className="app-shell-header no-print sticky top-0 z-40 border-b border-border/70"
      initial={reduce ? false : { opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="h-[3px] w-full bg-gradient-to-r from-ink via-action to-accent-warm" aria-hidden />
      <div className="mx-auto flex h-[60px] max-w-[1440px] items-center justify-between gap-4 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <RouteGlyph className="h-9 w-9 shrink-0 shadow-sm" />
          <div className="min-w-0 leading-tight">
            <div className="font-display text-[18px] font-semibold tracking-tight text-ink">
              RouteLedger
            </div>
            <div className="hidden truncate text-[11px] text-muted sm:block">
              Planned trip & driver log simulator
            </div>
          </div>
        </div>

        <nav className="relative flex shrink-0 items-center gap-1 rounded-full border border-border/80 bg-surface-elevated/80 p-1" aria-label="Primary">
          <span
            className={cn(
              "relative rounded-full px-3.5 py-1.5 text-sm font-medium text-white",
            )}
          >
            <motion.span
              layoutId="nav-pill"
              className="absolute inset-0 rounded-full bg-action shadow-sm"
              transition={{ type: "spring", stiffness: 420, damping: 34 }}
            />
            <span className="relative z-10">Planner</span>
          </span>
          {hasPlan && (
            <button
              type="button"
              onClick={onLogsClick}
              className="inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-medium text-muted transition hover:bg-white hover:text-text"
            >
              <FileText className="h-3.5 w-3.5" aria-hidden />
              Logs
            </button>
          )}
          <a
            href="#assumptions"
            className="inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-medium text-muted transition hover:bg-white hover:text-text"
          >
            <HelpCircle className="h-3.5 w-3.5" aria-hidden />
            <span className="hidden sm:inline">Assumptions</span>
          </a>
        </nav>
      </div>
    </motion.header>
  );
}

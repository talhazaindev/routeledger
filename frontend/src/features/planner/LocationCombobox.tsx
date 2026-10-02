import { useEffect, useId, useRef, useState } from "react";
import { MapPin, Loader2 } from "lucide-react";
import { searchLocations, type LocationValue } from "../../api/client";
import { cn } from "../../lib/utils";

type Props = {
  id?: string;
  label: string;
  number?: number;
  value: LocationValue | null;
  onChange: (value: LocationValue | null) => void;
  error?: string;
};

export function LocationCombobox({ id, label, number, value, onChange, error }: Props) {
  const listId = useId();
  const [query, setQuery] = useState(value?.label ?? "");
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [options, setOptions] = useState<LocationValue[]>([]);
  const [active, setActive] = useState(0);
  const abortRef = useRef<AbortController | null>(null);
  const seqRef = useRef(0);

  useEffect(() => {
    setQuery(value?.label ?? "");
  }, [value?.label]);

  useEffect(() => {
    if (query.trim().length < 2) {
      setOptions([]);
      return;
    }
    // If query matches selected label exactly, don't re-search
    if (value && query === value.label) {
      return;
    }
    const handle = window.setTimeout(async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const seq = ++seqRef.current;
      setLoading(true);
      try {
        const data = await searchLocations(query.trim(), controller.signal);
        if (seq !== seqRef.current) return;
        setOptions(data.results);
        setOpen(true);
        setActive(0);
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        if (seq !== seqRef.current) return;
        setOptions([]);
      } finally {
        if (seq === seqRef.current) setLoading(false);
      }
    }, 250);
    return () => window.clearTimeout(handle);
  }, [query, value]);

  function select(opt: LocationValue) {
    onChange(opt);
    setQuery(opt.label);
    setOpen(false);
  }

  function onInputChange(next: string) {
    setQuery(next);
    if (value && next !== value.label) {
      onChange(null); // invalidate coordinates until resolved again
    }
  }

  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="flex items-center gap-2 text-sm font-medium text-text">
        {number != null && (
          <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-action text-[11px] font-semibold text-white">
            {number}
          </span>
        )}
        {label}
      </label>
      <div className="relative">
        <MapPin className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
        <input
          id={id}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-invalid={!!error}
          className={cn(
            "w-full rounded-[10px] border bg-surface py-2.5 pl-9 pr-9 text-sm shadow-sm",
            error ? "border-red-500" : "border-border focus:border-action",
          )}
          value={query}
          onChange={(e) => onInputChange(e.target.value)}
          onFocus={() => options.length > 0 && setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 150)}
          onKeyDown={(e) => {
            if (!open || options.length === 0) return;
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((i) => Math.min(i + 1, options.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((i) => Math.max(i - 1, 0));
            } else if (e.key === "Enter") {
              e.preventDefault();
              select(options[active]);
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
          placeholder="Search city, state…"
          autoComplete="off"
        />
        {loading && (
          <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted" aria-hidden />
        )}
        {open && options.length > 0 && (
          <ul
            id={listId}
            role="listbox"
            className="absolute z-30 mt-1 max-h-56 w-full overflow-auto rounded-[10px] border border-border bg-surface py-1 shadow-lg"
          >
            {options.map((opt, i) => (
              <li key={`${opt.label}-${opt.coordinates.lat}-${opt.coordinates.lon}`} role="option" aria-selected={i === active}>
                <button
                  type="button"
                  className={cn(
                    "flex w-full flex-col px-3 py-2 text-left text-sm",
                    i === active ? "bg-bg" : "hover:bg-bg",
                  )}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => select(opt)}
                >
                  <span className="font-medium">{opt.label}</span>
                  <span className="text-xs text-muted">
                    {[opt.locality, opt.region, opt.country_code || "US"].filter(Boolean).join(" · ")}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {error && (
        <p className="text-xs text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

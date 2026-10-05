import type { ReactNode } from "react";
import { cn } from "../lib/utils";

type SpineItem = {
  number: number;
  children: ReactNode;
};

type Props = {
  items: SpineItem[];
  className?: string;
};

/** Vertical route spine connecting numbered location steps. */
export function RouteSpine({ items, className }: Props) {
  return (
    <ol className={cn("relative space-y-0", className)}>
      {items.map((item, i) => {
        const isLast = i === items.length - 1;
        return (
          <li key={item.number} className="relative flex gap-3 pb-4 last:pb-0">
            <div className="relative flex w-7 shrink-0 flex-col items-center">
              <span className="z-10 flex h-7 w-7 items-center justify-center rounded-full bg-ink text-[12px] font-semibold text-white shadow-sm ring-2 ring-white">
                {item.number}
              </span>
              {!isLast && (
                <span
                  className="absolute top-7 bottom-0 w-0.5 bg-gradient-to-b from-action/70 to-border"
                  aria-hidden
                />
              )}
            </div>
            <div className="min-w-0 flex-1 pt-0.5">{item.children}</div>
          </li>
        );
      })}
    </ol>
  );
}

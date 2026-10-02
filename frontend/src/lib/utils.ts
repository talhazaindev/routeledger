import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatHours(seconds: number): string {
  const h = seconds / 3600;
  if (Math.abs(h - Math.round(h)) < 1e-9) return `${Math.round(h)}h`;
  return `${h.toFixed(2)}h`;
}

export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}

export function metersToMiles(m: number): number {
  return m / 1609.344;
}

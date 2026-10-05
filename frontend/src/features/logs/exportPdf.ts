import { jsPDF } from "jspdf";
import "svg2pdf.js";
import type { DailyLog } from "../../api/client";
import { createElement } from "react";
import { createRoot } from "react-dom/client";
import { DailyLogSheet } from "./DailyLogSheet";

/** Render each daily log SVG into a US Letter PDF page. */
export async function downloadLogsPdf(sheets: DailyLog[], filename = "routeledger-logs.pdf") {
  const pdf = new jsPDF({ orientation: "landscape", unit: "pt", format: "letter" });
  const pageW = pdf.internal.pageSize.getWidth();
  const pageH = pdf.internal.pageSize.getHeight();

  for (let i = 0; i < sheets.length; i++) {
    if (i > 0) pdf.addPage();
    const host = document.createElement("div");
    host.style.position = "fixed";
    host.style.left = "-10000px";
    host.style.top = "0";
    document.body.appendChild(host);
    const root = createRoot(host);
    await new Promise<void>((resolve) => {
      root.render(createElement(DailyLogSheet, { sheet: sheets[i], width: 720 }));
      requestAnimationFrame(() => resolve());
    });
    // wait a tick for SVG paint
    await new Promise((r) => setTimeout(r, 50));
    const svg = host.querySelector("svg");
    if (svg) {
      const margin = 24;
      await pdf.svg(svg, {
        x: margin,
        y: margin,
        width: pageW - margin * 2,
        height: pageH - margin * 2,
      });
    }
    root.unmount();
    document.body.removeChild(host);
  }

  pdf.save(filename);
}

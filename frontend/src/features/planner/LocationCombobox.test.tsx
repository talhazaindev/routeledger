import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LocationCombobox } from "./LocationCombobox";

describe("LocationCombobox", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          results: [
            {
              label: "Chicago, Illinois, United States",
              coordinates: { lat: 41.8781, lon: -87.6298 },
              region: "IL",
              locality: "Chicago",
              country_code: "US",
              confidence: 0.9,
            },
          ],
        }),
      })),
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("selects a search result and keeps coordinates", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<LocationCombobox label="Current location" value={null} onChange={onChange} />);
    const input = screen.getByRole("combobox");
    await user.type(input, "Chi");
    await waitFor(() => expect(screen.getByText(/Chicago, Illinois/)).toBeInTheDocument());
    await user.click(screen.getByText(/Chicago, Illinois/));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        label: "Chicago, Illinois, United States",
        coordinates: { lat: 41.8781, lon: -87.6298 },
      }),
    );
  });
});

import {describe, expect, it} from "vitest";
import type {JobSummary} from "../api/api";
import {matches} from "./JobsPage";

const job: JobSummary = {
  id: 1,
  name: "RO/00042",
  label: "Silver/2005/Toyota/Corolla",
  state: "confirmed",
  state_label: "Confirmed",
  stage: null,
  priority: false,
  schedule_date: null,
  partner: {id: 2, name: "Wile E. Coyote"},
  vehicle: {
    id: 3,
    description: "Silver/2005/Toyota/Corolla",
    license_plate: "MXW4783",
    vin: "2T1KR32E05C123456",
    model_year: "2005",
    unit_number: "T-104",
  },
  technician: null,
  is_mine: true,
  customer_concern: "Grinding when braking",
  timer_running: false,
  parts_done: 0,
  parts_total: 1,
  inspection_graded: 0,
  inspection_total: 0,
};

describe("My Jobs filter", () => {
  it("matches what is printed on a work order or a car, any case", () => {
    for (const text of [
      "mxw4783",
      "C123456",
      "t-104",
      "coyote",
      "00042",
      "grinding",
      "  corolla ",
    ]) {
      expect(matches(job, text), text).toBe(true);
    }
  });
  it("matches everything when empty, nothing when unrelated", () => {
    expect(matches(job, "")).toBe(true);
    expect(matches(job, "F-150")).toBe(false);
  });
});

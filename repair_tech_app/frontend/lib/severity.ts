/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * How each inspection grade looks. The order of colours follows the PDF the
 * customer gets (shop_inspection_report): green good, yellow later, orange
 * attention, red today, the darkest for a failed state inspection.
 */
import {
  CheckCircleIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  MinusCircleIcon,
  WrenchIcon,
  XCircleIcon,
} from "@heroicons/react/24/solid";
import type {ComponentType, SVGProps} from "react";
import type {InspectionLine} from "../api/api";

export type Severity = NonNullable<InspectionLine["severity"]>;
type BadgeVariant = "green" | "yellow" | "orange" | "red" | "error" | "neutral";

export const SEVERITY: Readonly<
  Record<
    Severity,
    {
      badge: BadgeVariant;
      icon: ComponentType<SVGProps<SVGSVGElement>>;
      problem: boolean;
    }
  >
> = {
  good: {badge: "green", icon: CheckCircleIcon, problem: false},
  future: {badge: "yellow", icon: ClockIcon, problem: false},
  attention: {badge: "orange", icon: ExclamationTriangleIcon, problem: true},
  today: {badge: "red", icon: WrenchIcon, problem: true},
  fail_state: {badge: "error", icon: XCircleIcon, problem: true},
  na: {badge: "neutral", icon: MinusCircleIcon, problem: false},
};

/** Grades in the order the grading buttons show them: best to worst, then skip. */
export const SEVERITY_ORDER: readonly Severity[] = [
  "good",
  "future",
  "attention",
  "today",
  "fail_state",
  "na",
];

/** A grade in a badge's room. */
export const SHORT_LABEL: Readonly<Record<Severity, string>> = {
  good: "Good",
  future: "Later",
  attention: "Attention",
  today: "Today",
  fail_state: "Failed",
  na: "N/A",
};

export function isSeverity(value: unknown): value is Severity {
  return (
    typeof value === "string" && (SEVERITY_ORDER as readonly string[]).includes(value)
  );
}

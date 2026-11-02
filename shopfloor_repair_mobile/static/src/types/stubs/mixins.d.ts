/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Type-only stub for shopfloor_mobile_base's `scenario/mixins.esm.js` (the
 * `ScenarioBaseMixin` state machine) - see registry.d.ts for why this
 * exists. Declared as the subset of `data`/`computed`/
 * `methods` this module's scenario file actually reads; see that file's
 * own JS source for the full implementation.
 */
export interface StateSpec {
    display_info?: Record<string, unknown>;
    enter?: () => void;
    exit?: () => void;
    on_scan?: (scanned: unknown) => void;
    on_user_confirm?: (answer: unknown) => void;
    events?: Record<string, string | ((...args: unknown[]) => void)>;
    [key: string]: unknown;
}

export interface WrappedState extends StateSpec {
    key: string;
    data: Record<string, any>;
}

export const ScenarioBaseMixin: {
    data(): Record<string, unknown>;
    computed: Record<string, unknown>;
    methods: Record<string, unknown>;
    [key: string]: unknown;
};

/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The instance shape shopfloor_mobile_base's `ScenarioBaseMixin` (a plain,
 * untyped Vue 2 mixin object) gives a scenario component - see
 * scenario_base_mixin.esm.js, which attaches it to that mixin's
 * constructor form.
 */
import Vue from "vue";
import {WrappedState} from "/shopfloor_mobile_base/static/src/scenario/mixins.esm.js";
import {OdooClient} from "../types/shopfloor-mobile-base";

export {WrappedState};

export interface ScenarioBaseMixinInterface extends Vue {
    usage: string;
    initial_state_key: string;
    current_state_key: string;
    current_state: Record<string, unknown>;
    states: Record<string, unknown>;
    menu_item_id: unknown;
    messages: {
        message: {body: string | null; message_type: string | null};
        popup: {body: string | null};
    };
    need_confirmation: boolean;

    readonly odoo: OdooClient;
    readonly state: WrappedState;
    readonly search_input_placeholder: string;
    readonly show_cancel_button: boolean;
    readonly screen_info: Record<string, unknown>;
    readonly user_message: unknown;
    readonly user_popup: unknown;

    state_is(state_key: string): boolean;
    state_in(state_keys: string[]): boolean;
    state_to(state_key: string): Promise<unknown>;
    state_get_data(state_key?: string): Record<string, any>;
    state_set_data(data: Record<string, unknown>, state_key?: string, reload_state?: boolean): void;
    state_reset_data(state_key?: string): void;
    state_reset_data_all(): void;
    make_state_component_key(bits: unknown[]): string;
    make_component_key(bits: unknown[]): string;
    storage_key(state_key?: string): string;
    screen_klass(): string;
    wait_call<T>(promise: Promise<T>): Promise<T>;
    on_scan(scanned: {text: string}): void;
    set_message(message: {body: string; message_type: string}): void;
    set_popup(popup: {body: string}): void;
    reset_notification(): void;
}

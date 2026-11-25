/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */
import {useToast} from "@astryxdesign/core/Toast";
import {errorMessage} from "../api/client";

/** Toasts for what a write did, and for what went wrong (an error stays until dismissed). */
export function useNotify() {
    const showToast = useToast();
    return {
        done: (body: string): void => {
            showToast({body});
        },
        failed: (error: unknown): void => {
            showToast({body: errorMessage(error), type: "error"});
        },
    };
}

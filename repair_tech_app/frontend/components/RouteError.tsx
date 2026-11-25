/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */
import {Button} from "@astryxdesign/core/Button";
import {Center} from "@astryxdesign/core/Center";
import {EmptyState} from "@astryxdesign/core/EmptyState";
import {Icon} from "@astryxdesign/core/Icon";
import {useQueryErrorResetBoundary} from "@tanstack/react-query";
import {useRouter, type ErrorComponentProps} from "@tanstack/react-router";
import {errorMessage, RpcError} from "../api/client";

/** A screen that couldn't load: say why, in the technician's terms, and offer a retry. */
export function RouteError({error, reset}: ErrorComponentProps) {
    const router = useRouter();
    const queries = useQueryErrorResetBoundary();
    const offline = error instanceof RpcError && error.kind === "network";
    const retry = (): void => {
        queries.reset();
        reset();
        void router.invalidate();
    };
    return (
        <Center padding={8}>
            <EmptyState
                icon={<Icon icon={offline ? "warning" : "error"} size="lg" />}
                title={offline ? "No connection" : "This didn't load"}
                description={
                    offline
                        ? "This screen hasn't been opened on this device yet, so there is nothing saved to show. Try again once you're back online."
                        : errorMessage(error)
                }
                actions={<Button label="Try again" variant="primary" onClick={retry} />}
            />
        </Center>
    );
}

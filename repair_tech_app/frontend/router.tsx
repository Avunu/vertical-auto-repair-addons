/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Every screen is a typed route under /repair-tech/app/ (the controller
 * serves the page for any path below it, so a reload or a home-screen
 * shortcut lands anywhere). Loaders prefetch each screen's facade into the
 * query cache; screens read it with useSuspenseQuery. Every screen but My
 * Jobs, the one the app opens on, is its own chunk, loaded on intent (a
 * touch on its link) and precached by the service worker for offline.
 */
import type {QueryClient} from "@tanstack/react-query";
import {
    createRootRouteWithContext,
    createRoute,
    createRouter,
    lazyRouteComponent,
    redirect,
    type RegisteredRouter,
    type ToOptions,
} from "@tanstack/react-router";
import {Shell} from "./components/Shell";
import {facade} from "./data/queries";
import {JobsPage} from "./routes/JobsPage";
import {RouteError} from "./components/RouteError";
import {PageSkeleton} from "./components/PageSkeleton";

export const BASEPATH = "/repair-tech/app";

/** A route parameter that must be a record id. */
function toId(value: string): number {
    const id = Number(value);
    if (!Number.isSafeInteger(id) || id <= 0) {
        throw new Error(`Not a record id: ${value}`);
    }
    return id;
}

function optionalString(value: unknown): string | undefined {
    return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function optionalPage(value: unknown): number | undefined {
    const page = Number(value);
    return Number.isSafeInteger(page) && page > 1 ? page : undefined;
}

const rootRoute = createRootRouteWithContext<{queryClient: QueryClient}>()({
    component: Shell,
    loader: ({context}) => context.queryClient.ensureQueryData(facade("session", {})),
});

const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/",
    beforeLoad: () => {
        throw redirect({to: "/jobs"});
    },
});

const jobsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "jobs",
    validateSearch: (search: Record<string, unknown>): {scan?: boolean} => (search["scan"] ? {scan: true} : {}),
    loader: ({context}) => context.queryClient.ensureQueryData(facade("jobs", {})),
    component: JobsPage,
});

const jobParams = {
    parse: ({jobId}: {jobId: string}) => ({jobId: toId(jobId)}),
    stringify: ({jobId}: {jobId: number}) => ({jobId: String(jobId)}),
};

const jobRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "jobs/$jobId",
    params: jobParams,
    loader: ({context, params}) => context.queryClient.ensureQueryData(facade("job", {repair_id: params.jobId})),
    component: lazyRouteComponent(() => import("./routes/JobPage"), "JobPage"),
});

const partsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "jobs/$jobId/parts",
    params: jobParams,
    loader: ({context, params}) => context.queryClient.ensureQueryData(facade("parts", {repair_id: params.jobId})),
    component: lazyRouteComponent(() => import("./routes/PartsPage"), "PartsPage"),
});

export interface CatalogSearch {
    q?: string;
    category?: number;
    page?: number;
}

const catalogRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "jobs/$jobId/catalog",
    params: jobParams,
    validateSearch: (search: Record<string, unknown>): CatalogSearch => {
        const q = optionalString(search["q"]);
        const category = Number(search["category"]);
        const page = optionalPage(search["page"]);
        return {
            ...(q ? {q} : {}),
            ...(Number.isSafeInteger(category) && category > 0 ? {category} : {}),
            ...(page ? {page} : {}),
        };
    },
    component: lazyRouteComponent(() => import("./routes/CatalogPage"), "CatalogPage"),
});

const inspectionsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "jobs/$jobId/inspections",
    params: jobParams,
    loader: ({context, params}) => context.queryClient.ensureQueryData(facade("inspections", {repair_id: params.jobId})),
    component: lazyRouteComponent(() => import("./routes/InspectionsPage"), "InspectionsPage"),
});

const inspectionRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "inspections/$inspectionId",
    params: {
        parse: ({inspectionId}: {inspectionId: string}) => ({inspectionId: toId(inspectionId)}),
        stringify: ({inspectionId}: {inspectionId: number}) => ({inspectionId: String(inspectionId)}),
    },
    loader: ({context, params}) =>
        context.queryClient.ensureQueryData(facade("inspection", {inspection_id: params.inspectionId})),
    component: lazyRouteComponent(() => import("./routes/InspectionPage"), "InspectionPage"),
});

const inspectionLineRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "inspections/$inspectionId/items/$lineId",
    params: {
        parse: ({inspectionId, lineId}: {inspectionId: string; lineId: string}) => ({
            inspectionId: toId(inspectionId),
            lineId: toId(lineId),
        }),
        stringify: ({inspectionId, lineId}: {inspectionId: number; lineId: number}) => ({
            inspectionId: String(inspectionId),
            lineId: String(lineId),
        }),
    },
    loader: ({context, params}) => context.queryClient.ensureQueryData(facade("inspection_line", {line_id: params.lineId})),
    component: lazyRouteComponent(() => import("./routes/InspectionLinePage"), "InspectionLinePage"),
});

export interface TimesheetSearch {
    q?: string;
    page?: number;
}

const timesheetsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "timesheets",
    validateSearch: (search: Record<string, unknown>): TimesheetSearch => {
        const q = optionalString(search["q"]);
        const page = optionalPage(search["page"]);
        return {...(q ? {q} : {}), ...(page ? {page} : {})};
    },
    component: lazyRouteComponent(() => import("./routes/TimesheetsPage"), "TimesheetsPage"),
});

const routeTree = rootRoute.addChildren([
    indexRoute,
    jobsRoute,
    jobRoute,
    partsRoute,
    catalogRoute,
    inspectionsRoute,
    inspectionRoute,
    inspectionLineRoute,
    timesheetsRoute,
]);

export function makeRouter(queryClient: QueryClient) {
    return createRouter({
        routeTree,
        basepath: BASEPATH,
        context: {queryClient},
        defaultPreload: "intent",
        // The query cache decides freshness; the router always asks it.
        defaultPreloadStaleTime: 0,
        defaultPendingComponent: PageSkeleton,
        defaultErrorComponent: RouteError,
        scrollRestoration: true,
    });
}

declare module "@tanstack/react-router" {
    interface Register {
        router: ReturnType<typeof makeRouter>;
    }
}

/** A typed destination, as Astryx components take it: an href string. */
export type Destination = ToOptions<RegisteredRouter>;

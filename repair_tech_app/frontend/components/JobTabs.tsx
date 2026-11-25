/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */
import {Badge} from "@astryxdesign/core/Badge";
import {Tab, TabList} from "@astryxdesign/core/TabList";
import type {JobSummary} from "../api/api";
import {useHref} from "./links";

export type JobTab = "overview" | "parts" | "inspections";

/** The job's three screens, as link tabs: each is its own route. */
export function JobTabs({job, current}: {job: JobSummary; current: JobTab}) {
    const href = useHref();
    const params = {jobId: job.id};
    return (
        <TabList value={current} onChange={() => undefined} hasDivider isFullBleed>
            <Tab value="overview" label="Overview" href={href({to: "/jobs/$jobId", params})} />
            <Tab
                value="parts"
                label="Parts"
                href={href({to: "/jobs/$jobId/parts", params})}
                endContent={job.parts_total ? <Badge label={`${job.parts_done}/${job.parts_total}`} /> : null}
            />
            <Tab
                value="inspections"
                label="Inspections"
                href={href({to: "/jobs/$jobId/inspections", params})}
                endContent={job.inspection_total ? <Badge label={`${job.inspection_graded}/${job.inspection_total}`} /> : null}
            />
        </TabList>
    );
}

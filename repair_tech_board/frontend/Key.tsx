/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */
import type {BoardJob, BoardJobType} from "./api/api";
import {JobTypeIcon} from "./Icons";
import {STATUSES} from "./status";

export function Key({jobs, jobTypes}: {jobs: BoardJob[]; jobTypes: BoardJobType[]}) {
    return (
        <footer className="key">
            {STATUSES.map((status) => (
                <div key={status.id} className={`k s-${status.id}`}>
                    <span className="sw">{status.tag}</span>
                    <span>{status.label}</span>
                    <span className="n">{jobs.filter((job) => job.status === status.id).length}</span>
                </div>
            ))}
            {jobTypes.length > 0 && (
                <div className="legend">
                    {jobTypes.map((jobType) => (
                        <div key={jobType.id} className="k">
                            <JobTypeIcon icon={jobType.icon} />
                            {jobType.label}
                        </div>
                    ))}
                </div>
            )}
        </footer>
    );
}

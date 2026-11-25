/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */
import type {BoardJob} from "./api/api";
import {JobTypeIcon} from "./Icons";
import {STATUS} from "./status";

export function Card({job}: {job: BoardJob}) {
    const status = STATUS[job.status];
    return (
        <article
            className={`card s-${job.status}`}
            aria-label={[`WO ${job.number}`, job.customer, job.vehicle, job.job_type?.label, status.label]
                .filter(Boolean)
                .join(", ")}
        >
            {/* A job whose appointment type has no icon keeps the slot, so the cards stay aligned. */}
            {job.job_type ? <JobTypeIcon icon={job.job_type.icon} /> : <span className="ico" aria-hidden="true" />}
            <div className="who">
                <div className="cust">{job.customer}</div>
                <div className="veh">{job.vehicle}</div>
            </div>
            <div className="wo">
                <div className="n">
                    <small>WO#</small>
                    {job.number}
                </div>
                <div className="tag">{status.tag}</div>
            </div>
        </article>
    );
}

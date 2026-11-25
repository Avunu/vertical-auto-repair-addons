/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */
import type {BoardJob} from "./api/api";
import {Card} from "./Card";
import type {Plan} from "./layout";
import {STATUSES} from "./status";

export interface ColumnData {
    key: string;
    name: string;
    unassigned: boolean;
    jobs: BoardJob[];
}

const initials = (name: string) =>
    name
        .split(/\s+/)
        .map((word) => word[0])
        .join("")
        .slice(0, 2)
        .toUpperCase();

export function Column({
    column,
    plan,
    tick,
}: {
    column: ColumnData;
    plan: Plan;
    /** Counts up every few seconds; a column with more cards than fit pages on it. */
    tick: number;
}) {
    const {jobs} = column;
    const paged = jobs.length > plan.capacity;
    const size = paged ? plan.pagedCapacity : plan.capacity;
    const pages = paged ? Math.ceil(jobs.length / size) : 1;
    const page = tick % pages;
    const shown = jobs.slice(page * size, page * size + size);

    return (
        <section className={column.unassigned ? "col un" : "col"} aria-label={column.name}>
            <header className="head">
                <div className="who-row">
                    <div className="avatar">{column.unassigned ? "?" : initials(column.name)}</div>
                    <div className="name">{column.name}</div>
                    <div className="count">{jobs.length}</div>
                </div>
                <div className="mix">
                    {STATUSES.map((status) => {
                        const n = jobs.filter((job) => job.status === status.id).length;
                        return n > 0 && <i key={status.id} style={{flex: n, background: `var(--${status.id})`}} />;
                    })}
                </div>
            </header>
            <div className="cards" key={page}>
                {jobs.length === 0 ? (
                    <div className="empty">No jobs</div>
                ) : (
                    shown.map((job) => <Card key={job.id} job={job} />)
                )}
            </div>
            {paged && (
                <footer className="pager">
                    <span>
                        {page * size + 1}–{Math.min(jobs.length, page * size + size)} of {jobs.length}
                    </span>
                    <span className="dots">
                        {Array.from({length: pages}, (_, i) => (
                            <i key={i} className={i === page ? "on" : ""} />
                        ))}
                    </span>
                </footer>
            )}
        </section>
    );
}

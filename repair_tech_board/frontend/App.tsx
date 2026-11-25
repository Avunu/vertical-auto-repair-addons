/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */
import {useEffect, useState, type CSSProperties} from "react";
import {Column, type ColumnData} from "./Column";
import {Header} from "./Header";
import {Key} from "./Key";
import {planBoard} from "./layout";
import {byUrgency} from "./status";
import {useBoard} from "./useBoard";
import {useFit} from "./useFit";
import {useWakeLock} from "./useWakeLock";

const PAGE_MS = 10_000;

function loadingMessage(stale: boolean, denied: boolean): string {
    if (denied) {
        return "This user is not allowed to see the board. Sign in as a technician (Inventory access).";
    }
    return stale ? "Can't reach the server. Retrying." : "Loading the board";
}

export function App() {
    const {board, stale, denied} = useBoard();
    const {ref, scale, width, height} = useFit<HTMLDivElement>();
    useWakeLock();
    const [tick, setTick] = useState(0);
    useEffect(() => {
        const pager = setInterval(() => setTick((n) => n + 1), PAGE_MS);
        return () => clearInterval(pager);
    }, []);

    // Recomputed only when `board` changes: the React Compiler memoizes it.
    const columns: ColumnData[] = [];
    if (board) {
        const jobsOf = (technicianId: number | null) =>
            board.jobs.filter((job) => job.technician_id === technicianId).sort(byUrgency);
        columns.push(
            {key: "unassigned", name: "Unassigned", unassigned: true, jobs: jobsOf(null)},
            ...board.technicians.map((tech) => ({
                key: String(tech.id),
                name: tech.name,
                unassigned: false,
                jobs: jobsOf(tech.id),
            }))
        );
    }

    const plan = planBoard(Math.max(columns.length, 1), height);
    const d = plan.density;
    const boardStyle = {
        "--cols": plan.cols,
        "--rows": plan.rows,
        "--ch": `${d.card}px`,
        "--f1": `${d.f1}px`,
        "--f2": `${d.f2}px`,
        "--fwo": `${d.fwo}px`,
        "--ftag": `${d.ftag}px`,
        "--icon": `${d.icon}px`,
        "--hh": `${d.head}px`,
        "--fname": `${d.fname}px`,
    } as CSSProperties;

    return (
        <div className="viewport" ref={ref}>
            <main className="stage" style={{"--k": scale, "--w": `${width}px`, "--h": `${height}px`} as CSSProperties}>
                <Header open={board?.jobs.length ?? 0} unassigned={columns[0]?.jobs.length ?? 0} stale={stale} />
                <div className="board" style={boardStyle}>
                    {board ? (
                        columns.map((column) => <Column key={column.key} column={column} plan={plan} tick={tick} />)
                    ) : (
                        <div className="loading">{loadingMessage(stale, denied)}</div>
                    )}
                </div>
                <Key jobs={board?.jobs ?? []} jobTypes={board?.job_types ?? []} />
            </main>
        </div>
    );
}

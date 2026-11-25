/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */
import {useEffect, useState} from "react";

function useNow(): Date {
    const [now, setNow] = useState(() => new Date());
    useEffect(() => {
        const ticker = setInterval(() => setNow(new Date()), 1000);
        return () => clearInterval(ticker);
    }, []);
    return now;
}

export function Header({open, unassigned, stale}: {open: number; unassigned: number; stale: boolean}) {
    const now = useNow();
    return (
        <header className="top">
            <div className="title">Repair Job Board</div>
            {stale && <div className="stale">Not updating. Showing the last board received.</div>}
            <div className="stat">
                <b>{open}</b>open jobs
            </div>
            <div className="stat">
                <b>{unassigned}</b>unassigned
            </div>
            <div className="clock">
                <span className="t">{now.toLocaleTimeString([], {hour: "numeric", minute: "2-digit"})}</span>
                <span className="d">
                    {now.toLocaleDateString([], {weekday: "long", month: "short", day: "numeric"})}
                </span>
            </div>
        </header>
    );
}

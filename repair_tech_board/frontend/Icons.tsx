/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */

import type {BoardJobType} from "./api/api";

const Wheel = ({cx, cy}: {cx: number; cy: number}) => (
    <>
        <circle cx={cx} cy={cy} r={6.4} className="cut" />
        <circle cx={cx} cy={cy} r={5} />
    </>
);

export const CarIcon = () => (
    <svg viewBox="0 0 56 32" className="ico" role="img" aria-label="Car">
        <path d="M2 25V18.5Q2 15.8 5 15.2L12 13.6 18 6.4Q19 5 21 5H35Q37 5 38.2 6.4L44 13.6 51 15.2Q54 15.8 54 18.5V25Z" />
        <path className="cut" d="M19.2 8H27V13.2H14.6ZM29.6 8H35L40.2 13.2H29.6Z" />
        <Wheel cx={14} cy={25} />
        <Wheel cx={42} cy={25} />
    </svg>
);

export const TruckIcon = () => (
    <svg viewBox="0 0 56 32" className="ico" role="img" aria-label="Heavy truck">
        <path d="M2 25V14.5Q2 12.8 3.8 12.8H10.5L12.6 5.2Q13.1 3.5 15 3.5H25V25Z" />
        <path className="cut" d="M14.2 6H23V12H13Z" />
        <rect x={27} y={3.5} width={27} height={21.5} rx={2} />
        <path className="rib" d="M34 7V21M40.5 7V21M47 7V21" />
        <Wheel cx={8} cy={26} />
        <Wheel cx={30} cy={26} />
        <Wheel cx={43} cy={26} />
        <Wheel cx={51} cy={26} />
    </svg>
);

/** The icon an appointment type is marked with on the board. */
export const JobTypeIcon = ({icon}: {icon: BoardJobType["icon"]}) => (icon === "truck" ? <TruckIcon /> : <CarIcon />);

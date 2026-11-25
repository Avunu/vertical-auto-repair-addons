/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * My Timesheets: the technician's own job time, a card per day with the
 * day's clocked time beside it, and everything correctable in place - an
 * entry's times and job, moving part of it to another job, breaks, and the
 * clock-in times themselves.
 */
import {Badge} from "@astryxdesign/core/Badge";
import {Card} from "@astryxdesign/core/Card";
import {EmptyState} from "@astryxdesign/core/EmptyState";
import {Heading} from "@astryxdesign/core/Heading";
import {HStack} from "@astryxdesign/core/HStack";
import {Icon} from "@astryxdesign/core/Icon";
import {List, ListItem} from "@astryxdesign/core/List";
import {Pagination} from "@astryxdesign/core/Pagination";
import {Spinner} from "@astryxdesign/core/Spinner";
import {Text} from "@astryxdesign/core/Text";
import {TextInput} from "@astryxdesign/core/TextInput";
import {VStack} from "@astryxdesign/core/VStack";
import {PauseCircleIcon} from "@heroicons/react/24/outline";
import {keepPreviousData, useQuery} from "@tanstack/react-query";
import {getRouteApi} from "@tanstack/react-router";
import {useDeferredValue, useEffect, useState} from "react";
import type {Attendance, TimesheetEntry} from "../api/api";
import {Page} from "../components/Page";
import {AttendanceDialog, BreakDialog, EntryDialog} from "../components/TimeDialogs";
import {facade} from "../data/queries";
import {compact} from "../lib/compact";
import {formatDay, formatHours, formatTime, hoursBetween} from "../lib/time";
import {days, type Break, type Day} from "../lib/timesheets";

const route = getRouteApi("/timesheets");

type Editing = {kind: "entry"; entry: TimesheetEntry} | {kind: "break"; gap: Break} | {kind: "attendance"; attendance: Attendance};

export function TimesheetsPage() {
    const search = route.useSearch();
    const navigate = route.useNavigate();
    const [text, setText] = useState(search.q ?? "");
    const typed = useDeferredValue(text);
    const [editing, setEditing] = useState<Editing | null>(null);

    useEffect(() => {
        const q = typed.trim();
        if (q !== (search.q ?? "")) {
            void navigate({search: compact({q: q || undefined}), replace: true});
        }
    }, [typed, search.q, navigate]);

    const params = {...(search.q ? {search: search.q} : {}), page: search.page ?? 1};
    const {data, isFetching} = useQuery({...facade("timesheets", params), placeholderData: keepPreviousData});

    return (
        <Page
            title="Timesheets"
            subtitle="Your time on jobs, and the clock"
            toolbar={
                <TextInput
                    label="Search timesheets"
                    isLabelHidden
                    type="search"
                    startIcon="search"
                    placeholder="Work order, description, or a day (2026-01-05)"
                    value={text}
                    onChange={setText}
                    hasClear
                    isLoading={isFetching}
                    width="100%"
                />
            }
        >
            <VStack gap={4} paddingBlock={4}>
                {!data ? (
                    <Spinner label="Loading" />
                ) : data.records.length === 0 ? (
                    <EmptyState title="No time yet" description={search.q ? `Nothing matches “${search.q}”.` : "Start a timer on a job and it shows here."} />
                ) : (
                    <>
                        {days(data).map((day) => (
                            <DayCard key={day.date} day={day} onEdit={setEditing} />
                        ))}
                        <HStack hAlign="between" vAlign="center">
                            <Text type="supporting">{`${data.total} entries`}</Text>
                            <Pagination
                                page={data.page}
                                pageSize={data.page_size}
                                totalItems={data.total}
                                variant="compact"
                                onChange={(page) => void navigate({search: (prev) => compact({...prev, page: page > 1 ? page : undefined})})}
                            />
                        </HStack>
                    </>
                )}
            </VStack>
            {editing?.kind === "entry" ? <EntryDialog entry={editing.entry} onClose={() => setEditing(null)} /> : null}
            {editing?.kind === "break" ? <BreakDialog gap={editing.gap} onClose={() => setEditing(null)} /> : null}
            {editing?.kind === "attendance" ? <AttendanceDialog attendance={editing.attendance} onClose={() => setEditing(null)} /> : null}
        </Page>
    );
}

function DayCard({day, onEdit}: {day: Day; onEdit: (editing: Editing) => void}) {
    return (
        <Card>
            <VStack gap={2}>
                <HStack hAlign="between" vAlign="center" wrap="wrap" gap={2}>
                    <Heading level={2}>{formatDay(day.date)}</Heading>
                    <HStack gap={1}>
                        {day.clockedHours !== null ? <Badge label={`Clocked ${formatHours(day.clockedHours)}`} variant="blue" /> : <Badge label="Not clocked" variant="neutral" />}
                        <Badge label={`Jobs ${formatHours(day.jobHours)}`} variant="green" />
                    </HStack>
                </HStack>
                <List hasDividers edge="flush">
                    {(day.attendance?.records ?? []).map((attendance) => (
                        <ListItem
                            key={`a${attendance.id}`}
                            label="Clocked in"
                            description={<Text type="supporting" hasTabularNumbers>{`${formatTime(attendance.check_in)} – ${attendance.check_out ? formatTime(attendance.check_out) : "now"}`}</Text>}
                            startContent={<Icon icon="clock" color="secondary" />}
                            {...(attendance.check_out ? {onClick: () => onEdit({kind: "attendance", attendance})} : {})}
                        />
                    ))}
                    {day.timeline.map((moment) =>
                        moment.kind === "entry" ? (
                            <EntryRow key={`e${moment.entry.id}`} entry={moment.entry} onEdit={onEdit} />
                        ) : (
                            <BreakRow key={moment.gap.kind === "clock" ? `c${moment.gap.attendanceId}` : `j${moment.gap.lineId}-${moment.gap.afterId}`} gap={moment.gap} onEdit={onEdit} />
                        )
                    )}
                </List>
            </VStack>
        </Card>
    );
}

function EntryRow({entry, onEdit}: {entry: TimesheetEntry; onEdit: (editing: Editing) => void}) {
    return (
        <ListItem
            label={entry.job?.name ?? entry.job_ref}
            description={
                <Text type="supporting" hasTabularNumbers maxLines={2}>
                    {[entry.start ? `${formatTime(entry.start)} – ${entry.end ? formatTime(entry.end) : "running"}` : null, entry.job_ref, entry.service?.name]
                        .filter(Boolean)
                        .join(" · ")}
                </Text>
            }
            endContent={
                <Text weight="semibold" hasTabularNumbers>
                    {entry.end ? formatHours(entry.hours) : "running"}
                </Text>
            }
            onClick={() => onEdit({kind: "entry", entry})}
        />
    );
}

function BreakRow({gap, onEdit}: {gap: Break; onEdit: (editing: Editing) => void}) {
    return (
        <ListItem
            label="Break"
            description={<Text type="supporting" hasTabularNumbers>{`${formatTime(gap.start)} – ${formatTime(gap.end)}`}</Text>}
            startContent={<Icon icon={PauseCircleIcon} color="secondary" />}
            endContent={<Text hasTabularNumbers>{formatHours(hoursBetween(gap.start, gap.end))}</Text>}
            onClick={() => onEdit({kind: "break", gap})}
        />
    );
}

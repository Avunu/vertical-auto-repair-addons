/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The timesheet dialogs: an entry (its times and job; moving part of it to
 * another job; cutting a break out of it), a break, a clocked period. Each
 * picks times on the device's wall clock and sends them as instants.
 */
import {AlertDialog} from "@astryxdesign/core/AlertDialog";
import {Button} from "@astryxdesign/core/Button";
import {DateTimeInput, type ISODateTimeString} from "@astryxdesign/core/DateTimeInput";
import {Dialog, DialogHeader} from "@astryxdesign/core/Dialog";
import {FormLayout} from "@astryxdesign/core/FormLayout";
import {HStack} from "@astryxdesign/core/HStack";
import {SegmentedControl, SegmentedControlItem} from "@astryxdesign/core/SegmentedControl";
import {Selector} from "@astryxdesign/core/Selector";
import {Spinner} from "@astryxdesign/core/Spinner";
import {Text} from "@astryxdesign/core/Text";
import {useQuery} from "@tanstack/react-query";
import {useState} from "react";
import type {Attendance, IsoDateTime, JobChoice, TimesheetEntry} from "../api/api";
import {facade, useFacadeMutation} from "../data/queries";
import type {Break} from "../lib/timesheets";
import {epochMs, formatHours, fromLocalInput, hoursBetween, toLocalInput} from "../lib/time";
import {useNotify} from "./feedback";

const NO_SERVICE = "none";

/** A start and an end, on the wall clock; `interval` is set once both are valid and in order. */
function useInterval(start: IsoDateTime | null, end: IsoDateTime | null) {
    const [from, setFrom] = useState<ISODateTimeString | undefined>(start ? toLocalInput(start) : undefined);
    const [to, setTo] = useState<ISODateTimeString | undefined>(end ? toLocalInput(end) : undefined);
    const startAt = fromLocalInput(from);
    const endAt = fromLocalInput(to);
    const ordered = startAt !== undefined && endAt !== undefined && epochMs(endAt) > epochMs(startAt);
    const fields = (
        <>
            <DateTimeInput label="Start" value={from} onChange={setFrom} width="100%" isRequired />
            <DateTimeInput
                label="End"
                value={to}
                onChange={setTo}
                width="100%"
                isRequired
                {...(startAt && endAt && !ordered ? {status: {type: "error" as const, message: "The end has to come after the start."}} : {})}
            />
            {ordered ? <Text type="supporting">{`${formatHours(hoursBetween(startAt, endAt))} long`}</Text> : null}
        </>
    );
    return {fields, interval: ordered ? {start: startAt, end: endAt} : null};
}

function JobFields({jobs, jobId, serviceId, onJob, onService}: {jobs: JobChoice[]; jobId: string; serviceId: string; onJob: (id: string) => void; onService: (id: string) => void}) {
    const job = jobs.find((j) => String(j.id) === jobId);
    return (
        <>
            <Selector
                label="Job"
                hasSearch
                presentation="adaptive"
                value={jobId}
                onChange={(value) => {
                    onJob(value);
                    onService(NO_SERVICE);
                }}
                options={jobs.map((j) => ({value: String(j.id), label: j.name, description: [j.ref, j.customer].filter(Boolean).join(" · ")}))}
                width="100%"
            />
            <Selector
                label="Service"
                value={serviceId}
                onChange={onService}
                options={[{value: NO_SERVICE, label: "No particular service"}, ...(job?.services ?? []).map((s) => ({value: String(s.id), label: s.name}))]}
                width="100%"
            />
        </>
    );
}

const serviceParam = (serviceId: string) => (serviceId === NO_SERVICE ? {} : {service_id: Number(serviceId)});

type EntryMode = "edit" | "move" | "break";

export function EntryDialog({entry, onClose}: {entry: TimesheetEntry; onClose: () => void}) {
    const [mode, setMode] = useState<EntryMode>("edit");
    const detail = useQuery(facade("timesheet", {line_id: entry.id}));
    const running = entry.end === null;
    return (
        <Dialog isOpen onOpenChange={(open) => !open && onClose()} purpose="form" width={560}>
            <DialogHeader title={entry.job?.name ?? entry.job_ref} subtitle={[entry.job_ref, entry.service?.name].filter(Boolean).join(" · ")} onOpenChange={(open) => !open && onClose()} />
            {running ? (
                <Text>This timer is still running. Stop it to change the entry.</Text>
            ) : !detail.data ? (
                <Spinner label="Loading" />
            ) : (
                <FormLayout>
                    <SegmentedControl label="What to do" value={mode} onChange={(value) => setMode(value === "move" || value === "break" ? value : "edit")} layout="fill">
                        <SegmentedControlItem value="edit" label="Edit" />
                        <SegmentedControlItem value="move" label="Move part" />
                        <SegmentedControlItem value="break" label="Add break" />
                    </SegmentedControl>
                    {mode === "edit" ? (
                        <EditEntry entry={entry} jobs={detail.data.jobs} onClose={onClose} />
                    ) : mode === "move" ? (
                        <MoveEntry entry={entry} jobs={detail.data.jobs} onClose={onClose} />
                    ) : (
                        <BreakEntry entry={entry} onClose={onClose} />
                    )}
                </FormLayout>
            )}
        </Dialog>
    );
}

function EditEntry({entry, jobs, onClose}: {entry: TimesheetEntry; jobs: JobChoice[]; onClose: () => void}) {
    const notify = useNotify();
    const {fields, interval} = useInterval(entry.start, entry.end);
    const [jobId, setJobId] = useState(String(entry.job?.id ?? ""));
    const [serviceId, setServiceId] = useState(entry.service ? String(entry.service.id) : NO_SERVICE);
    const [confirmDelete, setConfirmDelete] = useState(false);
    const update = useFacadeMutation("update_timesheet", {onSuccess: () => (notify.done("Entry updated."), onClose())});
    const remove = useFacadeMutation("delete_timesheet", {onSuccess: (notice) => (notify.done(notice.message), onClose())});
    return (
        <>
            {fields}
            <JobFields jobs={jobs} jobId={jobId} serviceId={serviceId} onJob={setJobId} onService={setServiceId} />
            <HStack gap={2} hAlign="between">
                <Button label="Delete" variant="destructive" onClick={() => setConfirmDelete(true)} />
                <HStack gap={2}>
                    <Button label="Cancel" variant="ghost" onClick={onClose} />
                    <Button
                        label="Save"
                        variant="primary"
                        isDisabled={!interval}
                        isLoading={update.isPending}
                        onClick={() =>
                            interval &&
                            update.mutate(
                                {line_id: entry.id, start: interval.start, end: interval.end, job_id: Number(jobId), ...serviceParam(serviceId)},
                                {onError: notify.failed}
                            )
                        }
                    />
                </HStack>
            </HStack>
            <AlertDialog
                isOpen={confirmDelete}
                onOpenChange={setConfirmDelete}
                title="Delete this entry?"
                description={`${formatHours(entry.hours)} on ${entry.job?.name ?? entry.job_ref} goes. This can't be undone.`}
                actionLabel="Delete"
                isActionLoading={remove.isPending}
                onAction={() => remove.mutate({line_id: entry.id}, {onError: notify.failed})}
            />
        </>
    );
}

function MoveEntry({entry, jobs, onClose}: {entry: TimesheetEntry; jobs: JobChoice[]; onClose: () => void}) {
    const notify = useNotify();
    const {fields, interval} = useInterval(entry.start, entry.end);
    const other = jobs.find((job) => job.id !== entry.job?.id);
    const [jobId, setJobId] = useState(String(other?.id ?? entry.job?.id ?? ""));
    const [serviceId, setServiceId] = useState(NO_SERVICE);
    const split = useFacadeMutation("split_timesheet", {onSuccess: (notice) => (notify.done(notice.message), onClose())});
    return (
        <>
            <Text type="supporting">Pick the part of this entry that was really another job: it moves there, and the rest stays.</Text>
            {fields}
            <JobFields jobs={jobs} jobId={jobId} serviceId={serviceId} onJob={setJobId} onService={setServiceId} />
            <HStack gap={2} hAlign="end">
                <Button label="Cancel" variant="ghost" onClick={onClose} />
                <Button
                    label="Move"
                    variant="primary"
                    isDisabled={!interval}
                    isLoading={split.isPending}
                    onClick={() =>
                        interval &&
                        split.mutate({line_id: entry.id, job_id: Number(jobId), start: interval.start, end: interval.end, ...serviceParam(serviceId)}, {onError: notify.failed})
                    }
                />
            </HStack>
        </>
    );
}

function BreakEntry({entry, onClose}: {entry: TimesheetEntry; onClose: () => void}) {
    const notify = useNotify();
    const {fields, interval} = useInterval(null, null);
    const add = useFacadeMutation("add_break", {onSuccess: (notice) => (notify.done(notice.message), onClose())});
    return (
        <>
            <Text type="supporting">The break comes out of this entry, and off the clocked day as well.</Text>
            {fields}
            <HStack gap={2} hAlign="end">
                <Button label="Cancel" variant="ghost" onClick={onClose} />
                <Button
                    label="Add break"
                    variant="primary"
                    isDisabled={!interval}
                    isLoading={add.isPending}
                    onClick={() => interval && add.mutate({line_id: entry.id, start: interval.start, end: interval.end}, {onError: notify.failed})}
                />
            </HStack>
        </>
    );
}

export function BreakDialog({gap, onClose}: {gap: Break; onClose: () => void}) {
    const notify = useNotify();
    const {fields, interval} = useInterval(gap.start, gap.end);
    const done = {onSuccess: (notice: {message: string}) => (notify.done(notice.message), onClose())};
    const moveClock = useFacadeMutation("update_break", done);
    const moveJob = useFacadeMutation("update_job_break", done);
    const removeClock = useFacadeMutation("delete_break", done);
    const removeJob = useFacadeMutation("delete_job_break", done);
    const save = (): void => {
        if (!interval) {
            return;
        }
        if (gap.kind === "clock") {
            moveClock.mutate({attendance_id: gap.attendanceId, ...interval}, {onError: notify.failed});
        } else {
            moveJob.mutate({line_id: gap.lineId, after_id: gap.afterId, ...interval}, {onError: notify.failed});
        }
    };
    const remove = (): void => {
        if (gap.kind === "clock") {
            removeClock.mutate({attendance_id: gap.attendanceId}, {onError: notify.failed});
        } else {
            removeJob.mutate({line_id: gap.lineId, after_id: gap.afterId}, {onError: notify.failed});
        }
    };
    return (
        <Dialog isOpen onOpenChange={(open) => !open && onClose()} purpose="form" width={480}>
            <DialogHeader title="Break" subtitle={gap.kind === "clock" ? "Clocked out, then back in" : "Between two parts of a job"} onOpenChange={(open) => !open && onClose()} />
            <FormLayout>
                {fields}
                <HStack gap={2} hAlign="between">
                    <Button label="Remove break" variant="destructive" isLoading={removeClock.isPending || removeJob.isPending} onClick={remove} />
                    <HStack gap={2}>
                        <Button label="Cancel" variant="ghost" onClick={onClose} />
                        <Button label="Save" variant="primary" isDisabled={!interval} isLoading={moveClock.isPending || moveJob.isPending} onClick={save} />
                    </HStack>
                </HStack>
            </FormLayout>
        </Dialog>
    );
}

export function AttendanceDialog({attendance, onClose}: {attendance: Attendance; onClose: () => void}) {
    const notify = useNotify();
    const {fields, interval} = useInterval(attendance.check_in, attendance.check_out);
    const update = useFacadeMutation("update_attendance", {onSuccess: () => (notify.done("Clock times updated."), onClose())});
    return (
        <Dialog isOpen onOpenChange={(open) => !open && onClose()} purpose="form" width={480}>
            <DialogHeader title="Clocked in" subtitle="Correct when you clocked in and out" onOpenChange={(open) => !open && onClose()} />
            <FormLayout>
                {fields}
                <HStack gap={2} hAlign="end">
                    <Button label="Cancel" variant="ghost" onClick={onClose} />
                    <Button
                        label="Save"
                        variant="primary"
                        isDisabled={!interval}
                        isLoading={update.isPending}
                        onClick={() => interval && update.mutate({attendance_id: attendance.id, ...interval}, {onError: notify.failed})}
                    />
                </HStack>
            </FormLayout>
        </Dialog>
    );
}

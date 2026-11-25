/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The job hub: what the customer said, the services with their timers, the
 * notes, and the vehicle. Start and finish the repair from its header.
 */
import {AlertDialog} from "@astryxdesign/core/AlertDialog";
import {Badge} from "@astryxdesign/core/Badge";
import {Button} from "@astryxdesign/core/Button";
import {Card} from "@astryxdesign/core/Card";
import {EmptyState} from "@astryxdesign/core/EmptyState";
import {Heading} from "@astryxdesign/core/Heading";
import {HStack} from "@astryxdesign/core/HStack";
import {Icon} from "@astryxdesign/core/Icon";
import {List, ListItem} from "@astryxdesign/core/List";
import {MetadataList, MetadataListItem} from "@astryxdesign/core/MetadataList";
import {Text} from "@astryxdesign/core/Text";
import {TextArea} from "@astryxdesign/core/TextArea";
import {Timer} from "@astryxdesign/core/Timer";
import {VStack} from "@astryxdesign/core/VStack";
import {Grid} from "@astryxdesign/core/Grid";
import {PlayIcon} from "@heroicons/react/24/solid";
import * as stylex from "@stylexjs/stylex";
import {useSuspenseQuery} from "@tanstack/react-query";
import {getRouteApi} from "@tanstack/react-router";
import {useState} from "react";
import type {JobDetail, Service} from "../api/api";
import {useNotify} from "../components/feedback";
import {JobTabs} from "../components/JobTabs";
import {useHref} from "../components/links";
import {Page} from "../components/Page";
import {facade, useCacheWriter, useFacadeMutation} from "../data/queries";
import {STATE_BADGE} from "../lib/jobs";
import {epochMs, formatHours} from "../lib/time";

const route = getRouteApi("/jobs/$jobId");

const styles = stylex.create({
    // Notes are plain text with line breaks; keep them.
    lines: {whiteSpace: "pre-line"},
});

export function JobPage() {
    const {jobId} = route.useParams();
    const {data: job} = useSuspenseQuery(facade("job", {repair_id: jobId}));
    const href = useHref();
    const writeCache = useCacheWriter();
    const notify = useNotify();
    const [confirmFinish, setConfirmFinish] = useState(false);
    const keep = (result: JobDetail): void => writeCache("job", {repair_id: jobId}, result);

    const start = useFacadeMutation("start_repair", {onSuccess: (result) => (keep(result), notify.done("Repair started."))});
    const finish = useFacadeMutation("finish", {
        onSuccess: (result) => {
            keep(result);
            setConfirmFinish(false);
            notify.done(`${result.name} is finished.`);
        },
    });

    return (
        <Page
            title={job.label}
            subtitle={[job.name, job.partner?.name].filter(Boolean).join(" · ")}
            backHref={href({to: "/jobs"})}
            backLabel="My Jobs"
            actions={
                <>
                    {job.stage ? <Badge label={job.stage.name} variant="blue" /> : <Badge label={job.state_label} variant={STATE_BADGE[job.state]} />}
                    {job.can_start ? (
                        <Button
                            label="Start repair"
                            variant="primary"
                            isLoading={start.isPending}
                            onClick={() => start.mutate({repair_id: job.id}, {onError: notify.failed})}
                        />
                    ) : null}
                    {job.can_finish ? <Button label="Finish" variant="primary" onClick={() => setConfirmFinish(true)} /> : null}
                </>
            }
            toolbar={<JobTabs job={job} current="overview" />}
        >
            <VStack gap={4} paddingBlock={4}>
                {job.customer_concern || job.repair_request ? (
                    <Card>
                        <VStack gap={2}>
                            <Heading level={2}>Concern</Heading>
                            {job.customer_concern ? <Text textWrap="pretty">{job.customer_concern}</Text> : null}
                            {job.repair_request ? <Text type="supporting">{job.repair_request}</Text> : null}
                        </VStack>
                    </Card>
                ) : null}
                <Services job={job} onChange={keep} />
                <Grid columns={{minWidth: 320, max: 2}} gap={4}>
                    <Notes job={job} onChange={keep} />
                    <VehicleCard job={job} />
                </Grid>
            </VStack>
            <AlertDialog
                isOpen={confirmFinish}
                onOpenChange={setConfirmFinish}
                title={`Finish ${job.name}?`}
                description={
                    job.timer_running
                        ? "Your timer on this job stops, and the job is marked repaired."
                        : "The job is marked repaired, and leaves your list."
                }
                actionLabel="Finish"
                actionVariant="primary"
                isActionLoading={finish.isPending}
                onAction={() => finish.mutate({repair_id: job.id}, {onError: notify.failed})}
            />
        </Page>
    );
}

function Services({job, onChange}: {job: JobDetail; onChange: (job: JobDetail) => void}) {
    const notify = useNotify();
    const start = useFacadeMutation("timer_start", {
        onSuccess: (result, params) => {
            onChange(result.job);
            const service = result.job.services.find((s) => s.id === params.service_id);
            const parts = [`Started ${service?.name ?? "the timer"}.`];
            if (result.stopped) {
                parts.push(`Stopped ${result.stopped.service_name} on ${result.stopped.job_label}.`);
            }
            if (result.clocked_in) {
                parts.push("You're clocked in for the day; clock out when you leave.");
            }
            notify.done(parts.join(" "));
        },
    });
    const stop = useFacadeMutation("timer_stop", {onSuccess: (result) => onChange(result)});
    const busy = start.isPending || stop.isPending ? (start.variables ?? stop.variables)?.service_id : undefined;

    if (job.services.length === 0) {
        return (
            <Card>
                <EmptyState
                    isCompact
                    title="No accepted services"
                    description="The office hasn't accepted any work on this job yet, so there is nothing to time."
                />
            </Card>
        );
    }
    return (
        <VStack>
            <List
                hasDividers
                edge="flush"
                density="spacious"
                header={<Heading level={2}>Services</Heading>}
            >
                {job.services.map((service) => (
                    <ListItem
                        key={service.id}
                        itemKey={service.id}
                        label={service.name}
                        description={<ServiceHours service={service} />}
                        endContent={
                            service.timer.running && service.timer.started_at ? (
                                <HStack gap={3} vAlign="center">
                                    <Timer startTime={epochMs(service.timer.started_at)} format="clock" type="large" color="primary" />
                                    <Button
                                        label="Stop"
                                        variant="destructive"
                                        size="lg"
                                        icon={<Icon icon="stop" />}
                                        isLoading={busy === service.id}
                                        onClick={() => stop.mutate({repair_id: job.id, service_id: service.id}, {onError: notify.failed})}
                                    />
                                </HStack>
                            ) : (
                                <Button
                                    label="Start"
                                    variant="primary"
                                    size="lg"
                                    icon={<Icon icon={PlayIcon} />}
                                    isLoading={busy === service.id}
                                    isDisabled={busy !== undefined}
                                    onClick={() => start.mutate({repair_id: job.id, service_id: service.id}, {onError: notify.failed})}
                                />
                            )
                        }
                    />
                ))}
            </List>
        </VStack>
    );
}

function ServiceHours({service}: {service: Service}) {
    const parts = [`Mine ${formatHours(service.my_hours)}`, `All ${formatHours(service.actual_hours)}`];
    if (service.estimated_hours) {
        parts.push(`Estimate ${formatHours(service.estimated_hours)}`);
    }
    const over = service.estimated_hours > 0 && service.actual_hours > service.estimated_hours;
    return (
        <Text type="supporting" color={over ? "accent" : "secondary"} hasTabularNumbers>
            {parts.join(" · ")}
        </Text>
    );
}

function Notes({job, onChange}: {job: JobDetail; onChange: (job: JobDetail) => void}) {
    const notify = useNotify();
    const [note, setNote] = useState("");
    const add = useFacadeMutation("add_note", {
        onSuccess: (result) => {
            onChange(result);
            setNote("");
            notify.done("Note added.");
        },
    });
    return (
        <Card>
            <VStack gap={3}>
                <Heading level={2}>Notes</Heading>
                {job.internal_notes ? (
                    <Text textWrap="pretty" display="block" xstyle={styles.lines}>
                        {job.internal_notes}
                    </Text>
                ) : (
                    <Text type="supporting">No notes yet.</Text>
                )}
                <TextArea label="Add a note" value={note} onChange={setNote} rows={3} placeholder="What you found, what it needs…" />
                <HStack hAlign="end">
                    <Button
                        label="Add note"
                        isDisabled={!note.trim()}
                        isLoading={add.isPending}
                        onClick={() => add.mutate({repair_id: job.id, note}, {onError: notify.failed})}
                    />
                </HStack>
            </VStack>
        </Card>
    );
}

function VehicleCard({job}: {job: JobDetail}) {
    const vehicle = job.vehicle;
    return (
        <Card>
            <VStack gap={3}>
                <Heading level={2}>Vehicle</Heading>
                {vehicle ? (
                    <MetadataList>
                        {vehicle.license_plate ? <MetadataListItem label="Plate">{vehicle.license_plate}</MetadataListItem> : null}
                        {vehicle.vin ? <MetadataListItem label="VIN">{vehicle.vin}</MetadataListItem> : null}
                        {vehicle.model_year ? <MetadataListItem label="Year">{vehicle.model_year}</MetadataListItem> : null}
                        {vehicle.unit_number ? <MetadataListItem label="Unit">{vehicle.unit_number}</MetadataListItem> : null}
                        {job.odometer_in ? (
                            <MetadataListItem label="Odometer in">{`${job.odometer_in.toLocaleString()} ${job.odometer_unit}`}</MetadataListItem>
                        ) : null}
                        {job.under_warranty ? <MetadataListItem label="Warranty">Under warranty</MetadataListItem> : null}
                        {job.sale_order ? <MetadataListItem label="Quote">{job.sale_order.name}</MetadataListItem> : null}
                    </MetadataList>
                ) : (
                    <Text type="supporting">No vehicle on this job.</Text>
                )}
            </VStack>
        </Card>
    );
}

/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * My Jobs: the technician's own jobs first, then what they can pick up
 * (shared through an appointment type, or nobody's yet). Filter by typing;
 * scan a work order, plate or VIN to open its job.
 */
import {Badge} from "@astryxdesign/core/Badge";
import {Button} from "@astryxdesign/core/Button";
import {EmptyState} from "@astryxdesign/core/EmptyState";
import {HStack} from "@astryxdesign/core/HStack";
import {Icon} from "@astryxdesign/core/Icon";
import {List, ListItem} from "@astryxdesign/core/List";
import {StatusDot} from "@astryxdesign/core/StatusDot";
import {Text} from "@astryxdesign/core/Text";
import {TextInput} from "@astryxdesign/core/TextInput";
import {VStack} from "@astryxdesign/core/VStack";
import {FlagIcon, QrCodeIcon} from "@heroicons/react/24/solid";
import {useSuspenseQuery} from "@tanstack/react-query";
import {getRouteApi} from "@tanstack/react-router";
import {useDeferredValue, useEffect, useState} from "react";
import type {JobSummary} from "../api/api";
import {useHref} from "../components/links";
import {Page} from "../components/Page";
import {useOpenScanner} from "../components/scan";
import {facade} from "../data/queries";
import {STATE_BADGE} from "../lib/jobs";

const route = getRouteApi("/jobs");

/** What a typed filter matches: everything printed on a work order or a car. */
export function matches(job: JobSummary, text: string): boolean {
    const needle = text.trim().toLowerCase();
    if (!needle) {
        return true;
    }
    return [job.label, job.name, job.partner?.name, job.vehicle?.license_plate, job.vehicle?.vin, job.vehicle?.unit_number, job.customer_concern]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLowerCase().includes(needle));
}

export function JobsPage() {
    const {data: jobs} = useSuspenseQuery(facade("jobs", {}));
    const search = route.useSearch();
    const navigate = route.useNavigate();
    const openScanner = useOpenScanner();
    const [filter, setFilter] = useState("");
    const deferred = useDeferredValue(filter);

    // The home-screen "Scan" shortcut lands here with ?scan=1.
    useEffect(() => {
        if (search.scan) {
            openScanner("Scan a work order, plate or VIN");
            void navigate({search: {}, replace: true});
        }
    }, [search.scan, openScanner, navigate]);

    const shown = jobs.filter((job) => matches(job, deferred));
    const mine = shown.filter((job) => job.is_mine);
    const others = shown.filter((job) => !job.is_mine);

    return (
        <Page
            title="My Jobs"
            subtitle={`${jobs.length} open`}
            actions={<Button label="Scan" icon={<Icon icon={QrCodeIcon} />} onClick={() => openScanner("Scan a work order, plate or VIN")} />}
            toolbar={
                <TextInput
                    label="Filter jobs"
                    isLabelHidden
                    type="search"
                    startIcon="search"
                    placeholder="Plate, VIN, customer, work order…"
                    value={filter}
                    onChange={setFilter}
                    hasClear
                    enterKeyHint="search"
                    width="100%"
                />
            }
        >
            {jobs.length === 0 ? (
                <EmptyState title="No jobs right now" description="Jobs assigned to you, or that you can pick up, show here." />
            ) : shown.length === 0 ? (
                <EmptyState title="Nothing matches" description={`No job matches “${deferred}”.`} />
            ) : (
                <VStack gap={4}>
                    {mine.length > 0 ? <JobList title="Mine" jobs={mine} /> : null}
                    {others.length > 0 ? <JobList title="Shared and unassigned" jobs={others} /> : null}
                </VStack>
            )}
        </Page>
    );
}

function JobList({title, jobs}: {title: string; jobs: JobSummary[]}) {
    const href = useHref();
    return (
        <VStack>
            <List
                hasDividers
                edge="flush"
                density="spacious"
                header={
                    <Text type="label" color="secondary">
                        {title}
                    </Text>
                }
            >
                {jobs.map((job) => (
                    <ListItem
                        key={job.id}
                        itemKey={job.id}
                        href={href({to: "/jobs/$jobId", params: {jobId: job.id}})}
                        label={job.label}
                        description={
                            <VStack gap={0.5}>
                                <Text type="supporting" maxLines={1}>
                                    {[job.name, job.partner?.name, job.technician && !job.is_mine ? job.technician.name : null].filter(Boolean).join(" · ")}
                                </Text>
                                {job.customer_concern ? (
                                    <Text type="supporting" maxLines={2}>
                                        {job.customer_concern}
                                    </Text>
                                ) : null}
                            </VStack>
                        }
                        startContent={
                            job.timer_running ? (
                                <StatusDot variant="success" label="Your timer is running" isPulsing />
                            ) : job.priority ? (
                                <Icon icon={FlagIcon} color="error" label="Priority" />
                            ) : null
                        }
                        endContent={
                            <HStack gap={1} vAlign="center" wrap="wrap">
                                {/* The stage says more ("Waiting for parts"); the state when there is none. */}
                                {job.stage ? <Badge label={job.stage.name} variant="blue" /> : <Badge label={job.state_label} variant={STATE_BADGE[job.state]} />}
                                {job.parts_total > 0 ? <Badge label={`Parts ${job.parts_done}/${job.parts_total}`} variant="neutral" /> : null}
                            </HStack>
                        }
                    />
                ))}
            </List>
        </VStack>
    );
}

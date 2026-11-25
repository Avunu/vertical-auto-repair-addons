/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The frame around every screen: navigation, the running job timer (with its
 * Stop, from anywhere), the time clock, and what the device should know - a
 * banner when offline or when a new version is ready, the screen kept awake
 * and the app icon badged while a timer runs.
 */
import {AppShell} from "@astryxdesign/core/AppShell";
import {Banner} from "@astryxdesign/core/Banner";
import {Button} from "@astryxdesign/core/Button";
import {HStack} from "@astryxdesign/core/HStack";
import {Icon} from "@astryxdesign/core/Icon";
import {IconButton} from "@astryxdesign/core/IconButton";
import {StatusDot} from "@astryxdesign/core/StatusDot";
import {Text} from "@astryxdesign/core/Text";
import {Timer} from "@astryxdesign/core/Timer";
import {TopNav, TopNavHeading, TopNavItem} from "@astryxdesign/core/TopNav";
import {VStack} from "@astryxdesign/core/VStack";
import {QrCodeIcon} from "@heroicons/react/24/outline";
import {useQuery, useSuspenseQuery} from "@tanstack/react-query";
import type {RunningTimer as RunningTimerData} from "../api/api";
import {Outlet, useLocation, useNavigate} from "@tanstack/react-router";
import {useEffect} from "react";
import {MODEL, odoo} from "../data/odoo";
import {facade, useFacadeMutation} from "../data/queries";
import {useAppBadge, useOnline, useUpdateAvailable, useWakeLock} from "../lib/device";
import {epochMs, formatHours} from "../lib/time";
import {useNotify} from "./feedback";
import {useHref} from "./links";
import {useOpenScanner, useScanHandler} from "./scan";

/** How often the header asks about the shift: the timer itself ticks locally. */
const SHIFT_POLL_MS = 60_000;

export function Shell() {
    const {data: session} = useSuspenseQuery(facade("session", {}));
    const {data: shift} = useQuery({...facade("shift", {}), refetchInterval: SHIFT_POLL_MS});
    const href = useHref();
    const {pathname} = useLocation();
    const online = useOnline();
    const update = useUpdateAvailable();
    const openScanner = useOpenScanner();
    const navigate = useNavigate();
    const notify = useNotify();
    const running = shift?.running ?? null;
    useWakeLock(running !== null);
    useAppBadge(running !== null);
    // Up, with a session: what the browser tests wait for.
    useEffect(() => {
        document.documentElement.dataset["appReady"] = "";
    }, []);

    // Anywhere without a scanner of its own, a code opens its job.
    useScanHandler((code) => {
        void (async () => {
            try {
                const job = await odoo.call(MODEL, "find_job", {code});
                if (job) {
                    await navigate({to: "/jobs/$jobId", params: {jobId: job.id}});
                } else {
                    notify.failed(new Error(`No job matches ${code}.`));
                }
            } catch (error) {
                notify.failed(error);
            }
        })();
    });

    const banner = !online ? (
        <Banner
            status="warning"
            container="section"
            title="Offline"
            description="Showing what this device last saw. Changes wait until you're back online."
        />
    ) : update.available ? (
        <Banner
            status="info"
            container="section"
            title="A new version is ready"
            endContent={<Button label="Update" variant="primary" size="sm" onClick={update.apply} />}
        />
    ) : null;

    return (
        <AppShell
            contentPadding={0}
            banner={banner}
            topNav={
                <TopNav
                    heading={<TopNavHeading heading="Technician" subheading={session.name} headingHref={href({to: "/jobs"})} />}
                    startContent={
                        <>
                            <TopNavItem label="My Jobs" href={href({to: "/jobs"})} isSelected={pathname.startsWith("/jobs") || pathname.startsWith("/inspections")} />
                            <TopNavItem label="Timesheets" href={href({to: "/timesheets"})} isSelected={pathname.startsWith("/timesheets")} />
                        </>
                    }
                    endContent={
                        <HStack gap={2} vAlign="center">
                            {running ? <RunningTimer running={running} /> : null}
                            <ClockButton clockedIn={shift?.clocked_in ?? false} hoursToday={shift?.hours_today ?? 0} hasEmployee={session.employee !== null} />
                            <IconButton label="Scan" icon={<Icon icon={QrCodeIcon} />} onClick={() => openScanner()} />
                        </HStack>
                    }
                />
            }
        >
            <Outlet />
        </AppShell>
    );
}

function RunningTimer({running}: {running: RunningTimerData}) {
    const href = useHref();
    const notify = useNotify();
    const stop = useFacadeMutation("stop_running", {
        onSuccess: () => notify.done(`Stopped ${running.service_name}.`),
    });
    return (
        <HStack gap={2} vAlign="center" data-running-timer="">
            <StatusDot variant="success" label="Timer running" isPulsing />
            <Button
                variant="ghost"
                label={`${running.service_name} on ${running.job_label}`}
                href={href({to: "/jobs/$jobId", params: {jobId: running.repair_id}})}
            >
                <VStack gap={0}>
                    <Timer startTime={epochMs(running.started_at)} format="clock" type="label" color="primary" />
                    <Text type="supporting" maxLines={1}>
                        {running.service_name}
                    </Text>
                </VStack>
            </Button>
            <IconButton
                label="Stop timer"
                icon={<Icon icon="stop" />}
                variant="destructive"
                isLoading={stop.isPending}
                onClick={() => stop.mutate({}, {onError: notify.failed})}
            />
        </HStack>
    );
}

function ClockButton({clockedIn, hoursToday, hasEmployee}: {clockedIn: boolean; hoursToday: number; hasEmployee: boolean}) {
    const notify = useNotify();
    const toggle = useFacadeMutation("clock_toggle", {
        onSuccess: (shift) => notify.done(shift.clocked_in ? "Clocked in." : `Clocked out. ${formatHours(shift.hours_today)} today.`),
    });
    return (
        <Button
            label={clockedIn ? "Clock out" : "Clock in"}
            variant={clockedIn ? "secondary" : "primary"}
            icon={<Icon icon="clock" />}
            tooltip={`${formatHours(hoursToday)} clocked today`}
            isDisabled={!hasEmployee}
            isLoading={toggle.isPending}
            onClick={() => toggle.mutate({}, {onError: notify.failed})}
        />
    );
}

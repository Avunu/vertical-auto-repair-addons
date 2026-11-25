/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The job's inspections, and starting one from a checklist at the odometer
 * reading on the dash.
 */
import {Badge} from "@astryxdesign/core/Badge";
import {Button} from "@astryxdesign/core/Button";
import {Dialog, DialogHeader} from "@astryxdesign/core/Dialog";
import {EmptyState} from "@astryxdesign/core/EmptyState";
import {FormLayout} from "@astryxdesign/core/FormLayout";
import {HStack} from "@astryxdesign/core/HStack";
import {Icon} from "@astryxdesign/core/Icon";
import {List, ListItem} from "@astryxdesign/core/List";
import {NumberInput} from "@astryxdesign/core/NumberInput";
import {Selector} from "@astryxdesign/core/Selector";
import {Timestamp} from "@astryxdesign/core/Timestamp";
import {VStack} from "@astryxdesign/core/VStack";
import {ClipboardDocumentCheckIcon} from "@heroicons/react/24/outline";
import {useSuspenseQuery} from "@tanstack/react-query";
import {getRouteApi} from "@tanstack/react-router";
import {useState} from "react";
import type {InspectionList, InspectionSummary} from "../api/api";
import {useNotify} from "../components/feedback";
import {JobTabs} from "../components/JobTabs";
import {useHref} from "../components/links";
import {Page} from "../components/Page";
import {facade, useCacheWriter, useFacadeMutation} from "../data/queries";
import {SEVERITY} from "../lib/severity";

const route = getRouteApi("/jobs/$jobId/inspections");

export function InspectionsPage() {
    const {jobId} = route.useParams();
    const {data} = useSuspenseQuery(facade("inspections", {repair_id: jobId}));
    const href = useHref();
    const [starting, setStarting] = useState(false);
    const {job, records} = data;

    return (
        <Page
            title={job.label}
            subtitle={[job.name, job.partner?.name].filter(Boolean).join(" · ")}
            backHref={href({to: "/jobs"})}
            backLabel="My Jobs"
            actions={
                <Button
                    label="New inspection"
                    variant="primary"
                    icon={<Icon icon={ClipboardDocumentCheckIcon} />}
                    isDisabled={!data.has_vehicle || data.templates.length === 0}
                    {...(data.has_vehicle ? {} : {tooltip: "The job has no vehicle to inspect"})}
                    onClick={() => setStarting(true)}
                />
            }
            toolbar={<JobTabs job={job} current="inspections" />}
        >
            <VStack gap={4} paddingBlock={4}>
                {records.length === 0 ? (
                    <EmptyState
                        title="No inspections yet"
                        description={data.has_vehicle ? "Start one from a checklist." : "This job has no vehicle, so it can't be inspected."}
                    />
                ) : (
                    <List hasDividers edge="flush" density="spacious">
                        {records.map((inspection) => (
                            <ListItem
                                key={inspection.id}
                                itemKey={inspection.id}
                                href={href({to: "/inspections/$inspectionId", params: {inspectionId: inspection.id}})}
                                label={inspection.name}
                                description={
                                    <HStack gap={2} vAlign="center" wrap="wrap">
                                        {inspection.date_inspected ? <Timestamp value={inspection.date_inspected} format="date_time" /> : null}
                                        <Counts inspection={inspection} />
                                    </HStack>
                                }
                                endContent={
                                    <HStack gap={1} vAlign="center">
                                        <Badge label={`${inspection.graded_count}/${inspection.line_count}`} variant="neutral" />
                                        <Badge label={inspection.state_label} variant={inspection.state === "confirmed" ? "success" : "info"} />
                                    </HStack>
                                }
                            />
                        ))}
                    </List>
                )}
            </VStack>
            {starting ? <StartDialog data={data} onClose={() => setStarting(false)} /> : null}
        </Page>
    );
}

/** The problems found so far, as the customer's report will colour them. */
export function Counts({inspection}: {inspection: InspectionSummary}) {
    const {counts} = inspection;
    return (
        <HStack gap={1} wrap="wrap">
            {counts.today ? <Badge label={`${counts.today} today`} variant={SEVERITY.today.badge} /> : null}
            {counts.fail_state ? <Badge label={`${counts.fail_state} failed`} variant={SEVERITY.fail_state.badge} /> : null}
            {counts.attention ? <Badge label={`${counts.attention} attention`} variant={SEVERITY.attention.badge} /> : null}
            {counts.future ? <Badge label={`${counts.future} later`} variant={SEVERITY.future.badge} /> : null}
            {counts.good ? <Badge label={`${counts.good} good`} variant={SEVERITY.good.badge} /> : null}
        </HStack>
    );
}

function StartDialog({data, onClose}: {data: InspectionList; onClose: () => void}) {
    const navigate = route.useNavigate();
    const notify = useNotify();
    const writeCache = useCacheWriter();
    const [template, setTemplate] = useState(String(data.templates[0]?.id ?? ""));
    const [odometer, setOdometer] = useState<number | null>(data.default_odometer || null);
    const create = useFacadeMutation("create_inspection", {
        onSuccess: (detail) => {
            writeCache("inspection", {inspection_id: detail.inspection.id}, detail);
            void navigate({to: "/inspections/$inspectionId", params: {inspectionId: detail.inspection.id}});
        },
    });
    return (
        <Dialog isOpen onOpenChange={(open) => !open && onClose()} purpose="form" width={480}>
            <DialogHeader title="New inspection" subtitle={data.job.label} onOpenChange={(open) => !open && onClose()} />
            <FormLayout>
                <Selector
                    label="Checklist"
                    value={template}
                    onChange={setTemplate}
                    options={data.templates.map((t) => ({value: String(t.id), label: t.name}))}
                    width="100%"
                />
                <NumberInput
                    label="Odometer"
                    description="As read on the dash now."
                    value={odometer}
                    onChange={setOdometer}
                    min={1}
                    isIntegerOnly
                    units={data.odometer_unit || null}
                    isRequired
                    width="100%"
                />
                <HStack gap={2} hAlign="end">
                    <Button label="Cancel" variant="ghost" onClick={onClose} />
                    <Button
                        label="Start"
                        variant="primary"
                        isLoading={create.isPending}
                        isDisabled={!template || !odometer}
                        onClick={() =>
                            create.mutate(
                                {repair_id: data.job.id, template_id: Number(template), odometer: odometer ?? 0},
                                {onError: notify.failed}
                            )
                        }
                    />
                </HStack>
            </FormLayout>
        </Dialog>
    );
}

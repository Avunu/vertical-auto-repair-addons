/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * An inspection's checklist, by category, each item with its grade. Grade the
 * next item straight from the header; complete it once everything is graded.
 */
import {Badge} from "@astryxdesign/core/Badge";
import {Button} from "@astryxdesign/core/Button";
import {Heading} from "@astryxdesign/core/Heading";
import {HStack} from "@astryxdesign/core/HStack";
import {Icon} from "@astryxdesign/core/Icon";
import {List, ListItem} from "@astryxdesign/core/List";
import {ProgressBar} from "@astryxdesign/core/ProgressBar";
import {Text} from "@astryxdesign/core/Text";
import {VStack} from "@astryxdesign/core/VStack";
import {CameraIcon, ExclamationTriangleIcon} from "@heroicons/react/24/outline";
import {useSuspenseQuery} from "@tanstack/react-query";
import {getRouteApi} from "@tanstack/react-router";
import type {InspectionLine} from "../api/api";
import {useNotify} from "../components/feedback";
import {useHref} from "../components/links";
import {Page} from "../components/Page";
import {facade, useCacheWriter, useFacadeMutation} from "../data/queries";
import {SEVERITY, SHORT_LABEL} from "../lib/severity";
import {Counts} from "./InspectionsPage";

const route = getRouteApi("/inspections/$inspectionId");

/** The checklist's lines in category groups, in the order the facade sorted them. */
export function byCategory(lines: readonly InspectionLine[]): Array<{key: string; name: string; lines: InspectionLine[]}> {
    const groups = new Map<string, {key: string; name: string; lines: InspectionLine[]}>();
    for (const line of lines) {
        const key = String(line.category?.id ?? "none");
        const group = groups.get(key) ?? {key, name: line.category?.name ?? "Other", lines: []};
        group.lines.push(line);
        groups.set(key, group);
    }
    return [...groups.values()];
}

export function InspectionPage() {
    const {inspectionId} = route.useParams();
    const {data} = useSuspenseQuery(facade("inspection", {inspection_id: inspectionId}));
    const href = useHref();
    const navigate = route.useNavigate();
    const notify = useNotify();
    const writeCache = useCacheWriter();
    const {inspection, job, lines, editable} = data;
    const next = lines.find((line) => !line.severity);

    const confirm = useFacadeMutation("confirm_inspection", {
        onSuccess: (list) => {
            writeCache("inspections", {repair_id: job.id}, list);
            notify.done(`${inspection.name} is complete.`);
            void navigate({to: "/jobs/$jobId/inspections", params: {jobId: job.id}});
        },
    });

    return (
        <Page
            title={inspection.name}
            subtitle={`${job.label} · ${inspection.odometer.toLocaleString()} ${inspection.odometer_unit}`}
            backHref={href({to: "/jobs/$jobId/inspections", params: {jobId: job.id}})}
            backLabel="Inspections"
            actions={
                editable ? (
                    next ? (
                        <Button
                            label="Grade next"
                            variant="primary"
                            href={href({to: "/inspections/$inspectionId/items/$lineId", params: {inspectionId, lineId: next.id}})}
                        />
                    ) : (
                        <Button
                            label="Complete inspection"
                            variant="primary"
                            isLoading={confirm.isPending}
                            onClick={() => confirm.mutate({inspection_id: inspectionId}, {onError: notify.failed})}
                        />
                    )
                ) : (
                    <Badge label={inspection.state_label} variant="success" />
                )
            }
            toolbar={
                <VStack gap={2}>
                    <ProgressBar
                        label="Graded"
                        value={inspection.graded_count}
                        max={Math.max(inspection.line_count, 1)}
                        hasValueLabel
                        formatValueLabel={(value, max) => `${value} of ${max} graded`}
                        variant={next ? "accent" : "success"}
                    />
                    <Counts inspection={inspection} />
                </VStack>
            }
        >
            <VStack gap={4} paddingBlock={4}>
                {byCategory(lines).map((group) => (
                    <VStack key={group.key}>
                        <List hasDividers edge="flush" density="spacious" header={<Heading level={2}>{group.name}</Heading>}>
                            {group.lines.map((line) => (
                                <ListItem
                                    key={line.id}
                                    itemKey={line.id}
                                    href={href({to: "/inspections/$inspectionId/items/$lineId", params: {inspectionId, lineId: line.id}})}
                                    label={line.name}
                                    description={
                                        line.measurement_summary || line.note ? (
                                            <Text type="supporting" maxLines={2}>
                                                {[line.measurement_summary, line.note].filter(Boolean).join(" · ")}
                                            </Text>
                                        ) : undefined
                                    }
                                    startContent={line.severity ? <Icon icon={SEVERITY[line.severity].icon} color={SEVERITY[line.severity].problem ? "error" : "success"} /> : <Icon icon="info" color="tertiary" />}
                                    endContent={
                                        <HStack gap={1} vAlign="center">
                                            {line.measurement_alert ? <Icon icon={ExclamationTriangleIcon} color="warning" label="Out of spec" /> : null}
                                            {line.photo_count ? <Badge label={String(line.photo_count)} icon={<Icon icon={CameraIcon} />} /> : null}
                                            {line.severity ? (
                                                <Badge label={SHORT_LABEL[line.severity]} variant={SEVERITY[line.severity].badge} />
                                            ) : (
                                                <Badge label="To grade" variant="neutral" />
                                            )}
                                        </HStack>
                                    }
                                />
                            ))}
                        </List>
                    </VStack>
                ))}
            </VStack>
        </Page>
    );
}

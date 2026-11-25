/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Grading one checklist item: its measurements, the grade (six big buttons,
 * coloured as on the customer's report), the conditions seen and actions
 * recommended (the item's usual ones first), a note, and photos. Saving
 * moves on to the next ungraded item.
 */
import {Badge} from "@astryxdesign/core/Badge";
import {Button} from "@astryxdesign/core/Button";
import {Card} from "@astryxdesign/core/Card";
import {CheckboxList, CheckboxListItem} from "@astryxdesign/core/CheckboxList";
import {Grid} from "@astryxdesign/core/Grid";
import {Heading} from "@astryxdesign/core/Heading";
import {HStack} from "@astryxdesign/core/HStack";
import {Icon} from "@astryxdesign/core/Icon";
import {Lightbox} from "@astryxdesign/core/Lightbox";
import {NumberInput} from "@astryxdesign/core/NumberInput";
import {Text} from "@astryxdesign/core/Text";
import {TextArea} from "@astryxdesign/core/TextArea";
import {Thumbnail} from "@astryxdesign/core/Thumbnail";
import {ToggleButton, ToggleButtonGroup} from "@astryxdesign/core/ToggleButton";
import {VStack} from "@astryxdesign/core/VStack";
import {useSuspenseQuery} from "@tanstack/react-query";
import {getRouteApi} from "@tanstack/react-router";
import {useState} from "react";
import type {InspectionLineDetail, Measurement} from "../api/api";
import {useNotify} from "../components/feedback";
import {useHref} from "../components/links";
import {Page} from "../components/Page";
import {PhotoButton} from "../components/PhotoButton";
import {facade, useCacheWriter, useFacadeMutation} from "../data/queries";
import {isSeverity, SEVERITY, SEVERITY_ORDER, type Severity} from "../lib/severity";

const route = getRouteApi("/inspections/$inspectionId/items/$lineId");

export function InspectionLinePage() {
    const {inspectionId, lineId} = route.useParams();
    const {data} = useSuspenseQuery(facade("inspection_line", {line_id: lineId}));
    // Remount the form per item, so its state starts from that item.
    return <LineForm key={lineId} inspectionId={inspectionId} detail={data} />;
}

function LineForm({inspectionId, detail}: {inspectionId: number; detail: InspectionLineDetail}) {
    const {line, inspection, editable} = detail;
    const href = useHref();
    const navigate = route.useNavigate();
    const notify = useNotify();
    const writeCache = useCacheWriter();
    const [severity, setSeverity] = useState<Severity | null>(line.severity);
    const [conditions, setConditions] = useState(line.conditions.map((c) => String(c.id)));
    const [actions, setActions] = useState(line.actions.map((a) => String(a.id)));
    const [note, setNote] = useState(line.note);
    const [viewing, setViewing] = useState<number | null>(null);
    const keep = (next: InspectionLineDetail): void => writeCache("inspection_line", {line_id: line.id}, next);

    const grade = useFacadeMutation("grade", {
        onSuccess: (checklist) => {
            writeCache("inspection", {inspection_id: inspectionId}, checklist);
            // On to the next item that still needs a grade, else the checklist.
            const after = checklist.lines.slice(checklist.lines.findIndex((l) => l.id === line.id) + 1);
            const next = after.find((l) => !l.severity) ?? checklist.lines.find((l) => !l.severity);
            void (next
                ? navigate({to: "/inspections/$inspectionId/items/$lineId", params: {inspectionId, lineId: next.id}})
                : navigate({to: "/inspections/$inspectionId", params: {inspectionId}}));
        },
    });
    const measure = useFacadeMutation("set_measurement", {onSuccess: keep});
    const addPhoto = useFacadeMutation("add_photo", {onSuccess: keep});
    const removePhoto = useFacadeMutation("remove_photo", {onSuccess: keep});

    const save = (): void => {
        if (!severity) {
            return;
        }
        grade.mutate(
            {
                line_id: line.id,
                severity,
                condition_ids: conditions.map(Number),
                action_ids: actions.map(Number),
                note,
            },
            {onError: notify.failed}
        );
    };

    const needsPhoto = severity !== null && SEVERITY[severity].problem && detail.photos.length === 0;

    return (
        <Page
            title={line.name}
            subtitle={[...new Set([line.category?.name, inspection.name].filter(Boolean))].join(" · ")}
            backHref={href({to: "/inspections/$inspectionId", params: {inspectionId}})}
            backLabel="Checklist"
            actions={
                editable ? (
                    <Button label="Save and next" variant="primary" size="lg" isDisabled={!severity} isLoading={grade.isPending} onClick={save} />
                ) : (
                    <Badge label="Completed" variant="success" />
                )
            }
        >
            <VStack gap={4} paddingBlock={4}>
                {line.instruction ? <Text type="supporting">{line.instruction}</Text> : null}
                {line.measurements.length ? (
                    <Card>
                        <VStack gap={3}>
                            <Heading level={2}>Measurements</Heading>
                            <Grid columns={{minWidth: 200, max: 4}} gap={3}>
                                {line.measurements.map((m) => (
                                    <MeasurementField
                                        key={m.id}
                                        measurement={m}
                                        isDisabled={!editable}
                                        onCommit={(value) => measure.mutate({measurement_id: m.id, value}, {onError: notify.failed})}
                                    />
                                ))}
                            </Grid>
                        </VStack>
                    </Card>
                ) : null}

                <Card>
                    <VStack gap={3}>
                        <Heading level={2}>Grade</Heading>
                        <ToggleButtonGroup
                            label="Grade"
                            size="lg"
                            value={severity}
                            onChange={(value) => setSeverity(isSeverity(value) ? value : null)}
                            isDisabled={!editable}
                        >
                            {SEVERITY_ORDER.map((value) => {
                                const choice = detail.severities.find((s) => s.value === value);
                                return <ToggleButton key={value} value={value} label={choice?.label ?? value} icon={<Icon icon={SEVERITY[value].icon} />} />;
                            })}
                        </ToggleButtonGroup>
                        {needsPhoto ? <Text type="supporting" color="accent">A problem is clearer to the customer with a photo.</Text> : null}
                    </VStack>
                </Card>

                <Grid columns={{minWidth: 300, max: 2}} gap={4}>
                    <Card>
                        <CheckboxList label="Conditions" value={conditions} onChange={setConditions} isDisabled={!editable} density="compact">
                            {detail.conditions.map((c) => (
                                <CheckboxListItem key={c.id} value={String(c.id)} label={c.name} />
                            ))}
                        </CheckboxList>
                    </Card>
                    <Card>
                        <CheckboxList label="Recommended actions" value={actions} onChange={setActions} isDisabled={!editable} density="compact">
                            {detail.actions.map((a) => (
                                <CheckboxListItem key={a.id} value={String(a.id)} label={a.name} />
                            ))}
                        </CheckboxList>
                    </Card>
                </Grid>

                <Card>
                    <TextArea label="Note for the customer" value={note} onChange={setNote} rows={3} isDisabled={!editable} />
                </Card>

                <Card>
                    <VStack gap={3}>
                        <HStack hAlign="between" vAlign="center">
                            <Heading level={2}>Photos</Heading>
                            <PhotoButton
                                isDisabled={!editable}
                                onPhoto={(image, filename) => addPhoto.mutateAsync({line_id: line.id, image, filename}).catch(notify.failed)}
                            />
                        </HStack>
                        {detail.photos.length ? (
                            <HStack gap={2} wrap="wrap">
                                {detail.photos.map((photo, index) => (
                                    <Thumbnail
                                        key={photo.id}
                                        src={photo.url}
                                        alt={photo.name}
                                        label={photo.name}
                                        onClick={() => setViewing(index)}
                                        {...(editable ? {onRemove: () => removePhoto.mutate({photo_id: photo.id}, {onError: notify.failed})} : {})}
                                    />
                                ))}
                            </HStack>
                        ) : (
                            <Text type="supporting">No photos yet.</Text>
                        )}
                    </VStack>
                </Card>
            </VStack>
            <Lightbox
                isOpen={viewing !== null}
                onOpenChange={(open) => !open && setViewing(null)}
                media={detail.photos.map((photo) => ({src: photo.full_url, alt: photo.name}))}
                index={viewing ?? 0}
                onIndexChange={setViewing}
                hasZoom
            />
        </Page>
    );
}

function MeasurementField({measurement, isDisabled, onCommit}: {measurement: Measurement; isDisabled: boolean; onCommit: (value: number) => void}) {
    const spec = [measurement.spec_min ? `min ${measurement.spec_min}` : null, measurement.spec_max ? `max ${measurement.spec_max}` : null].filter(Boolean).join(", ");
    return (
        <NumberInput
            label={[measurement.name, measurement.position !== "none" ? measurement.position_label : null].filter(Boolean).join(" · ")}
            value={measurement.value || null}
            onChange={(value) => onCommit(value)}
            min={0}
            step={0.5}
            units={measurement.uom_label || null}
            isDisabled={isDisabled}
            {...(spec ? {description: spec} : {})}
            {...(measurement.out_of_spec ? {status: {type: "warning" as const, message: "Out of spec"}} : {})}
            width="100%"
        />
    );
}

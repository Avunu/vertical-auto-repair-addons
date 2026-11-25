/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The job's parts: what the estimate expects, and what has gone in. One tap
 * marks a part used; scan a part to find it (or to add it when the job
 * doesn't have it); the catalog adds anything else.
 */
import {Badge} from "@astryxdesign/core/Badge";
import {Button} from "@astryxdesign/core/Button";
import {EmptyState} from "@astryxdesign/core/EmptyState";
import {HStack} from "@astryxdesign/core/HStack";
import {Icon} from "@astryxdesign/core/Icon";
import {List, ListItem} from "@astryxdesign/core/List";
import {ProgressBar} from "@astryxdesign/core/ProgressBar";
import {StatusDot} from "@astryxdesign/core/StatusDot";
import {Text} from "@astryxdesign/core/Text";
import {VStack} from "@astryxdesign/core/VStack";
import {MagnifyingGlassIcon, QrCodeIcon} from "@heroicons/react/24/outline";
import {useSuspenseQuery} from "@tanstack/react-query";
import {getRouteApi} from "@tanstack/react-router";
import {useState} from "react";
import type {CatalogProduct, Part, PartList} from "../api/api";
import {useNotify} from "../components/feedback";
import {JobTabs} from "../components/JobTabs";
import {useHref} from "../components/links";
import {Page} from "../components/Page";
import {AddPartDialog, QuantityDialog} from "../components/PartDialogs";
import {useOpenScanner, useScanHandler} from "../components/scan";
import {MODEL, odoo} from "../data/odoo";
import {facade, useCacheWriter, useFacadeMutation} from "../data/queries";

const route = getRouteApi("/jobs/$jobId/parts");

export function PartsPage() {
    const {jobId} = route.useParams();
    const {data} = useSuspenseQuery(facade("parts", {repair_id: jobId}));
    const href = useHref();
    const notify = useNotify();
    const writeCache = useCacheWriter();
    const openScanner = useOpenScanner();
    const [editing, setEditing] = useState<Part | null>(null);
    const [adding, setAdding] = useState<CatalogProduct | null>(null);
    const keep = (list: PartList): void => writeCache("parts", {repair_id: jobId}, list);

    const useAll = useFacadeMutation("use_all", {onSuccess: keep});
    const reset = useFacadeMutation("reset_part", {onSuccess: keep});

    // A scan opens the part on the job, or offers to add a product it doesn't have.
    useScanHandler((code) => {
        const open = async (): Promise<void> => {
            const scan = await odoo.call(MODEL, "scan_part", {repair_id: jobId, code});
            const part = scan.move_id ? data.parts.find((p) => p.id === scan.move_id) : undefined;
            if (part) {
                setEditing(part);
            } else if (scan.product) {
                setAdding(scan.product);
            }
        };
        open().catch(notify.failed);
    });

    const {job, parts, can_edit: canEdit} = data;
    const done = parts.filter((part) => part.picked).length;

    return (
        <Page
            title={job.label}
            subtitle={[job.name, job.partner?.name].filter(Boolean).join(" · ")}
            backHref={href({to: "/jobs"})}
            backLabel="My Jobs"
            actions={
                canEdit ? (
                    <>
                        <Button label="Scan part" icon={<Icon icon={QrCodeIcon} />} onClick={() => openScanner("Scan a part's barcode")} />
                        <Button
                            label="Catalog"
                            variant="primary"
                            icon={<Icon icon={MagnifyingGlassIcon} />}
                            href={href({to: "/jobs/$jobId/catalog", params: {jobId}})}
                        />
                    </>
                ) : null
            }
            toolbar={<JobTabs job={job} current="parts" />}
        >
            <VStack gap={4} paddingBlock={4}>
                {parts.length === 0 ? (
                    <EmptyState title="No parts on this job" description="Scan a part or open the catalog to add one." />
                ) : (
                    <>
                        <ProgressBar label="Parts used" value={done} max={parts.length} hasValueLabel formatValueLabel={(value, max) => `${value} of ${max} used`} variant={done === parts.length ? "success" : "accent"} />
                        <List hasDividers edge="flush" density="spacious">
                            {parts.map((part) => (
                                <ListItem
                                    key={part.id}
                                    itemKey={part.id}
                                    label={part.product.name}
                                    description={<PartDetails part={part} />}
                                    startContent={<StatusDot variant={part.picked ? "success" : part.available ? "accent" : "neutral"} label={part.picked ? "Used" : part.available ? "Reserved, ready to pick" : "Not reserved yet"} />}
                                    endContent={
                                        canEdit ? (
                                            <HStack gap={2} vAlign="center">
                                                {part.added_by_technician ? <Badge label="Added by you" variant="purple" /> : null}
                                                {part.quantity_done > 0 ? (
                                                    <Button label="Undo" variant="ghost" isLoading={reset.isPending && reset.variables.move_id === part.id} onClick={() => reset.mutate({move_id: part.id}, {onError: notify.failed})} />
                                                ) : null}
                                                <Button label="Quantity" onClick={() => setEditing(part)} />
                                                {!part.picked && part.product.tracking === "none" ? (
                                                    <Button
                                                        label="Used all"
                                                        variant="primary"
                                                        isLoading={useAll.isPending && useAll.variables.move_id === part.id}
                                                        onClick={() => useAll.mutate({move_id: part.id}, {onError: notify.failed})}
                                                    />
                                                ) : null}
                                            </HStack>
                                        ) : null
                                    }
                                />
                            ))}
                        </List>
                    </>
                )}
            </VStack>
            {editing ? <QuantityDialog part={editing} onClose={() => setEditing(null)} onSaved={keep} /> : null}
            {adding ? <AddPartDialog repairId={jobId} product={adding} onClose={() => setAdding(null)} onAdded={keep} /> : null}
        </Page>
    );
}

function PartDetails({part}: {part: Part}) {
    const uom = part.product.uom.name;
    const bits = [part.product.default_code, `Used ${part.quantity_done} of ${part.quantity_demand} ${uom}`];
    if (part.lots.length) {
        bits.push(part.lots.map((lot) => lot.name).join(", "));
    }
    return (
        <Text type="supporting" hasTabularNumbers maxLines={2}>
            {bits.filter(Boolean).join(" · ")}
        </Text>
    );
}

/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Recording a part used, and adding one to the job. Quantities are decimal:
 * parts come in litres and metres as well as each.
 */
import {Button} from "@astryxdesign/core/Button";
import {Dialog, DialogHeader} from "@astryxdesign/core/Dialog";
import {FormLayout} from "@astryxdesign/core/FormLayout";
import {HStack} from "@astryxdesign/core/HStack";
import {Icon} from "@astryxdesign/core/Icon";
import {IconButton} from "@astryxdesign/core/IconButton";
import {NumberInput} from "@astryxdesign/core/NumberInput";
import {Switch} from "@astryxdesign/core/Switch";
import {Text} from "@astryxdesign/core/Text";
import {TextInput} from "@astryxdesign/core/TextInput";
import {QrCodeIcon} from "@heroicons/react/24/outline";
import {useState} from "react";
import type {CatalogProduct, Part, PartList} from "../api/api";
import {useFacadeMutation} from "../data/queries";
import {useNotify} from "./feedback";
import {useOpenScanner, useScanHandler} from "./scan";

export function QuantityDialog({part, onClose, onSaved}: {part: Part; onClose: () => void; onSaved: (list: PartList) => void}) {
    const notify = useNotify();
    const tracked = part.product.tracking !== "none";
    const [quantity, setQuantity] = useState<number>(part.quantity_done || part.quantity_demand);
    const [lot, setLot] = useState(part.lots[0]?.name ?? "");
    const openScanner = useOpenScanner();
    // While this dialog is open, a scan is the lot or serial.
    useScanHandler((code) => setLot(code));
    const save = useFacadeMutation("set_part_quantity", {
        onSuccess: (list) => {
            onSaved(list);
            notify.done(`${part.product.name}: ${quantity} ${part.product.uom.name} used.`);
            onClose();
        },
    });
    const submit = (): void => {
        const typed = lot.trim();
        const known = part.lots.find((l) => l.name === typed);
        save.mutate(
            {
                move_id: part.id,
                quantity,
                ...(tracked && known ? {lot_id: known.id} : {}),
                ...(tracked && typed && !known ? {lot_name: typed} : {}),
            },
            {onError: notify.failed}
        );
    };
    return (
        <Dialog isOpen onOpenChange={(open) => !open && onClose()} purpose="form" width={480}>
            <DialogHeader title={part.product.name} subtitle={`Expected ${part.quantity_demand} ${part.product.uom.name}`} onOpenChange={(open) => !open && onClose()} />
            <FormLayout>
                <NumberInput
                    label="Used"
                    value={quantity}
                    onChange={(value) => setQuantity(value)}
                    min={0}
                    step={part.product.uom.name.toLowerCase().startsWith("unit") ? 1 : 0.25}
                    units={part.product.uom.name}
                    hasAutoFocus
                    width="100%"
                />
                {tracked ? (
                    <HStack gap={2} vAlign="end">
                        <TextInput
                            label={part.product.tracking === "serial" ? "Serial number" : "Lot number"}
                            value={lot}
                            onChange={setLot}
                            autoCapitalize="characters"
                            hasAutoCorrect={false}
                            isRequired={quantity > 0}
                            width="100%"
                        />
                        <IconButton label="Scan it" icon={<Icon icon={QrCodeIcon} />} onClick={() => openScanner("Scan the lot or serial")} />
                    </HStack>
                ) : null}
                <HStack gap={2} hAlign="end">
                    <Button label="Cancel" variant="ghost" onClick={onClose} />
                    <Button label="Save" variant="primary" isLoading={save.isPending} isDisabled={tracked && quantity > 0 && !lot.trim()} onClick={submit} />
                </HStack>
            </FormLayout>
        </Dialog>
    );
}

export function AddPartDialog({
    repairId,
    product,
    onClose,
    onAdded,
}: {
    repairId: number;
    product: CatalogProduct;
    onClose: () => void;
    onAdded: (list: PartList) => void;
}) {
    const notify = useNotify();
    const [quantity, setQuantity] = useState(1);
    const [used, setUsed] = useState(true);
    const tracked = product.tracking !== "none";
    const add = useFacadeMutation("add_part", {
        onSuccess: (list) => {
            onAdded(list);
            notify.done(`Added ${quantity} × ${product.name}. The office will see it on the quote.`);
            onClose();
        },
    });
    return (
        <Dialog isOpen onOpenChange={(open) => !open && onClose()} purpose="form" width={480}>
            <DialogHeader title={`Add ${product.name}`} subtitle={[product.default_code, `${product.qty_available} in stock`].filter(Boolean).join(" · ")} onOpenChange={(open) => !open && onClose()} />
            <FormLayout>
                <NumberInput label="Quantity" value={quantity} onChange={setQuantity} min={0.01} units={product.uom.name} hasAutoFocus width="100%" />
                {tracked ? (
                    <Text type="supporting">It's tracked by lot or serial: record it as used from the parts list, with its number.</Text>
                ) : (
                    <Switch label="I've used it already" value={used} onChange={setUsed} />
                )}
                <Text type="supporting">A part you add goes on the customer's quote, marked as added by you, for the office to review.</Text>
                <HStack gap={2} hAlign="end">
                    <Button label="Cancel" variant="ghost" onClick={onClose} />
                    <Button
                        label="Add to job"
                        variant="primary"
                        isLoading={add.isPending}
                        isDisabled={!(quantity > 0)}
                        onClick={() => add.mutate({repair_id: repairId, product_id: product.id, quantity, used: used && !tracked}, {onError: notify.failed})}
                    />
                </HStack>
            </FormLayout>
        </Dialog>
    );
}

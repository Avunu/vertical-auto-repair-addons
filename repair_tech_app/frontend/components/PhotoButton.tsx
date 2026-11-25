/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Take a photo: the device's own camera (capture="environment" opens the rear
 * camera straight away on a tablet), downscaled on the device before upload.
 */
import {Button} from "@astryxdesign/core/Button";
import {Icon} from "@astryxdesign/core/Icon";
import {VisuallyHidden} from "@astryxdesign/core/VisuallyHidden";
import {CameraIcon} from "@heroicons/react/24/outline";
import {useRef, useState} from "react";
import {downscalePhoto} from "../lib/image";

export function PhotoButton({onPhoto, isDisabled = false}: {onPhoto: (base64: string, name: string) => Promise<unknown>; isDisabled?: boolean}) {
    const input = useRef<HTMLInputElement>(null);
    const [busy, setBusy] = useState(false);
    const take = async (file: File): Promise<void> => {
        setBusy(true);
        try {
            await onPhoto(await downscalePhoto(file), file.name.replace(/\.\w+$/, ".jpg"));
        } finally {
            setBusy(false);
            if (input.current) {
                input.current.value = "";
            }
        }
    };
    return (
        <>
            <Button label="Take photo" icon={<Icon icon={CameraIcon} />} isLoading={busy} isDisabled={isDisabled} onClick={() => input.current?.click()} />
            <VisuallyHidden>
                <input
                    ref={input}
                    type="file"
                    accept="image/*"
                    capture="environment"
                    tabIndex={-1}
                    aria-hidden="true"
                    onChange={(event) => {
                        const file = event.currentTarget.files?.[0];
                        if (file) {
                            void take(file);
                        }
                    }}
                />
            </VisuallyHidden>
        </>
    );
}

/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Scanning, app-wide. One provider owns the camera dialog and listens for a
 * hardware scanner; the screen on top says what a code means there with
 * `useScanHandler` (My Jobs: open the job; Parts: find the part). The last
 * screen to register wins, and unmounting hands the scanner back.
 */
import {Button} from "@astryxdesign/core/Button";
import {Dialog, DialogHeader} from "@astryxdesign/core/Dialog";
import {Text} from "@astryxdesign/core/Text";
import {TextInput} from "@astryxdesign/core/TextInput";
import {VStack} from "@astryxdesign/core/VStack";
import {HStack} from "@astryxdesign/core/HStack";
import * as stylex from "@stylexjs/stylex";
import {createContext, use, useEffect, useRef, useState, type ReactNode} from "react";
import {buzz} from "../lib/device";
import {cleanCode, getDetector, wedgeReader} from "../lib/scanner";

type Handler = (code: string) => void;

interface ScanApi {
    /** Open the camera; the code goes to the screen's handler. */
    open: (prompt?: string) => void;
    register: (handler: Handler) => () => void;
}

const ScanContext = createContext<ScanApi | null>(null);

function useScanApi(): ScanApi {
    const api = use(ScanContext);
    if (!api) {
        throw new Error("Scanning needs a ScanProvider");
    }
    return api;
}

/** What a scanned code does while this screen is showing. */
export function useScanHandler(handler: Handler): void {
    const api = useScanApi();
    const latest = useRef(handler);
    useEffect(() => {
        latest.current = handler;
    });
    useEffect(() => api.register((code) => latest.current(code)), [api]);
}

export function useOpenScanner(): (prompt?: string) => void {
    return useScanApi().open;
}

export function ScanProvider({children}: {children: ReactNode}) {
    const handlers = useRef<Handler[]>([]);
    const [prompt, setPrompt] = useState<string | null>(null);
    const deliver = (code: string): void => {
        buzz();
        handlers.current.at(-1)?.(code);
    };
    const deliverRef = useRef(deliver);
    useEffect(() => {
        deliverRef.current = deliver;
    });

    // A hardware scanner types fast and ends with Enter. Leave a field that
    // has focus alone: there the scanner simply types into it.
    useEffect(() => {
        const feed = wedgeReader((code) => deliverRef.current(code));
        const onKey = (event: KeyboardEvent): void => {
            const target = event.target as HTMLElement | null;
            if (target?.closest("input, textarea, [contenteditable]")) {
                return;
            }
            if (feed(event.key, event.timeStamp)) {
                event.preventDefault();
            }
        };
        document.addEventListener("keydown", onKey);
        return () => document.removeEventListener("keydown", onKey);
    }, []);

    // Built once: what it closes over (a ref, a state setter) never changes.
    const [api] = useState<ScanApi>(() => ({
        open: (text) => setPrompt(text ?? "Point the camera at a barcode"),
        register: (handler) => {
            handlers.current.push(handler);
            return () => {
                handlers.current = handlers.current.filter((h) => h !== handler);
            };
        },
    }));

    return (
        <ScanContext value={api}>
            {children}
            {prompt !== null ? (
                <ScanDialog
                    prompt={prompt}
                    onCode={(code) => {
                        setPrompt(null);
                        deliver(code);
                    }}
                    onClose={() => setPrompt(null)}
                />
            ) : null}
        </ScanContext>
    );
}

const styles = stylex.create({
    video: {
        width: "100%",
        aspectRatio: "4 / 3",
        objectFit: "cover",
        borderRadius: "var(--radius-container)",
        backgroundColor: "var(--color-background-muted)",
    },
});

type CameraState = "starting" | "scanning" | "denied" | "unavailable";

function ScanDialog({prompt, onCode, onClose}: {prompt: string; onCode: (code: string) => void; onClose: () => void}) {
    const video = useRef<HTMLVideoElement>(null);
    const [state, setState] = useState<CameraState>("starting");
    const [typed, setTyped] = useState("");
    const onCodeRef = useRef(onCode);
    useEffect(() => {
        onCodeRef.current = onCode;
    });

    useEffect(() => {
        let stream: MediaStream | null = null;
        let frame = 0;
        let alive = true;
        const start = async (): Promise<void> => {
            if (!navigator.mediaDevices?.getUserMedia) {
                setState("unavailable");
                return;
            }
            try {
                stream = await navigator.mediaDevices.getUserMedia({
                    video: {facingMode: "environment", width: {ideal: 1280}, height: {ideal: 960}},
                    audio: false,
                });
            } catch (error) {
                setState(error instanceof DOMException && error.name === "NotAllowedError" ? "denied" : "unavailable");
                return;
            }
            const element = video.current;
            if (!alive || !element) {
                stream.getTracks().forEach((track) => track.stop());
                return;
            }
            element.srcObject = stream;
            await element.play().catch(() => undefined);
            setState("scanning");
            const detector = await getDetector();
            const tick = async (): Promise<void> => {
                if (!alive) {
                    return;
                }
                if (element.readyState >= HTMLMediaElement.HAVE_ENOUGH_DATA) {
                    const found = await detector.detect(element).catch(() => []);
                    const code = found.map((barcode) => cleanCode(barcode.rawValue)).find(Boolean);
                    if (code && alive) {
                        onCodeRef.current(code);
                        return;
                    }
                }
                frame = requestAnimationFrame(() => void tick());
            };
            void tick();
        };
        void start();
        return () => {
            alive = false;
            cancelAnimationFrame(frame);
            stream?.getTracks().forEach((track) => track.stop());
        };
    }, []);

    const submitTyped = (): void => {
        const code = cleanCode(typed);
        if (code) {
            onCode(code);
        }
    };

    return (
        <Dialog isOpen onOpenChange={(open) => !open && onClose()} width={560} purpose="form">
            <DialogHeader title="Scan" subtitle={prompt} onOpenChange={(open) => !open && onClose()} />
            <VStack gap={3}>
                {state === "denied" ? (
                    <Text>Camera access is off for this app. Allow it in the device settings, or type the code below.</Text>
                ) : state === "unavailable" ? (
                    <Text>No camera here. Type the code below, or use a hardware scanner.</Text>
                ) : (
                    <video ref={video} muted playsInline aria-label="Camera" {...stylex.props(styles.video)} />
                )}
                <HStack gap={2} vAlign="end">
                    <TextInput
                        label="Or type it"
                        value={typed}
                        onChange={setTyped}
                        onEnter={submitTyped}
                        autoCapitalize="characters"
                        hasAutoCorrect={false}
                        enterKeyHint="go"
                        width="100%"
                    />
                    <Button label="Go" variant="primary" onClick={submitTyped} isDisabled={!cleanCode(typed)} />
                </HStack>
            </VStack>
        </Dialog>
    );
}

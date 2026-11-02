/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Take a photo with the tablet's rear camera.
 *
 * `capture="environment"` is what makes iPad Safari open the camera straight
 * away instead of the photo library. The image is downscaled in a canvas
 * before upload: a modern tablet camera produces 4-8 MB per shot, and a
 * technician takes a dozen per inspection.
 */
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";

const MAX_EDGE = 1600;
const JPEG_QUALITY = 0.75;

const RepairPhotoCapture = defineComponent({
    props: {
        count: {type: Number, default: 0},
    },
    data() {
        return {
            busy: false,
        };
    },
    methods: {
        /** @returns {void} */
        pick() {
            /** @type {HTMLInputElement} */ (this.$refs.input).click();
        },
        /**
         * @param {Event} event
         * @returns {void}
         */
        on_file(event) {
            const target = /** @type {HTMLInputElement} */ (event.target);
            const file = target.files && target.files[0];
            if (!file) {
                return;
            }
            this.busy = true;
            this._downscale(file)
                .then((data_url) => {
                    this.$emit("capture", {
                        image_b64: data_url,
                        filename: file.name || "photo.jpg",
                    });
                })
                .catch((err) => {
                    console.error("Could not process the photo", err);
                })
                .finally(() => {
                    this.busy = false;
                    // Let the same file be picked again.
                    target.value = "";
                });
        },
        /**
         * @param {File} file
         * @returns {Promise<string>}
         */
        _downscale(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onerror = reject;
                reader.onload = () => {
                    const img = new Image();
                    img.onerror = reject;
                    img.onload = () => {
                        const scale = Math.min(1, MAX_EDGE / Math.max(img.width, img.height));
                        const canvas = document.createElement("canvas");
                        canvas.width = Math.round(img.width * scale);
                        canvas.height = Math.round(img.height * scale);
                        /** @type {CanvasRenderingContext2D} */ (canvas.getContext("2d")).drawImage(
                            img,
                            0,
                            0,
                            canvas.width,
                            canvas.height
                        );
                        resolve(canvas.toDataURL("image/jpeg", JPEG_QUALITY));
                    };
                    img.src = /** @type {string} */ (reader.result);
                };
                reader.readAsDataURL(file);
            });
        },
    },
    template: html`
        <div class="photo-capture">
            <input
                ref="input"
                type="file"
                accept="image/*"
                capture="environment"
                class="photo-capture__input"
                @change="on_file" />
            <v-btn x-large block :loading="busy" @click="pick">
                <v-icon left>mdi-camera</v-icon>
                {{ $t('repair.inspection.add_photo') }}
                <v-chip x-small class="ml-2" v-if="count">{{ count }}</v-chip>
            </v-btn>
        </div>
    `,
});

export default RepairPhotoCapture;

Vue.component("repair-photo-capture", RepairPhotoCapture);

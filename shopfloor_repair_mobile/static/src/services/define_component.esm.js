/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Type-checking helpers for plain Vue 2 options objects. Neither changes
 * anything at runtime.
 *
 * `defineComponent` is Vue 2.7's own API of the same name, backported: the
 * vendored Vue in shopfloor_mobile_base is 2.6.12, which predates it. Vue
 * 2.6's typings for `Vue.component(tag, options)` / `Vue.extend(options)` end
 * with a catch-all overload whose `this` is untyped, and `tsc` silently
 * falls through to it whenever the typed overload fails - including when
 * it fails because of the very mistake (a misspelled `this.foo`) that
 * should have been reported. This helper has only the typed signature, so
 * the mistake is reported instead. Swap it for `Vue.defineComponent` if
 * the runtime is ever upgraded to 2.7.
 *
 * `extendComponent` is the same thing for a component built on a mixin's
 * constructor (`base.extend(options)`), with `this` typed as the base
 * instance too.
 */
/** @import {VueConstructor} from "vue" */
/** @import {ExtendedVue} from "vue/types/vue" */
/** @import {ThisTypedComponentOptionsWithRecordProps} from "vue/types/options" */

/**
 * @template [Data={}]
 * @template [Methods={}]
 * @template [Computed={}]
 * @template [Props={}]
 * @param {ThisTypedComponentOptionsWithRecordProps<Vue, Data, Methods, Computed, Props>} options
 * @returns {ThisTypedComponentOptionsWithRecordProps<Vue, Data, Methods, Computed, Props>}
 */
export function defineComponent(options) {
    return options;
}

/**
 * @template {Vue} V
 * @template [Data={}]
 * @template [Methods={}]
 * @template [Computed={}]
 * @template [Props={}]
 * @param {VueConstructor<V>} base
 * @param {ThisTypedComponentOptionsWithRecordProps<V, Data, Methods, Computed, Props>} options
 * @returns {ExtendedVue<V, Data, Methods, Computed, Props>}
 */
export function extendComponent(base, options) {
    return base.extend(options);
}

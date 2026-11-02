/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Type-only stub for shopfloor_mobile_base's `services/registry.esm.js`.
 * Wired in via tsconfig `paths` purely so the type-checker has a shape to
 * check against - at runtime the browser resolves this same absolute import
 * specifier to the real file served by shopfloor_mobile_base, never to this
 * one.
 */
export interface RegistryRecord<TComponent = unknown> {
    key: string;
    component: TComponent;
    metadata: Record<string, unknown>;
    route: Record<string, unknown>;
}

export class BaseRegistry<TComponent = unknown> {
    add(
        key: string,
        component: TComponent,
        route?: Record<string, unknown>,
        metadata?: Record<string, unknown>,
        override?: boolean
    ): RegistryRecord<TComponent>;
    replace(key: string, component: TComponent, metadata?: Record<string, unknown>): RegistryRecord<TComponent>;
    get(key: string): RegistryRecord<TComponent> | undefined;
    all(): Record<string, RegistryRecord<TComponent>>;
}

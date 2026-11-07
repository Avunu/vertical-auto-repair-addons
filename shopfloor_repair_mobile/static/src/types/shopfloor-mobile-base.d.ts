/**
 * Best-effort ambient types for the untyped `shopfloor_mobile_base` surface
 * this module touches. shopfloor_mobile_base itself has no TypeScript
 * types, so these are reverse-engineered from actual usage across this
 * module's source files rather than derived from a real source of truth -
 * treat unfamiliar shapes here as `any` rather than assuming correctness.
 */
import Vue from "vue";

/**
 * lodash, loaded as a plain global <script> by shopfloor_mobile_base.
 *
 * `Vue` itself is likewise a plain global <script> there - the full build,
 * template compiler included, which is what lets every component in this
 * module declare its `template` as a plain string. It needs no declaration
 * here: the npm `vue` package (a devDependency for its types only) already
 * declares that UMD global, and tsconfig's `allowUmdGlobalAccess` lets
 * these ES modules reference it without an import.
 */
declare global {
  const _: any;
}

/** A registered `Vue.observable`-style REST client returned by `$root.getOdoo`. */
export type OdooRoute = string | unknown[];

export interface OdooClient {
  get(url: OdooRoute, params?: Record<string, unknown>): Promise<any>;
  post(url: OdooRoute, data?: Record<string, unknown>): Promise<any>;
}

export interface OdooClientParams {
  usage: string;
  headers?: Record<string, string>;
  // Routes the request through `window.standardFetch` instead of
  // `window.fetch` (shopfloor_mobile_base's odoo.esm.js), skipping the
  // `fetchStart`/`fetchEnd` events that drive the app's global loading
  // indicator - for requests that shouldn't visibly block/flicker the UI.
  in_background?: boolean;
}

export interface AppNavItem {
  id: unknown;
  name: string;
  // The process_registry/scenario key this menu entry opens (e.g.
  // "repair_job") - `shopfloor_base`'s menu.py serializes it as
  // `scenario_key:scenario`. Used to resolve a `SERVICE-CTX-MENU-ID`
  // header for REST calls issued outside any scenario route (see
  // `menu_id_for` in services/root.esm.js).
  scenario: string;
  [key: string]: unknown;
}

export interface AppInfo {
  running_env: string;
  profile_required: boolean;
  [key: string]: unknown;
}

export interface UserProfile {
  id: unknown;
  name: string;
  [key: string]: unknown;
}

export interface AppUser {
  id: unknown;
  name: string;
  [key: string]: unknown;
}

/**
 * The root Vue instance every component can reach via `this.$root`,
 * assembled by shopfloor_mobile_base's own bootstrap code. Only the
 * members actually referenced from this module are declared.
 */
export interface ShopfloorRoot extends Vue {
  getOdoo(params: OdooClientParams): OdooClient;
  getNav(): {app_nav: AppNavItem[]};
  user: AppUser;
  profile: UserProfile;
  profiles: UserProfile[];
  /** The sync payload (`user_config`) the root keeps in `$storage` as "appconfig". */
  appconfig: {default_profile_id?: number | null; [key: string]: unknown} | null;
  has_profile: boolean;
  authenticated: boolean;
  /** The signed-in key, kept in browser storage; empty once it has expired. */
  apikey: string;
  is_authenticated(): boolean;
  app_info: AppInfo;
  loading: boolean;
  $storage: {
    get(key: string, default_value?: unknown): unknown;
    set(key: string, value: unknown): void;
    remove(key: string): void;
    keys(): string[];
  };
  logout(): void;
  trigger(event: string, payload?: unknown, force?: boolean): void;
}

export interface RouteInfo {
  name: string | null;
  params: Record<string, string>;
  [key: string]: unknown;
}

declare module "vue/types/vue" {
  interface Vue {
    $route: RouteInfo;
    $router: {
      push(location: string | Record<string, unknown>): Promise<unknown>;
    };
    $t(key: string, ...args: unknown[]): string;
    utils: {
      display: {
        format_date_display(value: string): string;
        [key: string]: (...args: any[]) => any;
      };
      [key: string]: any;
    };
  }
}

/**
 * Types for the rest of the `shopfloor_mobile_base` surface this module
 * imports (`page_registry`, `process_registry`, `translation_registry`,
 * `ScenarioBaseMixin`, ...) live in `types/stubs/*.d.ts`, wired to each
 * import's exact absolute specifier via `tsconfig.json`'s `paths` - see
 * that directory's own comment for why a `declare module "/abs/path"`
 * block (the more obvious approach) doesn't work: TypeScript's resolver
 * treats a leading `/` as a real filesystem path and never falls back to
 * ambient declarations for it, regardless of what's declared here.
 */

/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Overrides `shopfloor_mobile_base`'s own `user-session-detail`
 * (components/screen.esm.js) - same re-registration technique already
 * used for `nav-items-extra`/`app-bar-actions`. Rendered bare (no props)
 * in the sidebar drawer by `Screen`'s own template, so flipping this
 * component's own *prop defaults* is what actually changes the drawer -
 * there's no other override point for that specific call site.
 *
 * Drops the "Test"/running-env row (`show_env`) and the separate
 * "Technician"/profile row (`show_profile`) - the profile row's own job
 * (linking to `/profile`) moves onto the user's own name/avatar row
 * instead, so tapping your own name is how you reach the profile picker,
 * rather than a second, redundant row underneath it.
 */
/** @import {ShopfloorRoot} from "../types/shopfloor-mobile-base" */
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {sf_root} from "../services/root.esm.js";

const UserSessionDetail = defineComponent({
    props: {
        show_user: {type: Boolean, default: true},
        show_profile: {type: Boolean, default: false},
        show_env: {type: Boolean, default: false},
        show_report_issue_action: {type: Boolean, default: true},
    },
    data() {
        return {
            // Was `$options._componentTag` (a Vue-internal, undocumented field
            // some Vue-aware type-checking frontends don't model consistently) -
            // this is just that same tag name, explicit and typed, matching the
            // `Vue.component()` registration below.
            tag_name: "user-session-detail",
        };
    },
    computed: {
        // `$root` in a template resolves through Vue's own (bare) `$root: Vue`
        // type - see services/root.esm.js for why that can't be widened by
        // augmentation. Exposing a typed computed here is what actually gets
        // the template checked against the real shape.
        /** @returns {ShopfloorRoot} */
        root() {
            return sf_root(this);
        },
    },
    template: html`
      <div :class="tag_name" data-ref="user-session-detail">
        <v-list>
            <report-issue-action v-if="show_report_issue_action" />
            <v-list-item v-if="show_env"
                    data-ref="session-detail-env"
                    :data-id="root.app_info.running_env"
                    >
                <v-list-item-avatar>
                    <v-avatar :color="root.app_info.running_env == 'prod' ? 'primary' : 'warning'" size="36">
                        <v-icon dark>mdi-server</v-icon>
                    </v-avatar>
                </v-list-item-avatar>
                <v-list-item-content>
                    <span v-text="$t('app.running_env.' + root.app_info.running_env)" />
                </v-list-item-content>
            </v-list-item>
            <v-list-item v-if="show_user && root.user.id"
                    data-ref="session-detail-user"
                    :data-id="root.user.id"
                    :to="{name: 'profile'}"
                    >
                <v-list-item-avatar>
                    <v-avatar color="primary" size="36">
                        <v-icon dark>mdi-account-circle</v-icon>
                    </v-avatar>
                </v-list-item-avatar>
                <v-list-item-content>
                    <span v-text="root.user.name" />
                </v-list-item-content>
            </v-list-item>
            <v-list-item v-if="show_profile && root.has_profile"
                    data-ref="session-detail-profile"
                    :data-id="root.profile.id"
                    :to="{name: 'profile'}"
                    >
                <v-list-item-avatar>
                    <v-avatar color="primary" size="36">
                        <v-icon dark>mdi-account-multiple-check</v-icon>
                    </v-avatar>
                </v-list-item-avatar>
                <v-list-item-content>
                    <span v-text="root.profile.name" />
                </v-list-item-content>
            </v-list-item>
        </v-list>
      </div>
    `,
});

export default UserSessionDetail;

Vue.component("user-session-detail", UserSessionDetail);

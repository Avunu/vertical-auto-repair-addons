/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Astryx components take an `href`; the router owns navigation. RouterAnchor
 * (given to Astryx's LinkProvider) renders a real anchor with the public
 * URL - so long-press, middle-click and "open in new tab" work - and turns a
 * plain click into a client-side navigation. `useHref` makes those hrefs
 * from typed route options, so a link to a route that doesn't exist, or
 * with the wrong params, doesn't compile.
 */
import {useRouter} from "@tanstack/react-router";
import type {AnchorHTMLAttributes, MouseEvent, Ref} from "react";
import type {Destination} from "../router";

export function useHref(): (to: Destination) => string {
    const router = useRouter();
    return (to) => router.buildLocation(to).href;
}

type AnchorProps = AnchorHTMLAttributes<HTMLAnchorElement> & {ref?: Ref<HTMLAnchorElement>};

export function RouterAnchor({href, onClick, target, ...rest}: AnchorProps) {
    const router = useRouter();
    const internal = typeof href === "string" && href.startsWith("/") && !href.startsWith("//");
    const handleClick = (event: MouseEvent<HTMLAnchorElement>): void => {
        onClick?.(event);
        const modified = event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0;
        if (!internal || event.defaultPrevented || modified || (target && target !== "_self")) {
            return;
        }
        event.preventDefault();
        void router.navigate({href});
    };
    // The router's hrefs leave out its basepath; the anchor needs the real URL.
    const publicHref = internal ? `${router.basepath.replace(/\/$/, "")}${href}` : href;
    // Astryx renders this in place of its own <a>: the children, role and
    // keyboard behaviour come from it through `rest`.
    // oxlint-disable-next-line jsx-a11y/anchor-has-content, jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
    return <a {...rest} {...(publicHref === undefined ? {} : {href: publicHref})} {...(target ? {target} : {})} onClick={handleClick} />;
}

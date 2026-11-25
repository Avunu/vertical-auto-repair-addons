/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Every screen's frame: a header that stays put (back, title, the screen's
 * actions) over content that scrolls, held to a readable width on a
 * landscape iPad.
 */
import {Heading} from "@astryxdesign/core/Heading";
import {HStack} from "@astryxdesign/core/HStack";
import {IconButton} from "@astryxdesign/core/IconButton";
import {Icon} from "@astryxdesign/core/Icon";
import {Layout, LayoutContent, LayoutHeader} from "@astryxdesign/core/Layout";
import {StackItem} from "@astryxdesign/core/Stack";
import {Text} from "@astryxdesign/core/Text";
import {VStack} from "@astryxdesign/core/VStack";
import type {ReactNode} from "react";

export interface PageProps {
    title: string;
    subtitle?: ReactNode;
    /** Where the back arrow goes; no arrow without one. */
    backHref?: string;
    backLabel?: string;
    actions?: ReactNode;
    /** Under the title row: tabs, a search bar. */
    toolbar?: ReactNode;
    children: ReactNode;
}

export function Page({title, subtitle, backHref, backLabel = "Back", actions, toolbar, children}: PageProps) {
    return (
        <Layout
            contentWidth={1024}
            header={
                <LayoutHeader hasDivider>
                    <VStack gap={2}>
                        <HStack gap={2} vAlign="center" wrap="wrap">
                            {backHref ? (
                                <IconButton label={backLabel} icon={<Icon icon="chevronLeft" />} variant="ghost" href={backHref} />
                            ) : null}
                            <StackItem size="fill">
                                <VStack gap={0.5}>
                                    <Heading level={1} maxLines={1}>
                                        {title}
                                    </Heading>
                                    {subtitle ? (
                                        <Text type="supporting" maxLines={1}>
                                            {subtitle}
                                        </Text>
                                    ) : null}
                                </VStack>
                            </StackItem>
                            {actions ? (
                                <HStack gap={2} vAlign="center" wrap="wrap">
                                    {actions}
                                </HStack>
                            ) : null}
                        </HStack>
                        {toolbar}
                    </VStack>
                </LayoutHeader>
            }
            content={<LayoutContent>{children}</LayoutContent>}
        />
    );
}

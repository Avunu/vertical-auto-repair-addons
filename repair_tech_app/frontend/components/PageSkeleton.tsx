/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */
import {Skeleton} from "@astryxdesign/core/Skeleton";
import {VStack} from "@astryxdesign/core/VStack";

/** While a screen's data arrives (never long: most come from the cache). */
export function PageSkeleton() {
    return (
        <VStack gap={3} padding={4} aria-busy="true" aria-label="Loading">
            <Skeleton height={32} width="40%" />
            {[0, 1, 2, 3, 4].map((index) => (
                <Skeleton key={index} height={56} index={index} />
            ))}
        </VStack>
    );
}

/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The parts catalog, for a job: search by name, part number or barcode,
 * narrow by category, and add what was installed. The search lives in the
 * URL, so Back returns to the same results.
 */
import {EmptyState} from "@astryxdesign/core/EmptyState";
import {HStack} from "@astryxdesign/core/HStack";
import {List, ListItem} from "@astryxdesign/core/List";
import {Pagination} from "@astryxdesign/core/Pagination";
import {Selector} from "@astryxdesign/core/Selector";
import {Spinner} from "@astryxdesign/core/Spinner";
import {Text} from "@astryxdesign/core/Text";
import {TextInput} from "@astryxdesign/core/TextInput";
import {VStack} from "@astryxdesign/core/VStack";
import {Badge} from "@astryxdesign/core/Badge";
import {keepPreviousData, useQuery, useSuspenseQuery} from "@tanstack/react-query";
import {getRouteApi} from "@tanstack/react-router";
import {useDeferredValue, useEffect, useState} from "react";
import type {CatalogProduct} from "../api/api";
import {useHref} from "../components/links";
import {Page} from "../components/Page";
import {AddPartDialog} from "../components/PartDialogs";
import {useScanHandler} from "../components/scan";
import {facade, useCacheWriter} from "../data/queries";
import {compact} from "../lib/compact";

const route = getRouteApi("/jobs/$jobId/catalog");
const ALL = "all";

export function CatalogPage() {
    const {jobId} = route.useParams();
    const search = route.useSearch();
    const navigate = route.useNavigate();
    const href = useHref();
    const writeCache = useCacheWriter();
    const {data: categories} = useSuspenseQuery(facade("catalog_categories", {}));
    const [text, setText] = useState(search.q ?? "");
    const typed = useDeferredValue(text);
    const [adding, setAdding] = useState<CatalogProduct | null>(null);

    // The URL follows the typing (replace: one Back leaves the catalog).
    useEffect(() => {
        const q = typed.trim();
        if (q !== (search.q ?? "")) {
            void navigate({search: (prev) => compact({...prev, page: undefined, q: q || undefined}), replace: true});
        }
    }, [typed, search.q, navigate]);
    // A scan searches for the code.
    useScanHandler((code) => setText(code));

    const params = {
        ...(search.q ? {search: search.q} : {}),
        ...(search.category ? {category_id: search.category} : {}),
        page: search.page ?? 1,
    };
    const {data, isFetching} = useQuery({...facade("catalog", params), placeholderData: keepPreviousData});

    return (
        <Page
            title="Parts catalog"
            subtitle="Tap a part to add it to the job"
            backHref={href({to: "/jobs/$jobId/parts", params: {jobId}})}
            backLabel="Parts"
            toolbar={
                <HStack gap={2} wrap="wrap" vAlign="end">
                    <TextInput
                        label="Search parts"
                        isLabelHidden
                        type="search"
                        startIcon="search"
                        placeholder="Name, part number or barcode"
                        value={text}
                        onChange={setText}
                        hasClear
                        hasAutoFocus
                        autoCapitalize="none"
                        hasAutoCorrect={false}
                        enterKeyHint="search"
                        isLoading={isFetching}
                        width="min(100%, 480px)"
                    />
                    <Selector
                        label="Category"
                        isLabelHidden
                        hasSearch
                        presentation="adaptive"
                        value={search.category ? String(search.category) : ALL}
                        options={[{value: ALL, label: "All categories"}, ...categories.map((c) => ({value: String(c.id), label: c.name}))]}
                        onChange={(value) =>
                            void navigate({search: (prev) => compact({...prev, page: undefined, category: value === ALL ? undefined : Number(value)}), replace: true})
                        }
                    />
                </HStack>
            }
        >
            <VStack gap={4} paddingBlock={4}>
                {!data ? (
                    <Spinner label="Searching" />
                ) : data.records.length === 0 ? (
                    <EmptyState title="No parts found" description={search.q ? `Nothing matches “${search.q}”.` : "This category is empty."} />
                ) : (
                    <>
                        <List hasDividers edge="flush" density="spacious">
                            {data.records.map((product) => (
                                <ListItem
                                    key={product.id}
                                    itemKey={product.id}
                                    label={product.name}
                                    description={[product.default_code, product.barcode].filter(Boolean).join(" · ") || undefined}
                                    endContent={
                                        <HStack gap={2} vAlign="center">
                                            <Badge label={`${product.qty_available} ${product.uom.name}`} variant={product.qty_available > 0 ? "green" : "neutral"} />
                                        </HStack>
                                    }
                                    onClick={() => setAdding(product)}
                                />
                            ))}
                        </List>
                        <HStack hAlign="between" vAlign="center">
                            <Text type="supporting">{`${data.total} parts`}</Text>
                            <Pagination
                                page={data.page}
                                pageSize={data.page_size}
                                totalItems={data.total}
                                variant="compact"
                                onChange={(page) => void navigate({search: (prev) => compact({...prev, page: page > 1 ? page : undefined})})}
                            />
                        </HStack>
                    </>
                )}
            </VStack>
            {adding ? (
                <AddPartDialog
                    repairId={jobId}
                    product={adding}
                    onClose={() => setAdding(null)}
                    onAdded={(list) => {
                        writeCache("parts", {repair_id: jobId}, list);
                        void navigate({to: "/jobs/$jobId/parts", params: {jobId}, search: {}});
                    }}
                />
            ) : null}
        </Page>
    );
}

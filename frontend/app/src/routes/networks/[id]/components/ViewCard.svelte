<script lang="ts" module>
	// LRU cache for rendered views — shared across all ViewCard instances
	const VIEW_CACHE_MAX = 50;
	const viewCache = new Map<string, import('$lib/types.js').PlotData>();

	function cacheGet(key: string): import('$lib/types.js').PlotData | undefined {
		const v = viewCache.get(key);
		if (v !== undefined) {
			viewCache.delete(key);
			viewCache.set(key, v);
		}
		return v;
	}

	function cacheSet(key: string, value: import('$lib/types.js').PlotData): void {
		if (viewCache.has(key)) viewCache.delete(key);
		viewCache.set(key, value);
		while (viewCache.size > VIEW_CACHE_MAX) {
			const oldest = viewCache.keys().next().value;
			if (oldest === undefined) break;
			viewCache.delete(oldest);
		}
	}
</script>

<script lang="ts">
	import { onDestroy, tick } from 'svelte';
	import { views, type ViewTarget } from '$lib/api/client.js';
	import type { ApiError, PlotData } from '$lib/types.js';
	import type { ViewCardDefinition } from '$lib/stores/reportStore.svelte.js';
	import { loadPlotly, renderPlot, purgePlot, resizePlot } from './plotRenderer.js';
	import { PlotSkeleton } from '$lib/components/skeletons';
	import Pencil from '@lucide/svelte/icons/pencil';
	import Ellipsis from '@lucide/svelte/icons/ellipsis';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import ChartNoAxesColumn from '@lucide/svelte/icons/chart-no-axes-column';
	import Button from '$lib/components/ui/button/button.svelte';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';

	interface Props {
		card: ViewCardDefinition;
		networkId: string;
		/** The registered result folder (all planning years); the single network otherwise. */
		folderId?: string | null;
		onedit?: () => void;
		onremove?: () => void;
		onfullscreen?: () => void;
		label?: string;
		showActions?: boolean;
	}

	let { card, networkId, folderId = null, onedit, onremove, onfullscreen, label, showActions = true }: Props = $props();

	let target = $derived<ViewTarget>(folderId ? { folderId } : { networkIds: [networkId] });
	let title = $derived(card.name || card.view.replace(/^view_/, '').replace(/_/g, ' '));

	let cardEl: HTMLDivElement | undefined = $state();
	let plotEl: HTMLDivElement | undefined = $state();
	let Plotly: any = $state();
	let loading = $state(true);
	let error = $state<string | null>(null);
	let emptyData = $state(false);
	let visible = $state(false);
	let mounted = true;
	let requestId = 0;
	let debounceTimer: ReturnType<typeof setTimeout>;
	let resizeObserver: ResizeObserver | undefined;
	let visibilityObserver: IntersectionObserver | undefined;
	let resizeRaf = 0;

	async function waitForLayout(): Promise<void> {
		await tick();
		await new Promise((resolve) => requestAnimationFrame(() => resolve(undefined)));
	}

	function show(data: PlotData) {
		if (!plotEl) return;
		// the backend styles the figure completely; keep its layout, only let it size itself
		renderPlot(plotEl, data, Plotly);
	}

	async function generate() {
		const currentReqId = ++requestId;
		error = null;
		emptyData = false;

		const key = JSON.stringify([target, card.view, card.parameters]);
		const cached = cacheGet(key);
		if (cached) {
			loading = false;
			if (!Plotly) Plotly = await loadPlotly();
			if (currentReqId !== requestId || !mounted) return;
			await waitForLayout();
			if (currentReqId !== requestId || !mounted) return;
			show(cached);
			return;
		}

		loading = true;
		try {
			if (!Plotly) Plotly = await loadPlotly();
			const data = await views.generate(target, card.view, card.parameters);
			if (currentReqId !== requestId || !mounted) return;
			const traces = data.data;
			if (!traces || (Array.isArray(traces) && traces.length === 0)) {
				emptyData = true;
				loading = false;
				return;
			}
			cacheSet(key, data);
			loading = false;
			await waitForLayout();
			if (currentReqId !== requestId || !mounted) return;
			show(data);
		} catch (err: unknown) {
			if (currentReqId !== requestId) return;
			if ((err as ApiError).cancelled) {
				loading = false;
				return;
			}
			error = (err as Error).message;
			loading = false;
		}
	}

	let lastDefKey = '';
	$effect(() => {
		if (!visible) return;
		const key = JSON.stringify([card.view, card.parameters, target]);
		if (key !== lastDefKey) {
			const isFirst = lastDefKey === '';
			lastDefKey = key;
			clearTimeout(debounceTimer);
			if (isFirst) {
				if (mounted) generate();
			} else {
				debounceTimer = setTimeout(() => {
					if (mounted) generate();
				}, 500);
			}
		}
	});

	$effect(() => {
		if (!cardEl || visible) return;
		visibilityObserver?.disconnect();
		const el = cardEl;
		visibilityObserver = new IntersectionObserver(
			([entry]) => {
				if (entry.isIntersecting) {
					visible = true;
					visibilityObserver?.disconnect();
					visibilityObserver = undefined;
				}
			},
			{ rootMargin: '200px' },
		);
		visibilityObserver.observe(el);
		return () => {
			visibilityObserver?.disconnect();
			visibilityObserver = undefined;
		};
	});

	$effect(() => {
		if (!plotEl) return;
		resizeObserver?.disconnect();
		const el = plotEl;
		resizeObserver = new ResizeObserver(() => {
			if (resizeRaf) cancelAnimationFrame(resizeRaf);
			resizeRaf = requestAnimationFrame(() => {
				resizeRaf = 0;
				if (Plotly && mounted) resizePlot(el, Plotly);
			});
		});
		resizeObserver.observe(el);
		return () => {
			resizeObserver?.disconnect();
			resizeObserver = undefined;
		};
	});

	onDestroy(() => {
		mounted = false;
		clearTimeout(debounceTimer);
		if (resizeRaf) cancelAnimationFrame(resizeRaf);
		resizeObserver?.disconnect();
		visibilityObserver?.disconnect();
		if (plotEl && Plotly) purgePlot(plotEl, Plotly);
	});
</script>

<div bind:this={cardEl} class="group/card bg-card overflow-hidden flex flex-col h-full relative {showActions ? 'rounded-lg border border-border' : ''}">
	{#if showActions}
		<div class="card-drag-handle flex items-center justify-between px-3 py-1 border-b border-border/50 shrink-0 cursor-grab">
			<div class="flex items-center gap-1 min-w-0">
				{#if onfullscreen}
					<button class="text-xs font-medium text-muted-foreground truncate hover:text-foreground transition-colors cursor-pointer" onclick={onfullscreen}>{label ?? title}</button>
				{:else}
					<span class="text-xs font-medium text-muted-foreground truncate">{label ?? title}</span>
				{/if}
			</div>
			<div class="flex items-center gap-0.5">
				<Button variant="ghost" size="icon" class="h-6 w-6" onclick={onedit}>
					<Pencil class="h-3 w-3" />
				</Button>
				<DropdownMenu.Root>
					<DropdownMenu.Trigger>
						{#snippet child({ props })}
							<Button variant="ghost" size="icon" class="h-6 w-6" {...props}>
								<Ellipsis class="h-3 w-3" />
							</Button>
						{/snippet}
					</DropdownMenu.Trigger>
					<DropdownMenu.Content align="end" class="w-36">
						<DropdownMenu.Item onclick={onremove}>
							<Trash2 class="h-3.5 w-3.5 mr-2" />
							Remove
						</DropdownMenu.Item>
					</DropdownMenu.Content>
				</DropdownMenu.Root>
			</div>
		</div>
	{/if}

	<div class="relative flex-1 min-h-0">
		{#if loading}
			<PlotSkeleton />
		{:else if emptyData}
			<div class="flex flex-col items-center justify-center gap-2 p-6 h-full text-muted-foreground">
				<ChartNoAxesColumn class="h-8 w-8 opacity-40" />
				<p class="text-sm">No data available</p>
			</div>
		{:else if error}
			<div class="flex items-center justify-center p-6 text-sm text-destructive h-full">
				<p>{error}</p>
			</div>
		{:else}
			<div class="overflow-hidden h-full">
				<div bind:this={plotEl} class="w-full h-full"></div>
			</div>
		{/if}
	</div>
</div>

<style>
	:global(.js-plotly-plot),
	:global(.plotly),
	:global(.plot-container),
	:global(.svg-container) {
		width: 100% !important;
	}
</style>

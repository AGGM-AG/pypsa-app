<script lang="ts">
	import type { ViewCardDefinition } from '$lib/stores/reportStore.svelte.js';
	import type { ViewSpec } from '$lib/types.js';
	import { views, type ViewTarget } from '$lib/api/client.js';
	import ViewCard from './ViewCard.svelte';
	import * as Dialog from '$lib/components/ui/dialog';
	import * as Select from '$lib/components/ui/select';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import Button from '$lib/components/ui/button/button.svelte';

	interface Props {
		open: boolean;
		networkId: string;
		folderId?: string | null;
		initialCard?: ViewCardDefinition | null;
		onsave: (card: ViewCardDefinition) => void;
		onclose: () => void;
	}

	let { open = $bindable(), networkId, folderId = null, initialCard = null, onsave, onclose }: Props = $props();

	// catalogue (loaded once per dialog instance)
	let specs = $state<ViewSpec[]>([]);
	let catalogueError = $state<string | null>(null);
	// what the networks can be rendered for (locations, years), per extension
	let selections = $state<Record<string, string[]>>({});

	let target = $derived<ViewTarget>(folderId ? { folderId } : { networkIds: [networkId] });

	// form state
	let name = $state('');
	let viewName = $state('');
	// parameter values as strings (arrays joined by ", "), keyed by schema property
	let values = $state<Record<string, string>>({});
	let flags = $state<Record<string, boolean>>({});

	let spec = $derived(specs.find((s) => s.name === viewName) ?? null);
	let properties = $derived(spec?.params_schema?.properties ?? {});

	$effect(() => {
		if (!open) return;
		if (specs.length === 0) loadCatalogue();
		name = initialCard?.name ?? '';
		viewName = initialCard?.view ?? '';
		values = {};
		flags = {};
		for (const [key, raw] of Object.entries(initialCard?.parameters ?? {})) {
			if (typeof raw === 'boolean') flags[key] = raw;
			else if (Array.isArray(raw)) values[key] = raw.join(', ');
			else if (raw !== null && typeof raw === 'object') values[key] = JSON.stringify(raw);
			else if (raw !== undefined && raw !== null) values[key] = String(raw);
		}
	});

	async function loadCatalogue() {
		try {
			const res = await views.list();
			specs = res.data;
			if (!viewName && specs.length > 0) viewName = specs[0].name;
			if (res.extensions.length > 0) {
				try {
					selections = await views.selections(target, res.extensions[0]);
				} catch {
					selections = {};
				}
			}
		} catch (err) {
			catalogueError = (err as Error).message;
		}
	}

	function fieldKind(schema: Record<string, unknown>): 'boolean' | 'array' | 'object' | 'string' {
		const type = schema.type as string | undefined;
		if (type === 'boolean') return 'boolean';
		if (type === 'array') return 'array';
		if (type === 'object') return 'object';
		return 'string';
	}

	function choices(key: string): string[] | null {
		if (key === 'location' && selections.locations?.length) return selections.locations;
		if (key === 'year' && selections.years?.length) return selections.years;
		return null;
	}

	function buildParameters(): Record<string, unknown> {
		const params: Record<string, unknown> = {};
		for (const [key, schema] of Object.entries(properties)) {
			const kind = fieldKind(schema);
			if (kind === 'boolean') {
				if (key in flags) params[key] = flags[key];
				continue;
			}
			const raw = (values[key] ?? '').trim();
			if (!raw) continue;
			if (kind === 'array') params[key] = raw.split(',').map((s) => s.trim()).filter(Boolean);
			else if (kind === 'object') {
				try {
					params[key] = JSON.parse(raw);
				} catch {
					/* keep the previous value out rather than sending broken JSON */
				}
			} else params[key] = raw;
		}
		return params;
	}

	let previewCard = $derived<ViewCardDefinition>({
		id: initialCard?.id ?? 'preview',
		type: 'view',
		name: name.trim() || undefined,
		view: viewName,
		parameters: buildParameters(),
		x: 0,
		y: 0,
		w: 12,
		h: 7,
	});

	function handleSave() {
		onsave({
			id: initialCard?.id ?? crypto.randomUUID(),
			type: 'view',
			name: name.trim() || undefined,
			view: viewName,
			parameters: buildParameters(),
			x: initialCard?.x ?? 0,
			y: initialCard?.y ?? 0,
			w: initialCard?.w ?? 12,
			h: initialCard?.h ?? 7,
		});
	}
</script>

<Dialog.Root bind:open onOpenChange={(v) => { if (!v) onclose(); }}>
	<Dialog.Content class="sm:max-w-7xl max-h-[90vh] overflow-hidden flex flex-col" onOpenAutoFocus={(e) => e.preventDefault()}>
		<Dialog.Header>
			<Dialog.Title>{initialCard ? 'Edit View' : 'Add View'}</Dialog.Title>
			<Dialog.Description>
				{#if folderId}
					Rendered for all planning years of the registered result folder.
				{:else}
					This network is not part of a registered result folder; only its own year is rendered.
				{/if}
			</Dialog.Description>
		</Dialog.Header>

		<div class="flex gap-6 flex-1 min-h-0 overflow-hidden">
			<!-- Left: settings -->
			<div class="w-1/3 flex flex-col gap-4 overflow-y-auto pr-2">
				<div>
					<label class="text-sm font-medium mb-1.5 block">
						Name
						<input
							type="text"
							class="w-full text-sm border border-border rounded-md px-3 py-1.5 bg-background text-foreground placeholder:text-muted-foreground mt-1.5"
							placeholder={spec?.title ?? ''}
							bind:value={name}
						/>
					</label>
				</div>

				<div>
					<span class="text-sm font-medium mb-1.5 block">View</span>
					{#if catalogueError}
						<p class="text-xs text-destructive">{catalogueError}</p>
					{:else}
						<Select.Root type="single" value={viewName} onValueChange={(v) => (viewName = v)}>
							<Select.Trigger class="w-full">{spec?.title ?? viewName ?? 'Select a view'}</Select.Trigger>
							<Select.Content>
								{#each specs as s (s.name)}
									<Select.Item value={s.name}>{s.title}</Select.Item>
								{/each}
							</Select.Content>
						</Select.Root>
						{#if spec?.description}
							<p class="text-xs text-muted-foreground mt-1">{spec.description}</p>
						{/if}
					{/if}
				</div>

				{#each Object.entries(properties) as [key, schema] (key)}
					{#if !(key === 'year' && spec && !spec.per_year)}
						{@const kind = fieldKind(schema)}
						{@const options = choices(key)}
						<div>
							<span class="text-sm font-medium mb-1.5 block">{(schema.title as string) ?? key}</span>
							{#if kind === 'boolean'}
								<label class="flex items-center gap-2 text-sm">
									<Checkbox checked={flags[key] ?? Boolean(schema.default)} onCheckedChange={(v) => (flags[key] = Boolean(v))} />
									{(schema.description as string) ?? ''}
								</label>
							{:else if options}
								<Select.Root type="single" value={values[key] ?? String(schema.default ?? '')} onValueChange={(v) => (values[key] = v)}>
									<Select.Trigger class="w-full">{values[key] || String(schema.default ?? 'Select')}</Select.Trigger>
									<Select.Content>
										{#each options as opt (opt)}
											<Select.Item value={opt}>{opt}</Select.Item>
										{/each}
									</Select.Content>
								</Select.Root>
							{:else}
								<input
									type="text"
									class="w-full text-sm border border-border rounded-md px-3 py-1.5 bg-background text-foreground placeholder:text-muted-foreground"
									placeholder={kind === 'array' ? 'comma-separated, empty for the default' : String(schema.default ?? '')}
									bind:value={values[key]}
								/>
							{/if}
							{#if kind !== 'boolean' && schema.description}
								<p class="text-xs text-muted-foreground mt-1">{schema.description}</p>
							{/if}
						</div>
					{/if}
				{/each}
			</div>

			<!-- Right: preview -->
			<div class="flex-1 min-w-0 flex flex-col">
				<span class="text-sm font-medium mb-1.5 block">Preview</span>
				<div class="flex-1 min-h-0 rounded-lg border border-border overflow-hidden">
					{#if viewName}
						{#key JSON.stringify([previewCard.view, previewCard.parameters])}
							<ViewCard card={previewCard} {networkId} {folderId} showActions={false} />
						{/key}
					{/if}
				</div>
			</div>
		</div>

		<Dialog.Footer>
			<Button variant="outline" onclick={onclose}>Cancel</Button>
			<Button onclick={handleSave} disabled={!viewName}>{initialCard ? 'Save' : 'Add'}</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>

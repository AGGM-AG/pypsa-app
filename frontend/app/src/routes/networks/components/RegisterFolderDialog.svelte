<script lang="ts">
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Button } from '$lib/components/ui/button';
	import { folders } from '$lib/api/client.js';
	import { toast } from 'svelte-sonner';

	interface Props {
		open: boolean;
		onSuccess?: () => void;
	}

	let { open = $bindable(false), onSuccess }: Props = $props();

	let path = $state('');
	let registering = $state(false);

	$effect(() => {
		if (!open) path = '';
	});

	async function handleSubmit(e: Event) {
		e.preventDefault();
		const trimmed = path.trim();
		if (!trimmed || registering) return;
		registering = true;
		try {
			const folder = await folders.register(trimmed);
			toast.success(`Registered ${folder.name} (${folder.networks.length} networks)`);
			onSuccess?.();
			open = false;
		} catch (err) {
			toast.error((err as Error).message);
		} finally {
			registering = false;
		}
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Content class="max-w-md">
		<Dialog.Header>
			<Dialog.Title>Register result folder</Dialog.Title>
			<Dialog.Description>
				Absolute path of a run's result folder below the configured NETWORK_ROOTS
				(e.g. results/&lt;prefix&gt;/&lt;run&gt;). The folder name is the scenario; every .nc
				file in it or its networks/ subfolder becomes a network named
				"&lt;scenario&gt; &lt;year&gt;". Files stay in place.
			</Dialog.Description>
		</Dialog.Header>
		<form onsubmit={handleSubmit} class="space-y-4">
			<input
				type="text"
				bind:value={path}
				placeholder="/absolute/path/to/results/prefix/run"
				class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
				disabled={registering}
				required
			/>
			<div class="flex justify-end gap-2">
				<Button
					type="button"
					variant="outline"
					size="sm"
					onclick={() => (open = false)}
					disabled={registering}
				>
					Cancel
				</Button>
				<Button type="submit" size="sm" disabled={registering || !path.trim()}>
					{#if registering}
						<LoaderCircle class="h-4 w-4 mr-2 animate-spin" />
						Registering...
					{:else}
						Register
					{/if}
				</Button>
			</div>
		</form>
	</Dialog.Content>
</Dialog.Root>

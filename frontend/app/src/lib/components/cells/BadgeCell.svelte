<script lang="ts">
	import { Badge } from '$lib/components/ui/badge';

	let {
		label,
		variant = 'default',
		icon = undefined
	}: {
		label: string;
		variant?: 'default' | 'secondary' | 'outline' | 'destructive';
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		icon?: any;
	} = $props();
</script>

<Badge {variant} class="gap-1">
	{#if icon}
		{@const Icon = icon}
		<Icon class="size-3" />
	{/if}
	{label}
</Badge>

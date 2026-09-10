<script lang="ts">
	import * as Empty from '$lib/components/ui/empty';

	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	let { icon: Icon, title, description }: { icon: any; title: string; description: string } = $props();
</script>

<Empty.Root>
	<Empty.Header>
		<Empty.Media variant="icon">
			<Icon />
		</Empty.Media>
		<Empty.Title>{title}</Empty.Title>
		<Empty.Description>{description}</Empty.Description>
	</Empty.Header>
</Empty.Root>

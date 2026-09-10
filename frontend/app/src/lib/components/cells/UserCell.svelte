<script lang="ts">
	import * as Avatar from '$lib/components/ui/avatar';

	let { user }: { user: { username: string; avatar_url?: string } } = $props();
</script>

<div class="flex items-center gap-2">
	<Avatar.Root class="h-6 w-6">
		{#if user.avatar_url}
			<Avatar.Image src={user.avatar_url} alt={user.username} />
		{/if}
		<Avatar.Fallback class="text-xs">
			{user.username.substring(0, 2).toUpperCase()}
		</Avatar.Fallback>
	</Avatar.Root>
	<span class="font-medium">{user.username}</span>
</div>

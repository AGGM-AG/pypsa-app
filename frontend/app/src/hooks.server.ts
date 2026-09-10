import type { Handle } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';

const API_BASE_URL = env.BACKEND_URL || 'http://localhost:8000';

export const handle: Handle = async ({ event, resolve }) => {
	// Proxy /api requests to the backend
	if (event.url.pathname.startsWith('/api')) {
		const targetUrl = `${API_BASE_URL}${event.url.pathname}${event.url.search}`;

		try {
			const response = await fetch(targetUrl, {
				method: event.request.method,
				headers: event.request.headers,
				body: event.request.method !== 'GET' && event.request.method !== 'HEAD'
					? await event.request.text()
					: undefined
			});

			// Create a new response with the proxied content
			const responseBody = await response.text();

			const headers: Record<string, string> = {
				'content-type': response.headers.get('content-type') || 'application/json',
				'cache-control': response.headers.get('cache-control') || 'no-cache',
			};
			const setCookie = response.headers.get('set-cookie');
			if (setCookie) headers['set-cookie'] = setCookie;

			return new Response(responseBody, {
				status: response.status,
				statusText: response.statusText,
				headers
			});
		} catch (error) {
			console.error('API proxy error:', error);
			return new Response(
				JSON.stringify({
					detail: `Failed to connect to backend: ${(error as Error).message}`
				}),
				{
					status: 502,
					headers: { 'content-type': 'application/json' }
				}
			);
		}
	}

	// For non-API requests, proceed as normal
	return resolve(event);
};

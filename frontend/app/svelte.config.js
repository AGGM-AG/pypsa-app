import adapter from '@sveltejs/adapter-static';

// Use environment variable to determine output path
// In Docker builds, use 'build' directory (default for adapter-static)
// In local development, output directly to backend static directory
const isDockerBuild = process.env.DOCKER_BUILD === 'true';
const outputPath = isDockerBuild ? 'build' : '../../src/pypsa_app/backend/static/app';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	kit: {
		// Use static adapter for building to static files that can be served by FastAPI
		adapter: adapter({
			pages: outputPath,
			assets: outputPath,
			fallback: 'index.html',  // SPA mode - all routes return index.html
			precompress: false,
			strict: true
		}),
		// Keep API routes pointing to /api/v1
		paths: {
			base: ''
		}
	}
};

export default config;

/**
 * Welcome to Cloudflare Workers! This is your first worker.
 *
 * - Run `npm run dev` in your terminal to start a development server
 * - Open a browser tab at http://localhost:8787/ to see your worker in action
 * - Run `npm run deploy` to publish your worker
 *
 * Bind resources to your worker in `wrangler.jsonc`. After adding bindings, a type definition for the
 * `Env` object can be regenerated with `npm run cf-typegen`.
 *
 * Learn more at https://developers.cloudflare.com/workers/
 */

interface Env {
    MAPTILER_API_KEY: string;
}

export default {
    async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
        const apiKey = env.MAPTILER_API_KEY;
        if (!apiKey) {
            return new Response("MapTiler API key is not configured", {
                status: 500,
                headers: { "Access-Control-Allow-Origin": "*" },
            });
        }

        const url = new URL(request.url);

        // Handle CORS preflight
        if (request.method === "OPTIONS") {
            return new Response(null, {
                status: 204, // No Content
                headers: {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET,OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Max-Age": "86400", // Cache preflight for 24 hours
                },
            });
        }

        // Match /:z/:x/:y.pbf
        const tileMatch = url.pathname.match(/(\d+)\/(\d+)\/(\d+)\.pbf$/);
        if (!tileMatch) {
            return new Response("Invalid tile request", {
                status: 400,
                headers: { "Access-Control-Allow-Origin": "*" },
            });
        }

        const [_, z, x, y] = tileMatch;

        // Construct MapTiler tile request URL
        const tileUrl = `https://api.maptiler.com/tiles/v3-4326/${z}/${x}/${y}.pbf?key=${apiKey}`;

        // Create a cache key based on the requested URL path without the API key
        const cacheKey = new Request(`https://api.maptiler.com/tiles/v3-4326/${z}/${x}/${y}.pbf`, {
            method: "GET",
            headers: request.headers
        });

        // Try to find the response in the cache
        const cache = caches.default;
        let response = await cache.match(cacheKey);

        // If we have a cache hit, return it
        if (response) {
            return new Response(response.body, {
                status: 200,
                headers: {
                    "Content-Type": "application/x-protobuf",
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=86400", // Cache for 1 day
                    "CF-Cache-Status": "HIT",
                    "Age": response.headers.get("Age") || "0"
                },
            });
        }

        // Cache miss, proceed with the external request
        try {
            response = await fetch(tileUrl, {
                method: "GET",
                headers: { 
                    "User-Agent": "Cloudflare Worker",
                    "Accept": "application/x-protobuf"
                },
            });

            if (!response.ok) {
                return new Response(`Failed to fetch tile: ${response.statusText}`, {
                    status: response.status,
                    headers: { "Access-Control-Allow-Origin": "*" },
                });
            }

            // Clone the response so we can modify headers before caching
            const clonedResponse = new Response(response.body, response);
            
            // Set appropriate cache headers
            const responseHeaders = new Headers(clonedResponse.headers);
            responseHeaders.set("Content-Type", "application/x-protobuf");
            responseHeaders.set("Access-Control-Allow-Origin", "*");
            responseHeaders.set("Cache-Control", "public, max-age=86400"); // 1 day
            responseHeaders.set("CF-Cache-Status", "MISS");
            
            // Create the response we'll return to the client
            const finalResponse = new Response(clonedResponse.body, {
                status: 200,
                headers: responseHeaders,
            });

            // Create a new response for the cache (we need to clone again because response bodies can only be used once)
            const cacheResponse = new Response(response.clone().body, {
                status: 200,
                headers: {
                    "Content-Type": "application/x-protobuf",
                    "Cache-Control": "public, max-age=86400", // 1 day
                }
            });

            // Store the response in the cache
            ctx.waitUntil(cache.put(cacheKey, cacheResponse));

            return finalResponse;
        } catch (error) {
            return new Response(`Error fetching tile: ${error.message}`, {
                status: 500,
                headers: { "Access-Control-Allow-Origin": "*" },
            });
        }
    },
};
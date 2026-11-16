const LOCAL_CALLBACK = "http://127.0.0.1:8374/callback";

const NO_STORE_HEADERS = {
	"Cache-Control": "no-store",
	"Referrer-Policy": "no-referrer",
};

/**
 * Sends the browser from FreshBooks' OAuth redirect to the `fb auth login`
 * listener on 127.0.0.1:8374, keeping the query string (code, state, error).
 * FreshBooks rejects localhost redirect URIs, so this fixed HTTPS address
 * stands in for one. It stores and logs nothing.
 */
function relayCallback(url: URL): Response {
	return new Response(null, {
		status: 302,
		headers: { ...NO_STORE_HEADERS, Location: `${LOCAL_CALLBACK}${url.search}` },
	});
}

export default {
	fetch(request) {
		const url = new URL(request.url);
		if (request.method !== "GET" && request.method !== "HEAD") {
			return new Response("Method not allowed", { status: 405, headers: { Allow: "GET, HEAD" } });
		}
		if (url.pathname === "/callback") {
			return relayCallback(url);
		}
		return new Response("Not found", { status: 404, headers: NO_STORE_HEADERS });
	},
} satisfies ExportedHandler;

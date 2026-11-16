const LOCAL_CALLBACK = "http://127.0.0.1:8374/callback";

const REPO_URL = "https://github.com/mysticcoders/freshbooks-tools";

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

/**
 * Explains what this host is for anyone who opens it directly.
 */
function landingPage(): Response {
	const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>freshbooks-tools OAuth relay</title>
<style>
body { font-family: system-ui, sans-serif; max-width: 40rem; margin: 3rem auto; padding: 0 1rem; line-height: 1.5; color: #1f2328; background: #fff; }
code { background: #f1f3f5; padding: 0.1rem 0.3rem; border-radius: 4px; }
@media (prefers-color-scheme: dark) { body { color: #e6edf3; background: #0d1117; } code { background: #21262d; } }
</style>
</head>
<body>
<h1>freshbooks-tools OAuth relay</h1>
<p>FreshBooks only redirects to HTTPS addresses and rejects localhost. Set your FreshBooks app's redirect URI to
<code>https://freshbooks-tools.wecodefire.com/callback</code> and <code>fb auth login</code> receives the
authorization code on <code>127.0.0.1:8374</code> without a tunnel.</p>
<p>This relay only redirects your browser. It never sees your client secret, and it stores and logs nothing.
The source is in the <a href="${REPO_URL}/tree/main/relay">freshbooks-tools repository</a>.</p>
</body>
</html>`;
	return new Response(html, {
		headers: { ...NO_STORE_HEADERS, "Content-Type": "text/html; charset=utf-8" },
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
		if (url.pathname === "/") {
			return landingPage();
		}
		return new Response("Not found", { status: 404, headers: NO_STORE_HEADERS });
	},
} satisfies ExportedHandler;

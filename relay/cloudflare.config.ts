import { defineConfig } from "cf/config";
import * as entrypoint from "./src/index.ts" with { type: "cf-worker" };

export default defineConfig({
	worker: {
		name: "freshbooks-tools-relay",
		compatibilityDate: "2026-10-23",
		entrypoint,
		domains: ["freshbooks-tools.wecodefire.com"],
		assets: { runWorkerFirst: ["/callback"], htmlHandling: "auto-trailing-slash", notFoundHandling: "none" },
		workersDev: false,
		previewUrls: false,
		observability: { enabled: false },
	},
});

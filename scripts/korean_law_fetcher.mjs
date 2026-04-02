import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const action = process.argv[2];
const payload = JSON.parse(process.argv[3] ?? "{}");
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "..");
const defaultMcpDir = path.resolve(repoRoot, "external", "korean-law-mcp");
const mcpDir = process.env.KOREAN_LAW_MCP_DIR || defaultMcpDir;

if (!process.env.LAW_OC) {
  const envPath = path.join(mcpDir, ".env");
  if (fs.existsSync(envPath)) {
    for (const line of fs.readFileSync(envPath, "utf-8").split(/\r?\n/)) {
      if (line.startsWith("LAW_OC=")) {
        process.env.LAW_OC = line.split("=", 2)[1].trim();
        break;
      }
    }
  }
}

const { LawApiClient } = await import(pathToFileURL(path.join(mcpDir, "build/lib/api-client.js")).href);
const client = new LawApiClient({ apiKey: process.env.LAW_OC || "" });

let raw;
if (action === "law_history") {
  raw = await client.getLawHistory(payload);
} else if (action === "law_text") {
  raw = await client.getLawText(payload);
} else if (action === "search_admin_rule") {
  raw = await client.searchAdminRule(payload);
} else if (action === "admin_rule_detail") {
  raw = await client.fetchApi({
    endpoint: "lawService.do",
    target: "admrul",
    type: "XML",
    extraParams: { ID: String(payload.id) },
  });
} else {
  throw new Error(`Unsupported action: ${action}`);
}

process.stdout.write(JSON.stringify({ action, raw }));

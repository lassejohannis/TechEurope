// Hardcoded "AGENTS.md"-style prompt that drops the integrating IDE agent
// (Claude Code, Cursor, Codex) directly into action: read it, find the right
// place to wire Qontext in, write the code, run the verification curl.

export type BuildPromptOpts = {
  apiBaseUrl: string
  token: string | null
}

const TOKEN_PLACEHOLDER = '<paste your token here>'

export function buildAgentPrompt({ apiBaseUrl, token }: BuildPromptOpts): string {
  const tokenStr = token ?? TOKEN_PLACEHOLDER
  return `# Wire Qontext into this codebase

You are integrating **Qontext**, a knowledge-graph + memory engine, into the
project I just opened with you. Your job is to figure out where the LLM
lives in this repo and register Qontext's tools so the model can call them.

## Connection details

- **Base URL:** ${apiBaseUrl}
- **Bearer token:** ${tokenStr}
- **MCP server:** ${apiBaseUrl}/mcp/sse  (FastMCP / SSE transport)
- **REST root:** ${apiBaseUrl}/api/

The token must go in the \`Authorization: Bearer <token>\` header on every
request. Treat it as a secret — never commit it; load from an env var.

## What Qontext exposes

A bi-temporal entity-resolution graph. Three primitives:

1. **Entities** — people, organizations, communications, documents, products…
2. **Facts** — bi-temporal edges between entities, every one carries
   \`{value, confidence, evidence: [...]}\`.
3. **Resolutions** — pending HITL decisions (entity merges, fact conflicts).

## Five MCP tools to register

\`\`\`json
${MCP_TOOL_SCHEMAS}
\`\`\`

REST equivalents (in case MCP isn't available in this stack):

- \`POST /api/search\` — body \`{query, limit}\` → ranked entities
- \`GET /api/entities/{entity_id}\` — entity card with active facts
- \`GET /api/facts/{fact_id}/provenance\` — full evidence chain
- \`GET /api/changes/recent?limit=N\` — recent fact-change feed
- \`POST /api/vfs/propose-fact\` — submit an agent-derived fact

## Your task

1. **Detect the project's stack.** Look at \`package.json\` / \`pyproject.toml\`
   / \`Cargo.toml\` to figure out: language, LLM SDK in use (OpenAI,
   Anthropic, Vercel AI SDK, LangChain, raw, etc.), agent framework if any.

2. **Pick the integration point.**
   - If MCP is supported (Claude Desktop, Cursor, Claude Code clients),
     drop the MCP server into the appropriate \`mcp.json\` file.
   - If the project uses an agent SDK, register the five tools above as
     SDK-native tool definitions and add a dispatcher that translates tool
     calls into HTTP requests against \`${apiBaseUrl}/api/...\`.
   - If no LLM app exists yet, scaffold a minimal one in \`/qontext_demo\`
     using whatever the project's primary language is.

3. **Add the token securely.**
   - Add \`QONTEXT_TOKEN=${tokenStr}\` to \`.env.example\`.
   - Add \`QONTEXT_BASE=${apiBaseUrl}\` likewise.
   - Make sure both are gitignored (\`.env\` should already be).
   - Read them via environment in code, never hardcode.

4. **Write a smoke test.** Add a \`qontext_health\` script that calls
   \`/api/search\` once and prints the first entity. Show me you can run it.

5. **Verify with this curl** before reporting back:

\`\`\`bash
curl -sX POST "${apiBaseUrl}/api/search" \\
  -H "Authorization: Bearer ${tokenStr}" \\
  -H "Content-Type: application/json" \\
  -d '{"query":"Inazuma","limit":3}'
\`\`\`

If that returns 200 OK with non-empty \`results\`, you're done.
If it returns 401, the token is wrong — stop and surface the error.
If it returns connection refused, the engine isn't running on
\`${apiBaseUrl}\` — surface that too.

## Style notes

- No new abstractions or wrappers around the SDK — use it directly.
- Prefer existing config patterns in the repo over inventing new ones.
- One tight smoke test, not a full test suite.
- Keep the diff small enough that I can review it in one sitting.
`
}

const MCP_TOOL_SCHEMAS = `{
  "search_memory": {
    "description": "Hybrid semantic + structural search across the knowledge graph.",
    "input": { "query": "string", "k": "integer (default 10)", "entity_type": "string?" }
  },
  "get_entity": {
    "description": "Fetch a full entity card by id.",
    "input": { "entity_id": "string" }
  },
  "get_fact_provenance": {
    "description": "Return the full evidence chain for a fact.",
    "input": { "fact_id": "string" }
  },
  "list_recent_changes": {
    "description": "Stream recent fact changes (insert/update/supersede).",
    "input": { "since": "ISO8601?", "limit": "integer (default 20)" }
  },
  "propose_fact": {
    "description": "Submit an agent-derived fact for resolution & storage.",
    "input": {
      "subject_id": "string",
      "predicate": "string",
      "object_id": "string?",
      "object_literal": "object?",
      "confidence": "number"
    }
  }
}`

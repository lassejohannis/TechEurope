// Data definitions for the /connect onboarding page.
// Snippets contain {{TOKEN}} and {{API_BASE_URL}} placeholders that are
// replaced at render time with the user's freshly issued token + the
// deployed backend URL.

export type Tier = 'mcp-clients' | 'agent-sdks' | 'automation' | 'raw'

export type SnippetLanguage =
  | 'json'
  | 'bash'
  | 'python'
  | 'typescript'
  | 'text'
  | 'markdown'

export type ConnectorStep = {
  title: string
  snippet?: string
  language?: SnippetLanguage
  note?: string
}

export type LanguageVariant = {
  language: SnippetLanguage
  label: string
  steps: ConnectorStep[]
  testCommand?: string
}

export type Connector = {
  id: string
  name: string
  tier: Tier
  emoji: string
  blurb: string
  languages: LanguageVariant[]
}

export type VibeAgent = {
  id: 'claude-code' | 'cursor' | 'codex'
  name: string
  emoji: string
  invokeSummary: string
  invokeSteps: string[]
}

export const TIER_LABEL: Record<Tier, string> = {
  'mcp-clients': 'MCP clients',
  'agent-sdks': 'Agent SDKs',
  automation: 'Automation',
  raw: 'Raw HTTP',
}

export const TIER_BLURB: Record<Tier, string> = {
  'mcp-clients': 'Plug Qontext into IDEs that already speak the Model Context Protocol.',
  'agent-sdks': 'Wire Qontext into LLM apps via OpenAI, Anthropic, or Vercel AI SDK.',
  automation: 'Hook Qontext into low-code workflow tools or webhook receivers.',
  raw: 'Drop down to plain HTTP for quick checks or unsupported runtimes.',
}

export const VIBE_AGENTS: VibeAgent[] = [
  {
    id: 'claude-code',
    name: 'Claude Code',
    emoji: '⌨️',
    invokeSummary: 'CLI agent that lives in your repo terminal.',
    invokeSteps: [
      'Open your repo in a terminal.',
      'Run `claude` to start a Claude Code session.',
      'Paste the prompt and press Enter — Claude Code will scan your project, find the right place to register Qontext, and write the integration code.',
    ],
  },
  {
    id: 'cursor',
    name: 'Cursor',
    emoji: '⚡',
    invokeSummary: 'AI-first code editor.',
    invokeSteps: [
      'Open your project in Cursor.',
      'Press ⌘+L (or Ctrl+L) to open the Composer.',
      'Paste the prompt and hit Enter — Cursor will edit files across your repo to wire Qontext in.',
    ],
  },
  {
    id: 'codex',
    name: 'Codex CLI',
    emoji: '🤖',
    invokeSummary: "OpenAI's CLI agent for autonomous code edits.",
    invokeSteps: [
      'Install Codex if needed: `npm i -g @openai/codex` (or use the IDE extension).',
      'Run `codex` in your repo root.',
      'Paste the prompt — Codex plans the change, applies edits, and runs the verification curl.',
    ],
  },
]

// ─── Snippet text constants (deduped between Python/TS variants) ─────────────

const OPENAI_TOOLS_PY = `[
  {
    "type": "function",
    "function": {
      "name": "search_memory",
      "description": "Hybrid semantic + structural search across the knowledge graph. Returns ranked entities with trust scores.",
      "parameters": {
        "type": "object",
        "properties": {
          "query": { "type": "string" },
          "k": { "type": "integer", "default": 10 },
          "entity_type": { "type": "string", "nullable": true }
        },
        "required": ["query"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "get_entity",
      "description": "Fetch a full entity card by id, including trust score and active facts.",
      "parameters": {
        "type": "object",
        "properties": { "entity_id": { "type": "string" } },
        "required": ["entity_id"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "propose_fact",
      "description": "Submit an agent-derived fact. Engine resolves entities and merges or supersedes existing facts.",
      "parameters": {
        "type": "object",
        "properties": {
          "subject_id": { "type": "string" },
          "predicate": { "type": "string" },
          "object_id": { "type": "string", "nullable": true },
          "object_literal": { "type": "object", "nullable": true },
          "confidence": { "type": "number" }
        },
        "required": ["subject_id", "predicate", "confidence"]
      }
    }
  }
]`

const ANTHROPIC_TOOLS_PY = `[
  {
    "name": "search_memory",
    "description": "Hybrid semantic + structural search across the knowledge graph.",
    "input_schema": {
      "type": "object",
      "properties": {
        "query": { "type": "string" },
        "k": { "type": "integer" },
        "entity_type": { "type": "string" }
      },
      "required": ["query"]
    }
  },
  {
    "name": "get_entity",
    "description": "Fetch a full entity card by id.",
    "input_schema": {
      "type": "object",
      "properties": { "entity_id": { "type": "string" } },
      "required": ["entity_id"]
    }
  },
  {
    "name": "propose_fact",
    "description": "Submit an agent-derived fact for resolution & storage.",
    "input_schema": {
      "type": "object",
      "properties": {
        "subject_id": { "type": "string" },
        "predicate": { "type": "string" },
        "object_id": { "type": "string" },
        "confidence": { "type": "number" }
      },
      "required": ["subject_id", "predicate", "confidence"]
    }
  }
]`

// ─── Connectors ──────────────────────────────────────────────────────────────

export const CONNECTORS: Connector[] = [
  // ─── Tier: MCP clients ─────────────────────────────────────────────────────
  {
    id: 'claude-desktop',
    name: 'Claude Desktop',
    tier: 'mcp-clients',
    emoji: '🖥️',
    blurb: 'Add Qontext as an MCP server in Claude Desktop',
    languages: [
      {
        language: 'json',
        label: 'JSON',
        testCommand: `curl -s "{{API_BASE_URL}}/api/health"`,
        steps: [
          {
            title: 'Open your Claude Desktop config',
            language: 'bash',
            snippet: `# macOS
open "$HOME/Library/Application Support/Claude/claude_desktop_config.json"

# Windows
notepad %APPDATA%\\Claude\\claude_desktop_config.json`,
            note: 'Create the file if it does not exist yet.',
          },
          {
            title: 'Add the Qontext MCP server',
            language: 'json',
            snippet: `{
  "mcpServers": {
    "qontext": {
      "url": "{{API_BASE_URL}}/mcp/sse",
      "headers": {
        "Authorization": "Bearer {{TOKEN}}"
      }
    }
  }
}`,
            note: 'Restart Claude Desktop. The MCP icon should appear in the chat bar.',
          },
        ],
      },
    ],
  },
  {
    id: 'cursor',
    name: 'Cursor',
    tier: 'mcp-clients',
    emoji: '⚡',
    blurb: 'Wire Qontext into Cursor as an MCP tool provider',
    languages: [
      {
        language: 'json',
        label: 'JSON',
        testCommand: `curl -s "{{API_BASE_URL}}/api/health"`,
        steps: [
          {
            title: 'Open Cursor MCP config',
            language: 'bash',
            snippet: `open "$HOME/.cursor/mcp.json"`,
          },
          {
            title: 'Register Qontext',
            language: 'json',
            snippet: `{
  "mcpServers": {
    "qontext": {
      "url": "{{API_BASE_URL}}/mcp/sse",
      "headers": {
        "Authorization": "Bearer {{TOKEN}}"
      }
    }
  }
}`,
            note: 'Reload Cursor. Use ⌘+L and ask Cursor to use the search_memory tool.',
          },
        ],
      },
    ],
  },
  {
    id: 'claude-code',
    name: 'Claude Code',
    tier: 'mcp-clients',
    emoji: '⌨️',
    blurb: 'Project-scoped MCP server for the Claude Code CLI',
    languages: [
      {
        language: 'json',
        label: 'JSON',
        steps: [
          {
            title: 'Add to your project .mcp.json',
            language: 'json',
            snippet: `{
  "mcpServers": {
    "qontext": {
      "type": "http",
      "url": "{{API_BASE_URL}}/mcp/sse",
      "headers": {
        "Authorization": "Bearer {{TOKEN}}"
      }
    }
  }
}`,
            note: 'Place the file at the repo root. Claude Code will load it automatically.',
          },
        ],
      },
    ],
  },

  // ─── Tier: Agent SDKs ──────────────────────────────────────────────────────
  {
    id: 'openai-agents',
    name: 'OpenAI Agents',
    tier: 'agent-sdks',
    emoji: '🟢',
    blurb: 'Function-calling tools backed by Qontext REST',
    languages: [
      {
        language: 'python',
        label: 'Python',
        steps: [
          {
            title: 'Define the Qontext tools',
            language: 'python',
            snippet: `from openai import OpenAI
import requests

QONTEXT_BASE = "{{API_BASE_URL}}"
QONTEXT_TOKEN = "{{TOKEN}}"

QONTEXT_TOOLS = ${OPENAI_TOOLS_PY}

def call_qontext_tool(name: str, args: dict) -> dict:
    headers = {"Authorization": f"Bearer {QONTEXT_TOKEN}"}
    if name == "search_memory":
        return requests.post(f"{QONTEXT_BASE}/api/search",
                             json=args, headers=headers, timeout=10).json()
    if name == "get_entity":
        return requests.get(f"{QONTEXT_BASE}/api/entities/{args['entity_id']}",
                            headers=headers, timeout=10).json()
    if name == "propose_fact":
        return requests.post(f"{QONTEXT_BASE}/api/vfs/propose-fact",
                             json=args, headers=headers, timeout=10).json()
    raise ValueError(f"Unknown tool: {name}")

# Pass QONTEXT_TOOLS to client.chat.completions.create(tools=...)`,
          },
        ],
      },
      {
        language: 'typescript',
        label: 'TypeScript',
        steps: [
          {
            title: 'Define the Qontext tools',
            language: 'typescript',
            snippet: `import OpenAI from 'openai'

const QONTEXT_BASE = '{{API_BASE_URL}}'
const QONTEXT_TOKEN = '{{TOKEN}}'

export const QONTEXT_TOOLS = [
  {
    type: 'function' as const,
    function: {
      name: 'search_memory',
      description: 'Hybrid semantic + structural search across the knowledge graph.',
      parameters: {
        type: 'object',
        properties: {
          query: { type: 'string' },
          k: { type: 'integer', default: 10 },
          entity_type: { type: 'string', nullable: true },
        },
        required: ['query'],
      },
    },
  },
  // …get_entity, propose_fact (see Python tab for the full list)
]

export async function callQontextTool(name: string, args: any) {
  const headers = {
    'Content-Type': 'application/json',
    Authorization: \`Bearer \${QONTEXT_TOKEN}\`,
  }
  if (name === 'search_memory') {
    const r = await fetch(\`\${QONTEXT_BASE}/api/search\`, {
      method: 'POST', headers, body: JSON.stringify(args),
    })
    return r.json()
  }
  if (name === 'get_entity') {
    const r = await fetch(\`\${QONTEXT_BASE}/api/entities/\${args.entity_id}\`, { headers })
    return r.json()
  }
  if (name === 'propose_fact') {
    const r = await fetch(\`\${QONTEXT_BASE}/api/vfs/propose-fact\`, {
      method: 'POST', headers, body: JSON.stringify(args),
    })
    return r.json()
  }
  throw new Error(\`Unknown tool: \${name}\`)
}`,
          },
        ],
      },
    ],
  },
  {
    id: 'anthropic-tools',
    name: 'Anthropic Tool Use',
    tier: 'agent-sdks',
    emoji: '🟠',
    blurb: 'Use Qontext as tools in the Anthropic Messages API',
    languages: [
      {
        language: 'python',
        label: 'Python',
        steps: [
          {
            title: 'Define the Qontext tools array',
            language: 'python',
            snippet: `import anthropic
import requests

QONTEXT_BASE = "{{API_BASE_URL}}"
QONTEXT_TOKEN = "{{TOKEN}}"

tools = ${ANTHROPIC_TOOLS_PY}

client = anthropic.Anthropic()
resp = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "What do we know about Inazuma?"}],
)

def dispatch(block):
    headers = {"Authorization": f"Bearer {QONTEXT_TOKEN}"}
    if block.name == "search_memory":
        return requests.post(f"{QONTEXT_BASE}/api/search",
                             json=block.input, headers=headers).json()
    # … get_entity, propose_fact dispatchers`,
          },
        ],
      },
      {
        language: 'typescript',
        label: 'TypeScript',
        steps: [
          {
            title: 'Define the Qontext tools array',
            language: 'typescript',
            snippet: `import Anthropic from '@anthropic-ai/sdk'

const QONTEXT_BASE = '{{API_BASE_URL}}'
const QONTEXT_TOKEN = '{{TOKEN}}'

export const tools = [
  {
    name: 'search_memory',
    description: 'Hybrid semantic + structural search across the knowledge graph.',
    input_schema: {
      type: 'object',
      properties: {
        query: { type: 'string' },
        k: { type: 'integer' },
        entity_type: { type: 'string' },
      },
      required: ['query'],
    },
  },
  // …get_entity, propose_fact
]

const client = new Anthropic()
const resp = await client.messages.create({
  model: 'claude-opus-4-7',
  max_tokens: 1024,
  tools,
  messages: [{ role: 'user', content: 'What do we know about Inazuma?' }],
})

async function dispatch(block: any) {
  const headers = { Authorization: \`Bearer \${QONTEXT_TOKEN}\` }
  if (block.name === 'search_memory') {
    const r = await fetch(\`\${QONTEXT_BASE}/api/search\`, {
      method: 'POST', headers, body: JSON.stringify(block.input),
    })
    return r.json()
  }
  // …
}`,
          },
        ],
      },
    ],
  },
  {
    id: 'vercel-ai-sdk',
    name: 'Vercel AI SDK',
    tier: 'agent-sdks',
    emoji: '▲',
    blurb: 'TypeScript helpers for Next.js + AI SDK',
    languages: [
      {
        language: 'typescript',
        label: 'TypeScript',
        steps: [
          {
            title: 'Define a Qontext tool with the AI SDK',
            language: 'typescript',
            snippet: `import { tool } from 'ai'
import { z } from 'zod'

const QONTEXT_BASE = '{{API_BASE_URL}}'
const QONTEXT_TOKEN = '{{TOKEN}}'

export const searchMemory = tool({
  description: 'Hybrid semantic + structural search across the org knowledge graph.',
  parameters: z.object({
    query: z.string(),
    k: z.number().int().default(10).optional(),
    entity_type: z.string().optional(),
  }),
  execute: async (args) => {
    const r = await fetch(\`\${QONTEXT_BASE}/api/search\`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: \`Bearer \${QONTEXT_TOKEN}\`,
      },
      body: JSON.stringify(args),
    })
    return r.json()
  },
})

// Use: streamText({ model, tools: { searchMemory }, prompt })`,
          },
        ],
      },
    ],
  },

  // ─── Tier: Automation ──────────────────────────────────────────────────────
  {
    id: 'n8n',
    name: 'n8n',
    tier: 'automation',
    emoji: '🔗',
    blurb: 'Wire Qontext into n8n workflows via HTTP Request node',
    languages: [
      {
        language: 'text',
        label: 'Setup',
        steps: [
          {
            title: 'Add an HTTP Request node',
            language: 'text',
            snippet: `Method:        POST
URL:           {{API_BASE_URL}}/api/search
Authentication: Header Auth
Header Name:   Authorization
Header Value:  Bearer {{TOKEN}}

Send Body:     JSON
Body:          { "query": "{{ $json.query }}", "limit": 5 }`,
            note: 'Hook the output to any downstream node. The response.results array is ranked by trust × freshness.',
          },
        ],
      },
    ],
  },
  {
    id: 'zapier',
    name: 'Zapier / Make',
    tier: 'automation',
    emoji: '🟣',
    blurb: 'Subscribe to Qontext events via outbound webhooks',
    languages: [
      {
        language: 'bash',
        label: 'Setup',
        steps: [
          {
            title: 'Create a webhook receiver in Zapier/Make',
            language: 'text',
            note: 'Spin up a "Catch Hook" trigger and copy its public URL.',
          },
          {
            title: 'Register the URL with Qontext',
            language: 'bash',
            snippet: `curl -X POST "{{API_BASE_URL}}/api/admin/webhooks" \\
  -H "Authorization: Bearer {{TOKEN}}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "url": "https://hooks.zapier.com/hooks/catch/...",
    "event_types": ["fact.created", "fact.superseded", "entity.merged"]
  }'`,
            note: 'The response includes a one-time `secret` for HMAC verification — save it in your Zap.',
          },
          {
            title: 'Verify HMAC in Zap (Code step)',
            language: 'typescript',
            snippet: `import crypto from 'crypto'

const SECRET = '<paste secret from /api/admin/webhooks response>'
const sig = inputData.headers['x-qontext-signature']
const expected = 'sha256=' + crypto.createHmac('sha256', SECRET)
  .update(inputData.rawBody).digest('hex')
if (sig !== expected) throw new Error('Invalid signature')

return inputData.body`,
          },
        ],
      },
    ],
  },

  // ─── Tier: Raw HTTP ────────────────────────────────────────────────────────
  {
    id: 'curl',
    name: 'Raw HTTP / curl',
    tier: 'raw',
    emoji: '🌐',
    blurb: 'Quick and dirty REST examples',
    languages: [
      {
        language: 'bash',
        label: 'curl',
        testCommand: `curl -s "{{API_BASE_URL}}/api/health"`,
        steps: [
          {
            title: 'Search the graph',
            language: 'bash',
            snippet: `curl -X POST "{{API_BASE_URL}}/api/search" \\
  -H "Authorization: Bearer {{TOKEN}}" \\
  -H "Content-Type: application/json" \\
  -d '{"query":"Inazuma","limit":5}'`,
          },
          {
            title: 'Fetch an entity card',
            language: 'bash',
            snippet: `curl -H "Authorization: Bearer {{TOKEN}}" \\
  "{{API_BASE_URL}}/api/entities/organization:inazuma-com"`,
          },
          {
            title: 'Stream the change feed',
            language: 'bash',
            snippet: `curl -H "Authorization: Bearer {{TOKEN}}" \\
  "{{API_BASE_URL}}/api/changes/recent?limit=20"`,
          },
        ],
      },
    ],
  },
  {
    id: 'postman',
    name: 'Postman',
    tier: 'raw',
    emoji: '📮',
    blurb: 'Import the auto-generated OpenAPI spec',
    languages: [
      {
        language: 'text',
        label: 'Import',
        steps: [
          {
            title: 'Import OpenAPI into Postman',
            language: 'text',
            snippet: `1. Open Postman → File → Import
2. Paste this URL:
   {{API_BASE_URL}}/openapi.json
3. Add a collection-wide Authorization header:
   Authorization: Bearer {{TOKEN}}`,
            note: 'All ~50 REST endpoints become first-class requests with example bodies.',
          },
        ],
      },
    ],
  },
]

export const TIER_ORDER: Tier[] = ['mcp-clients', 'agent-sdks', 'automation', 'raw']

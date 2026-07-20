# Vaultly MCP Server

This is a Model Context Protocol (MCP) server that exposes your Vaultly knowledge base to other AI agents and IDEs — while keeping retrieval strictly scoped to **your own** documents.

## How it works
This server exposes exactly one tool: `query_localrag`.
When an AI agent (like Claude Desktop or Cursor) decides it needs to search your files, it will call this tool. The tool makes an authenticated HTTP request to your Vaultly backend (`/query`) using your personal API token, and formats the ranked passages and file citations back into text for the agent to read. Because the request is authenticated as you, only your documents are searched — never any other user's.

## Prerequisites
1. A running Vaultly backend — the hosted service, or your own `docker-compose up -d` stack.
2. A **personal API token**. Sign in to the Vaultly dashboard and create one under **Settings → API tokens**. The token is shown once — copy it immediately.
3. Node.js installed on your host machine.
4. Install dependencies in this directory:
   ```bash
   cd mcp
   npm install
   ```

## Configuration

Set these environment variables before starting the server (e.g. in your MCP client's `env` config):

| Variable | Default | Purpose |
| --- | --- | --- |
| `VAULTLY_API_URL` | `http://127.0.0.1:8000` | Base URL of your Vaultly backend (use your hosted URL here) |
| `VAULTLY_MCP_TOKEN` | *(unset)* | Your personal API token (`vlt_…`), sent as `Authorization: Bearer <token>`. **Required** — every route is account-scoped. Revoke it any time in the dashboard. |

> The older `LOCALRAG_API_URL` / `LOCALRAG_API_KEY` names are still accepted as fallbacks, but the `x-api-key` scheme they used no longer exists — set `VAULTLY_MCP_TOKEN` to a real token.

## Connecting to AI Clients

### 1. Cursor IDE
To allow Cursor's AI to search your documents while you code:
1. Open Cursor Settings > **Features** > **MCP Servers**.
2. Click **+ Add new MCP server**.
3. Configuration:
   - **Name**: `LocalRAG`
   - **Type**: `command`
   - **Command**: `node "f:\Projects\VS Code\LocalRAG\mcp\index.js"`
4. Click Save. You should see a green dot indicating it's connected!

### 2. Claude Desktop
To connect the official Claude Desktop app:
1. Open your Claude configuration file (usually located at `%APPDATA%\Claude\claude_desktop_config.json` on Windows).
2. Add the server configuration:
   ```json
   {
     "mcpServers": {
       "vaultly": {
         "command": "node",
         "args": [
           "/absolute/path/to/mcp/index.js"
         ],
         "env": {
           "VAULTLY_API_URL": "https://your-vaultly-host",
           "VAULTLY_MCP_TOKEN": "vlt_your_token_here"
         }
       }
     }
   }
   ```
3. Restart Claude Desktop. You will now see a "hammer" icon next to the chat bar indicating tools are available.

### 3. AnythingLLM
AnythingLLM natively supports MCP for empowering its agents with new skills!
1. Open AnythingLLM and navigate to **Agent Skills** in the settings.
2. Locate the **MCP Servers** section.
3. Add a new server configuration:
   - **Name**: `localrag`
   - **Command**: `node`
   - **Args**: `f:\Projects\VS Code\LocalRAG\mcp\index.js`
4. Save and start the MCP server in the UI. When you chat with an AnythingLLM `@agent`, it will now be able to search your LocalRAG system!

### 4. Windsurf
1. Open Windsurf Settings > **MCP**.
2. Click **Add Server**.
3. Configuration:
   - **Name**: `LocalRAG`
   - **Command**: `node`
   - **Arguments**: `f:\Projects\VS Code\LocalRAG\mcp\index.js`

## Usage
Once connected, simply ask your AI agent a question about your files!
For example:
> *"Can you search my local knowledge base for the latest architectural decisions?"*

The AI will automatically invoke the `query_localrag` tool, retrieve the answer from your LocalRAG backend, and synthesize a response for you.

# LocalRAG MCP Server

This is a Model Context Protocol (MCP) server that exposes your LocalRAG knowledge base to other AI agents and IDEs.

## How it works
This server exposes exactly one tool: `query_localrag`. 
When an AI agent (like Claude Desktop or Cursor) decides it needs to search your files, it will call this tool. The tool makes an HTTP request to your running LocalRAG docker backend (`http://localhost:8000/query`) and formats the AI-generated answer and file citations back into text for the agent to read.

## Prerequisites
1. Ensure your LocalRAG docker containers are running (`docker-compose up -d`).
2. Ensure you have Node.js installed on your host machine.
3. Install dependencies in this directory:
   ```bash
   cd "f:\Projects\VS Code\LocalRAG\mcp"
   npm install
   ```

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
       "localrag": {
         "command": "node",
         "args": [
           "f:\\Projects\\VS Code\\LocalRAG\\mcp\\index.js"
         ]
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

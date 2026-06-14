import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import axios from "axios";

// Default to the docker-compose backend endpoint if not specified
const API_URL = process.env.LOCALRAG_API_URL || "http://127.0.0.1:8000";

const server = new Server(
  {
    name: "localrag-mcp",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// 1. List our available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "query_localrag",
        description: "Searches the LocalRAG knowledge base and returns an AI-synthesized answer with source citations. Use this whenever the user asks about local documents, internal knowledge, or specific context from their files.",
        inputSchema: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "The search query to ask the local knowledge base.",
            },
            top_k: {
              type: "number",
              description: "Number of initial document chunks to retrieve before reranking (default: 10).",
            },
            rerank_top_k: {
              type: "number",
              description: "Number of highly relevant chunks to use for the final answer (default: 5).",
            },
          },
          required: ["query"],
        },
      },
    ],
  };
});

// 2. Handle tool execution
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === "query_localrag") {
    try {
      if (!request.params.arguments || !request.params.arguments.query) {
        throw new Error("Missing required argument 'query'. You must provide a search query.");
      }
      const { query, top_k = 10, rerank_top_k = 5 } = request.params.arguments;
      
      const response = await axios.post(`${API_URL}/query`, {
        query,
        top_k,
        rerank_top_k
      });

      const data = response.data;
      let outputText = `## LocalRAG Answer\n${data.answer}\n\n## Sources\n`;
      
      if (data.sources && data.sources.length > 0) {
        data.sources.forEach((source, index) => {
          const filename = source.file_name || 'Unknown File';
          const category = source.category || 'none';
          const score = source.score ? (source.score * 100).toFixed(1) : 'N/A';
          outputText += `${index + 1}. **${filename}** (Category: ${category}, Score: ${score}%)\n`;
          outputText += `   > "${source.content.substring(0, 150)}..."\n`;
        });
      } else {
        outputText += "No relevant sources found in the knowledge base.";
      }

      return {
        content: [
          {
            type: "text",
            text: outputText,
          },
        ],
      };
    } catch (error) {
      return {
        content: [
          {
            type: "text",
            text: `Tool Execution Failed.
Error type: ${error.name}
Error message: ${error.message}`,
          },
        ],
        isError: true,
      };
    }
  }

  throw new Error("Tool not found");
});

// 3. Start the server
async function run() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("LocalRAG MCP Server running on stdio");
}

run().catch(console.error);

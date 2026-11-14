# Root Dockerfile for MCP directories that build from the repository root (e.g. glama.ai). It packages only
# packages/mcp-server: the zero-dependency stdio MCP server (no npm install step, nothing else from the repo).
# The same server is also reachable with zero install over Streamable HTTP: https://pacta-x402.pacta.workers.dev/mcp
FROM node:22-alpine

WORKDIR /app

COPY packages/mcp-server/package.json packages/mcp-server/server.json packages/mcp-server/index.d.ts packages/mcp-server/README.md packages/mcp-server/SKILL.md ./
COPY packages/mcp-server/bin ./bin
COPY packages/mcp-server/src ./src

# Gateway tools on by default: the live gateway is free during the launch (no key, no wallet). The server holds no
# keys and never pays: with metering on, a gateway tool only returns the x402 challenge. Override with -e PACTA_X402_URL=.
ENV PACTA_X402_URL=https://pacta-x402.pacta.workers.dev

# stdio MCP server: reads JSON-RPC on stdin, writes on stdout, never opens a socket.
ENTRYPOINT ["node", "/app/bin/pacta-mcp.mjs"]

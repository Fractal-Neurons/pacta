FROM node:22-alpine

WORKDIR /app

COPY package.json server.json index.d.ts README.md SKILL.md ./
COPY bin ./bin
COPY src ./src

# Gateway tools on by default: the live gateway is free during the launch (no key, no wallet). The server holds no
# keys and never pays: with metering on, a gateway tool only returns the x402 challenge. Override with -e PACTA_X402_URL=.
ENV PACTA_X402_URL=https://api.pacta.wtf

# stdio MCP server: reads JSON-RPC on stdin, writes on stdout, never opens a socket. CMD (not ENTRYPOINT): MCP directory
# harnesses such as Glama's mcp-proxy replace the entrypoint and pass CMD as the child command; runs as the unprivileged node user.
USER node
CMD ["node", "/app/bin/pacta-mcp.mjs"]

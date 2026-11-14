FROM node:22-alpine

WORKDIR /app

COPY package.json server.json index.d.ts README.md SKILL.md ./
COPY bin ./bin
COPY src ./src

ENTRYPOINT ["node", "/app/bin/pacta-mcp.mjs"]

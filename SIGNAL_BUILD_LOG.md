# SIGNAL — Build Log
# Every file action recorded. Original user files outside E:\gitprac\n8n\signal are NEVER modified.

## 2026-08-21 Build Session

| Time (UTC) | Action | Path | Reason |
|---|---|---|---|
| build-start | READ | E:\gitprac\n8n\nexus-ai-war-room\secrets.txt | Obtain Groq/OpenRouter dev credentials (user-authorized) |
| build-start | STOP+RM | docker container zealous_chandrasekhar | Stray ephemeral n8n container (user-approved) |
| build-start | CREATED | E:\gitprac\n8n\signal\ | Project root |
| build-start | CREATED | .env.example | Variable names only, no secrets |
| build-start | CREATED | .env | Local secrets (gitignored), parsed from secrets.txt programmatically |
| build-start | CREATED | .gitignore | Protect secrets/env/artifacts |
| build-start | CREATED | docker-compose.yml | pgvector/pg16 + n8n only |
| build-start | CREATED | db/init/01-schema.sql | 14-table memory schema + pgvector |

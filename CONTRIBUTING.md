# Contributing

1. Create a feature branch from `main`.
2. Keep agent contracts narrow and deterministic tools separate from LLM narrative.
3. Add or update unit tests for every behavioral change.
4. Run `python -m unittest discover -s tests -v` from `backend/`.
5. Run `npm ci && npm run build` from `frontend/`.
6. Never commit `.env`, API keys, uploads, SQLite databases, artifacts, node_modules or build output.
7. Use conventional commits: `feat:`, `fix:`, `test:`, `docs:`, `refactor:`.

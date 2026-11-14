# RAG module

Retrieval-augmented generation module. This directory is a placeholder reserved for the
RAG owner, who decides its internal structure, dependencies and tests.

## Boundaries

- The module is a separate Python module with its own dependencies.
- It does not import code from `backend/app/`, and the backend does not import its
  internals.
- The shared data contracts are available as language-neutral files in
  [schemas/](../schemas/).
- The interface between the backend and this module is not defined yet. It is agreed
  with the RAG owner and then documented in
  [docs/api-contracts.md](../docs/api-contracts.md).

Shared conventions are in [AGENTS.md](../AGENTS.md).

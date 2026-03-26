---
name: docsearch
description: Semantic search over a local document archive (PDFs, Word, PowerPoint, Excel, Markdown). Uses ChromaDB + any OpenAI-compatible embeddings endpoint.
user-invocable: true
argument-hint: "[search query or task]"
---

# docsearch

Semantic search over a local directory of documents. Indexes into ChromaDB using any OpenAI-compatible embeddings endpoint (LM Studio, Ollama, OpenAI, etc.) and supports incremental re-sync via content hashing.

Supported formats: `.docx`, `.pptx`, `.pdf`, `.xlsx`, `.xlsm`, `.md`, `.txt`, `.csv`

## Companion documents

| Topic | File |
|---|---|
| Embedding backend options (LM Studio, Ollama, OpenAI, remote) | [embeddings.md](embeddings.md) |
| Troubleshooting install issues, venv setup, platform quirks | [setup.md](setup.md) |

## Configuration

All configuration is via environment variables — no config files to edit.

| Variable | Default | Purpose |
|---|---|---|
| `DOCSEARCH_DIR` | *(required)* | Root directory to index and search |
| `DOCSEARCH_DB` | `~/.docsearch/chroma_db` | ChromaDB storage path |
| `DOCSEARCH_COLLECTION` | *(derived from dir name)* | Override the collection name |
| `DOCSEARCH_EMBED_URL` | `http://localhost:1234/v1/embeddings` | Embeddings endpoint |
| `DOCSEARCH_EMBED_MODEL` | `text-embedding-nomic-embed-text-v1.5` | Model name |
| `DOCSEARCH_EMBED_KEY` | `lmstudio` | API key |
| `DOCSEARCH_EMBED_DIM` | `768` | Embedding dimensions |
| `DOCSEARCH_PYTHON` | *(python3 on PATH)* | Override Python interpreter |

Set these in your shell profile (`.zshrc`, `.bashrc`) or pass them inline.

## Commands

### Search
```bash
docsearch search "QUERY" [--top N] [--filter KEY=VALUE ...]
```

**Filters** use path-depth metadata extracted at index time:
- `--filter depth_1=customers` — top-level subdirectory
- `--filter depth_2=acme_corp` — second-level subdirectory
- `--filter extension=.pdf` — file type

**Output:** JSON when piped (for agent use), human-readable when run in a terminal.

### Index
```bash
docsearch index [--dir PATH] [--force]
```
Incremental by default — only processes new or changed files. `--force` rebuilds from scratch.

### Show index stats
```bash
docsearch info
```

### Check configuration
```bash
docsearch config
```

## Running as an agent

When calling docsearch from a Bash tool, the output is JSON:

```json
[
  {
    "rank": 1,
    "score": 0.87,
    "file": "/path/to/document.pdf",
    "filename": "document.pdf",
    "relative_path": "customers/acme/proposal.pdf",
    "type": ".pdf",
    "depth_1": "customers",
    "depth_2": "acme",
    "preview": "..."
  }
]
```

After finding a document:
- `.md`, `.txt`, `.csv` — read directly with the Read tool
- `.docx`, `.pptx`, `.pdf`, `.xlsx` — show the path to the user or open with `open "FILE_PATH"`

## Installation

**1. Python packages**
```bash
pip install chromadb requests python-docx python-pptx pypdfium2 openpyxl
```
Requires Python 3.10+. Install into a venv if preferred.

**2. Embeddings server** — any OpenAI-compatible endpoint must be running when you index or search.

| Backend | Default URL | Quick start |
|---------|-------------|-------------|
| LM Studio | `http://localhost:1234/v1/embeddings` | Load a nomic-embed-text model in the app |
| Ollama | `http://localhost:11434/v1/embeddings` | `ollama pull nomic-embed-text` |
| OpenAI | `https://api.openai.com/v1/embeddings` | Set `DOCSEARCH_EMBED_KEY=sk-...` and `DOCSEARCH_EMBED_MODEL=text-embedding-3-small` |

**3. Make the script accessible** — pick one approach:
```bash
# Symlink onto PATH
ln -s /path/to/mad-skills/skills/docsearch/scripts/docsearch.sh ~/.local/bin/docsearch

# Or call directly
python3 /path/to/mad-skills/skills/docsearch/scripts/docsearch.py search "query"
```

**4. Set required env var and index**
```bash
export DOCSEARCH_DIR="$HOME/Documents/my-docs"
docsearch index   # walks DOCSEARCH_DIR, builds ChromaDB index
docsearch info    # verify
```

See [setup.md](setup.md) for venv setup, troubleshooting, and platform-specific notes. See [embeddings.md](embeddings.md) for full backend configuration options.

## Notes

- The embeddings server must be running when you index or search
- iCloud-evicted files (`.icloud` placeholders) are automatically skipped
- Re-indexing is safe to run at any time — unchanged files are skipped
- Each indexed directory gets its own ChromaDB collection (isolated namespaces)

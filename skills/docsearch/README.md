# docsearch

Semantic search over a local document archive using ChromaDB and any OpenAI-compatible embeddings endpoint (LM Studio, Ollama, OpenAI, etc.).

Supported formats: `.docx`, `.pptx`, `.pdf`, `.xlsx`, `.xlsm`, `.md`, `.txt`, `.csv`

## Quick start

```bash
# Install Python dependencies
pip install chromadb requests python-docx python-pptx pypdfium2 openpyxl

# Point at your documents and index
export DOCSEARCH_DIR="$HOME/Documents/my-docs"
python3 scripts/docsearch.py index

# Search
python3 scripts/docsearch.py search "budget proposal Q3"
```

Requires an embeddings server running locally. Defaults to LM Studio at `http://localhost:1234/v1/embeddings` with a nomic-embed-text model loaded.

## Configuration

All config via environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `DOCSEARCH_DIR` | *(required)* | Root directory to index and search |
| `DOCSEARCH_DB` | `~/.docsearch/chroma_db` | ChromaDB storage path |
| `DOCSEARCH_EMBED_URL` | `http://localhost:1234/v1/embeddings` | Embeddings endpoint |
| `DOCSEARCH_EMBED_MODEL` | `text-embedding-nomic-embed-text-v1.5` | Model name |
| `DOCSEARCH_EMBED_KEY` | `lmstudio` | API key |
| `DOCSEARCH_EMBED_DIM` | `768` | Embedding dimensions |

See [embeddings.md](embeddings.md) for LM Studio, Ollama, and OpenAI configuration. See [setup.md](setup.md) for troubleshooting.

## Commands

```bash
docsearch index [--dir PATH] [--force]   # build or update the index
docsearch search "QUERY" [--top N] [--filter KEY=VALUE ...]
docsearch info                           # index statistics
docsearch config                         # show active configuration
```

## Using as a Claude Code skill

Install via the plugin manager, then invoke as `/mad-skills:docsearch` in Claude Code. Claude will use the Bash tool to run searches and return structured JSON results.

Filter results by directory structure:
```bash
docsearch search "quarterly forecast" --filter depth_1=finance --filter extension=.xlsx
```

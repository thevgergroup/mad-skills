# docsearch — Troubleshooting & Platform Notes

## Virtual environment setup

If you want an isolated install:

```bash
python3 -m venv ~/.docsearch/venv
~/.docsearch/venv/bin/pip install chromadb requests python-docx python-pptx pypdfium2 openpyxl
export DOCSEARCH_PYTHON="$HOME/.docsearch/venv/bin/python3"
```

`DOCSEARCH_PYTHON` overrides the Python interpreter used by `docsearch.sh`. If unset, the script uses the active venv (`VIRTUAL_ENV`) or falls back to `python3` on PATH.

## Common errors

**`ModuleNotFoundError: No module named 'chromadb'`**
The wrong Python is being used. Set `DOCSEARCH_PYTHON` explicitly or activate the correct venv before running.

**`Connection refused` / `requests.exceptions.ConnectionError`**
The embeddings server isn't running. Start LM Studio/Ollama or check `DOCSEARCH_EMBED_URL`.

**`No index found. Run 'docsearch index' first.`**
Either `DOCSEARCH_DIR` isn't set, or the collection name doesn't match what was indexed. Run `docsearch config` to confirm the active collection name.

**`docsearch: command not found`**
The script isn't on PATH. Symlink it or call via `python3 .../docsearch.py` directly.

## pypdfium2 on Linux (ARM)

`pypdfium2` ships prebuilt wheels for most platforms. On ARM Linux (Raspberry Pi, AWS Graviton), install with:
```bash
pip install pypdfium2 --no-binary pypdfium2
```
Requires `gcc` and `libpdfium` dev headers.

## iCloud files

Files not downloaded locally appear as `.icloud` placeholders and are automatically skipped during indexing. To download everything first on macOS:
```bash
brctl download "$DOCSEARCH_DIR"
```

## Rebuilding after switching embedding models

Embeddings from different models are not compatible. After changing `DOCSEARCH_EMBED_MODEL` or `DOCSEARCH_EMBED_URL` to a different backend, force a full rebuild:
```bash
docsearch index --force
```

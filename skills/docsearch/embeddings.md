# docsearch — Embedding Backend Options

docsearch works with any OpenAI-compatible embeddings endpoint. Set `DOCSEARCH_EMBED_URL`, `DOCSEARCH_EMBED_MODEL`, and `DOCSEARCH_EMBED_DIM` to match your backend.

## LM Studio (default)

```bash
export DOCSEARCH_EMBED_URL="http://localhost:1234/v1/embeddings"
export DOCSEARCH_EMBED_MODEL="text-embedding-nomic-embed-text-v1.5"
export DOCSEARCH_EMBED_KEY="lmstudio"
export DOCSEARCH_EMBED_DIM="768"
```

Load the **nomic-embed-text-v1.5** model in LM Studio before indexing/searching.

## Ollama

```bash
export DOCSEARCH_EMBED_URL="http://localhost:11434/v1/embeddings"
export DOCSEARCH_EMBED_MODEL="nomic-embed-text"
export DOCSEARCH_EMBED_KEY="ollama"
export DOCSEARCH_EMBED_DIM="768"
```

Pull the model first: `ollama pull nomic-embed-text`

## OpenAI

```bash
export DOCSEARCH_EMBED_URL="https://api.openai.com/v1/embeddings"
export DOCSEARCH_EMBED_MODEL="text-embedding-3-small"
export DOCSEARCH_EMBED_KEY="sk-..."
export DOCSEARCH_EMBED_DIM="1536"
```

Note: text-embedding-3-small outputs 1536 dimensions by default. text-embedding-3-large is 3072.

## Remote LM Studio (LAN)

```bash
export DOCSEARCH_EMBED_URL="http://192.168.x.x:1234/v1/embeddings"
```

Enable "Allow access from local network" in LM Studio settings.

## Changing models

If you switch embedding models after indexing, you must rebuild the index — embeddings from different models are not compatible:

```bash
docsearch index --force
```

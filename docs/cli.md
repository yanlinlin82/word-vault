# CLI Reference

## init-db

Initialize local SQLite schema.

```bash
uv run word-vault init-db
```

## add

Add or update a word via DeepSeek API.

```bash
uv run word-vault add apple --sentence "I ate an apple after lunch."
```

## show

Show one word entry.

```bash
uv run word-vault show apple
```

## list

List all words.

```bash
uv run word-vault list
```

## review

Show words for review and mark as reviewed.

```bash
uv run word-vault review --count 5
```

## delete

Delete one word.

```bash
uv run word-vault delete apple
```

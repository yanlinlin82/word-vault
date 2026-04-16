# CLI Reference

## init-db

Initialize local SQLite schema.

```bash
uv run word-vault init-db
```

## add

Add a word using cache-first behavior.

- If the word already exists locally, the command returns cached data behavior and does not call DeepSeek again.
- Use `--refresh` or `-r` to force a new DeepSeek call and update the stored fields.
- Use `--sentence` or `-s` to pass a context sentence.
- After printing the result, the command tries to play the stored IPA through `espeak-ng` or `espeak` when available.

```bash
uv run word-vault add apple --sentence "I ate an apple after lunch."
uv run word-vault add apple -s "I ate an apple after lunch."
uv run word-vault add apple --refresh
uv run word-vault add apple -r
```

## show

Show one word entry.

- By default this command is mute.
- Use `--speak` or `-s` to play audio after printing details.

```bash
uv run word-vault show apple
uv run word-vault show apple --speak
uv run word-vault show apple -s
```

## speak

Speak one stored word only (no details output).

```bash
uv run word-vault speak apple
```

## Audio configuration

- Set `WORD_VAULT_AUDIO_ENABLED=0` to disable playback.
- Set `WORD_VAULT_AUDIO_VOICE=en-us` to choose a specific eSpeak voice.

## list

List all words, or filter them with shell-style wildcards.

- `*` matches any sequence of characters.
- `?` matches a single character.
- Quote the pattern in your shell to avoid local shell expansion.

```bash
uv run word-vault list
uv run word-vault list 'app*'
uv run word-vault list 'b?nana'
```

## review

Interactive review session for listening, speaking, reading, and writing.

- Shows only IPA first and optionally plays pronunciation audio.
- Prompts you to spell the word.
- If spelling is wrong, allows one retry, then shows the correct spelling.
- Shows a four-choice meaning question using distractor meanings from other stored words when enough words exist in the database.
- Prints example sentences for the word and plays each sentence with `espeak-ng` or `espeak` when audio is enabled.
- Prompts you to read one example sentence aloud before continuing.
- Reveals meaning and usage details after the quiz steps.
- Asks for recall score from 0 to 5 and applies SM-2 spaced-repetition scheduling.
- Wrong spelling or a wrong meaning choice lowers the final quality score, so unfamiliar words are scheduled sooner.

```bash
uv run word-vault review --count 5
uv run word-vault review -c 5
```

## delete

Delete one word.

```bash
uv run word-vault delete apple
```

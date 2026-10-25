# Adding cards through the AnkiMCP add-on

The "Anki MCP Server" add-on (AnkiWeb 124672614) runs inside desktop Anki and serves MCP at `http://127.0.0.1:3141/`. It's registered with Claude Code as the `anki` server. Its tools appear as `mcp__anki__<tool>`.

## Before writing

- **Anki must be open with a profile loaded**, and no modal dialog (Add, Browse-edit, Preferences, a sync prompt) may be open. Every request runs on Anki's main thread with a 30-second timeout, so an open dialog makes calls hang and then fail. If a call times out, ask the user to close any Anki dialogs and retry once.
- **If the `mcp__anki__*` tools aren't available**, the server isn't connected in this session. Don't fall back to another write path. Give the user the approved cards in a copy-paste-ready form and tell them that restarting Claude Code with Anki open should connect it (registration command, if it's missing: `claude mcp add anki -s user --transport http http://127.0.0.1:3141/`).

## Write sequence

1. `model_names` — check the note type exists. Without a domain profile, use the built-in `Basic` (or `Cloze` for a fixed list). If a profile names a custom note type that's missing, create it with `create_model` using the definition in the profile. Creating a note type is a one-time change to the collection, so mention it in the approval message.
2. `list_decks` — if the target deck is missing, `create_deck` (at most two levels, e.g. `Parent::Child`).
3. `add_notes` with `deck_name`, `model_name`, and `notes: [{fields: {...}, tags: [...]}]`. One deck and one note type per call; max 100 notes. The duplicate check compares only the first field, and returns per-note status — report any `skipped` duplicates rather than retrying with `allow_duplicate`.
4. Report the created note IDs to the user. Offer `sync` (it's an async job: call with no arguments to start, then poll with the returned `job_id`). If sync reports a full-sync conflict, stop and ask the user which direction to resolve — never pick one yourself, it can overwrite their collection.

## Other useful tools

- `find_notes(query)` with Anki search syntax: `deck:"<deck>" "<term>"`, `tag:<tag>`, `tag:leech`, `prop:lapses>=4`. Pair with `notes_info` to read fields.
- `update_note_fields(id, fields)` to apply an approved rewrite of an existing card in place (keeps its review history — prefer this over delete + add).
- A field with an inline SVG chart: write and update it only through `add_notes` and `update_note_fields`, never by hand in Anki's editor, which can rewrite the SVG. Tell the user the same when you add one.
- `tag_add(note_ids, "space separated tags")` — tag tools take a space-separated string, unlike `add_notes`, which takes arrays.

## Never without explicit instruction

- `delete_notes` — even with `confirmDeletion`. Suggest suspending instead (`card_suspend`), which is reversible.
- Changing fields on an existing note type (`model_field_add`, `model_field_rename`, …) — forces a one-way full sync.
- `card_forget`, `set_fsrs_params`, `optimize_fsrs_params` — scheduling changes the user didn't ask for.

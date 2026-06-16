# Demo Recording — Talk Track Section Format

## [START - END] SECTION NAME
> **ACTION: What to click/do**

"Narration text here."

> **ON SCREEN: What the viewer sees**

"More narration referencing specific numbers visible on screen."
```

**Include:**
1. **Opening** (~20s) — Context, who this is for, what they'll see
2. **Per-page sections** — Distribute remaining time
3. **Closing** (~30s) — Recap, next steps, call to action

**⚠️ STOP**: Get approval on talk track.

**UX note — don't duplicate the talk track in chat.** The agent should:
1. Present the page-by-page **outline** in chat (short, scannable).
2. Once the outline is approved, write the full talk track directly to `RECORDING_SCRIPT.md` (with PRE-RECORDING SETUP and RECORDING TIPS included — combines Steps 2 and 3).
3. **Ask the user how they want to review the script** via `ask_user_question`:

   > *"The full talk track has been written to `RECORDING_SCRIPT.md`. How would you like to review it?"*
   > - **Open it for me** — "Open the file in my editor so I can read through it."
   > - **Looks good, proceed** — "I trust the outline — let's move to audio generation."
   > - **I have edits** — "I want to suggest changes to the narration."

   If the user picks **"Open it for me"**, open the file (use the IDE's file open mechanism), then follow up with a second `ask_user_question`:

   > *"Take your time reviewing. How does it look?"*
   > - **Looks good, proceed** — "Happy with the talk track, let's generate audio."
   > - **I have edits** — "I want to change some parts of the narration."

   If the user picks **"I have edits"** (at either step), collect their feedback and make the changes. After editing, offer the same review options again (open / approve / more edits) until the user confirms.

Do NOT type the full talk track into the chat conversation — it wastes screen space and the user has to scroll. Write it to the file and let them read it there.


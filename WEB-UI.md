# Permission desk — localhost web UI

A browser interface for the same local `licenses.json` and private audit history
used by the Python menu manager. Python 3.10+ is required; no pip packages, external
fonts, account, API key, or internet connection is needed to run the UI.

## Start on Windows

1. Keep `web_manager.py`, `license_manager.py`, and the `web/` folder together.
2. In your **public registry's local folder**, double-click `START-WEB.cmd`.
3. Your browser opens the private local session. Keep the terminal open while using it.
4. Use the dashboard, forms, and previews. Saves change the local JSON; publish it
   to GitHub yourself when ready.
5. Stop the server with Ctrl+C in its terminal when finished. Closing the browser
   does not stop the server. Relaunching creates a fresh session token.

The private repository's launcher asks for the full path to your canonical public
working copy so it does not silently treat the private mirror as a separate registry.
Opening a dashboard does not renew, revoke, or rewrite any permission.

Command-line equivalent:

```text
python web_manager.py "C:\Repos\game-framework-roblox-licenses\licenses.json"
```

Optional fixed mirror destination:

```text
python web_manager.py "C:\Repos\game-framework-roblox-licenses\licenses.json" --mirror "C:\Repos\game-framework-roblox\licenses.json"
```

Use `--port 0` to choose an available port if the default 8765 is occupied, and
`--no-browser` to print the launch address without opening it automatically.
The complete launch address includes a per-session token after `#`; use that address
when opening a new browser session. The fragment is cleared from the address bar
after the UI stores it in that tab's session storage. Do not share it.

`--state-dir` optionally selects a private state directory outside the registry folder.
Normally omit it to share the CLI's default history for the same canonical file path.
Changing registry paths or private state paths changes which local history is available.

## Dashboard and record forms

- Search by game name, license ID, Universe ID, or group ID.
- Filter expired, expiring within 30 days, not-started, archived, ending-recorded,
  or perpetual records. Date descriptions use the recorded UTC dates, not a legal finding.
- Open **Manage** to inspect every public field and choose an operation.
- Add a game, document an amendment, extend an unexpired fixed term, record a completed
  ending, or give permission again with a new grant ID.
- Select rows to archive, unarchive, or remove several public rows in one reviewed save.
- View the last 100 private audit events, open their complete before/after records,
  or recover a removed row as archived. All history remains in private local storage.

Forms collect identity and scope references separately from private evidence notes.
Actual acceptance requires actual evidence; no acceptance is inferred or invented.
The UI displays the public JSON diff and private audit details before **Save locally**.
**Back to form**, the close button, or Escape discards that unsaved preview.
Previews expire after ten minutes and can be committed only once.

Dates and date/time fields are explicitly **UTC**, even though your browser provides
a native date picker. A fixed expiry is the ending instant, not the end of that calendar
day. A perpetual term uses `expiresAt: null`; it does not by itself mean irrevocable.

The supplied records retain their original dates. For example, LIC-003 has a recorded
expiry of September 15, 2026, and appears past expiry after that timestamp. Nothing
is automatically extended, revoked, archived, or disabled as time passes.

## Permission actions and listing actions

| Action | Effect recorded by the UI |
| --- | --- |
| Extend expiry | Later expiry for an unexpired fixed-term grant, supported by an actual extension reference. |
| Edit / amend | An effective amendment or factual correction; requires evidence. Does not itself establish new rights. |
| Record ending | Completed owner-recorded revocation/termination, effective time, public reference, and private authority/notice evidence. |
| Give permission again | A separate new grant ID with its own term. The old record remains. |
| Archive / unarchive | Administrative listing only. |
| Remove row | Removes the public row, with private recovery history; does not revoke permission. |
| Recover row | Restores the recorded row as archived, including any previous ending; does not grant permission again. |
| Correct mistaken ending | Records evidence that the earlier ending assertion was factually wrong. |

An unknown or prohibited at-will revocation rule blocks that revocation route.
The other-ground route requires an identified authority and evidence; the program
cannot verify their legal validity. The actual grant and applicable law remain controlling.
The UI does not send notices, sign agreements, enforce rights inside Roblox, or submit claims.

## Files, exports, and mirrors

**Files & tools** shows the canonical path, private history location, and configured
mirror status. Download JSON to obtain the actual saved registry. CSV is a viewing
summary, not an import format or a grant document; dangerous spreadsheet-formula
prefixes are escaped in exported cells.

When a mirror was configured at startup, **Preview mirror export** shows the diff
before copying. An existing valid mirror is backed up privately first. A changed
source or changed mirror blocks the copy. JSON downloads reflect the saved file,
not an unsaved form. Publishing to GitHub is a separate step.

Use **Initialize / save format** for an empty registry or to save a supported older
format as schema 1.1. It makes no change when the saved representation already matches.

## Saves and recovery

The web and command-line managers use the same validation, atomic replacement,
pre-save backups, write lock, and pending-transaction recovery. They record separate
actions in the same private journal when using the same canonical path and state directory.
The CLI can recover rows removed in the web UI and vice versa.

Every web form captures a file revision. A stale form, stale preview, changed mirror,
or competing browser tab is rejected instead of overwriting newer bytes. Refresh and
review again. Validation is repeated at commit time for rules such as an expiry that
may have passed while the preview was open. A failed save can require a fresh preview.

Retain the private history directory and back it up. It normally lives under
`%LOCALAPPDATA%\RanuLicenseManager\<registry-path-hash>`, outside the public repository.
Private evidence is not encrypted or independently authenticated by this app.
For an interrupted process or stale `manager.lock`, follow LICENSE-MANAGER.md; do not
delete audit history or pending recovery records merely to clear an error.

The UI does not poll for external changes or monitor expiry in the background. Use
Refresh to update the dashboard; safety checks re-read disk on preview and save.
Close a stale preview before refreshing and opening a fresh form.

## Local access and limits

The server binds only `127.0.0.1`. It checks the Host and Origin and requires an
unpredictable launch token for private API access and writes. There are no cross-origin
permissions, arbitrary file-serving routes, or user-supplied server paths in forms.
Page values are rendered as text, and a restrictive content policy blocks framing
and external scripts. This is a local owner tool, not a public hosting service.

Do not expose it through port forwarding or a tunnel. Other software running under
your account may still read local files; the tool does not protect against a compromised
computer. Public repository uploads should include only the application source and
public registry, never private audit directories or launch URLs.

The UI and CLI support schema 1.1. The Roblox header plugin is a separate Studio tool;
the website does not access Studio or change script comments.

## Checks

From this repository folder:

```text
python -m unittest discover -s tests -v
python validate_registry.py licenses.json
```

The browser workflow was also exercised on a separate local test registry, including
adding a game, reviewing the diff, saving, and displaying the saved record. Test data
and private audit entries are not included in the repository package.

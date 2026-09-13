# RanuRbx License Manager

A local Python menu application for maintaining `licenses.json`. Uses Python 3.10+
and its standard library; no packages, login, network connection, or API key required.

## Start

1. Extract this package into a local folder.
2. Double-click `START.cmd` on Windows, or run `python license_manager.py` in a terminal.
3. Enter the path to your public repository's local `licenses.json`, or to a downloaded
   working copy. The default is `licenses.json` beside the script.
4. Choose an action from the numbered menu. Enter `/cancel` in a form to abandon it.
5. Read the public JSON diff and private audit details. Type `SAVE` only when correct.
6. Upload or commit the saved JSON to your public repository yourself. Use option 15
   to export an identical copy into the private repository. This program does not push
   to GitHub or communicate with game operators.

For an explicit path:

```text
python license_manager.py "C:\My Repositories\game-framework-roblox-licenses\licenses.json"
```

If the file does not exist, the program opens an empty registry in memory. Use option
3 to add a game or option 17 to save an empty registry. It does not silently populate
new repositories with sample permissions. Keep using the same local path so its private
history remains associated with it.

If Windows does not recognize `python`, try `py -3 license_manager.py`, or install
Python with its command-line launcher. The supplied launcher tries both commands.

## Common actions

| Menu | Action | What it does |
| --- | --- | --- |
| 1 / 2 | Find / inspect | Search names and identifiers; inspect every field. |
| 3 | Add permission | Record an actually issued owner permission or actual agreement, with verified IDs and document references. |
| 4 | Extend expiry | Require a later expiry for an unexpired fixed-term grant and an extension reference. |
| 5 | Record ending | Record a completed revocation or termination, its effective time, authority, and notice evidence; also archive the listing. |
| 6 | Give permission again | Create a new grant ID for the same game, with fresh dates and terms. Preserve the old record. |
| 7 | Archive / unarchive | Change administrative listing only. Does not revoke or restore permission. |
| 8 | Remove row | Delete a public record, retaining its contents in private history. Does not revoke permission. |
| 9 | Recover removed row | Recover the deleted record as archived, including any recorded ending. Does not give permission again. |
| 10 | Correct metadata | Correct name, IDs, or grantor based on evidence. A change of actual operator or experience requires review of the grant, not a disguised typo correction. |
| 11 | Amend / correct terms | Record an effective amendment or factual correction to scope, term, basis, revocation terms, or acceptance metadata. |
| 12 | Correct mistaken ending | Undo a factually incorrect ending assertion with evidence; not a shortcut for issuing permission again. |
| 13 | History | Inspect private action notes and locate the complete before/after records. |
| 14 | Validate | Check the file currently loaded from disk without changing it. Reload first if another editor changed it. |
| 15 | Export mirror | Copy the saved public JSON to a specified private `licenses.json`, backing up an existing valid destination. |
| 16 | Reload | Reload external edits without saving a form. |
| 17 | Initialize / save format | Save an empty registry or the schema 1.1 representation of an existing file. |

Every form is collected in memory first. Cancelling before SAVE leaves the registry
unchanged. Read-only validation is also available without creating private state:

```text
python license_manager.py --validate "C:\path\licenses.json"
```

## Owner-controlled permission

To record a new grant with no scheduled expiry but with discretionary revocation
reserved in its actual terms, choose:

- Basis: `owner-issued-permission`.
- Duration: `perpetual` (sets expiry to JSON `null`).
- At-will revocation: `yes`.
- Grant, scope, and termination references: actual document references.

The grant itself must establish the recipient, covered materials, permitted uses,
and the revocation procedure. A registry field does not establish those rights.
Prepare the actual terms using the owner-controlled permission worksheet
in the owner's private repository or other appropriate drafting process.
This worksheet is not issued permission and is not proof of a legally enforceable contract.

`yes` does not mean deletion instantly ends permission. Follow the actual notice and
termination procedure first, then record it with option 5. A `no` or `unknown` value
blocks the at-will route. The other-ground route requires an identified independent
termination ground and evidence. The program cannot verify whether that ground is valid.
Do not switch a value to `yes` merely to bypass the check.

To give permission back after a real ending or expired term, use option 6. Set a new
start date and grant reference. The previous grant stays in the record; a new permission
does not silently cover a gap. If there never was a valid ending and its recorded status
was a factual error, option 12 records that correction separately.

Perpetual permission with `revocableAtWill: false` is the separate arrangement for
no scheduled expiry and no discretionary revocation. Other express termination terms
and mandatory law may still apply. The [U.S. Copyright Office](https://www.copyright.gov/recordation/termination.html)
describes statutory termination rights that may affect some grants. Applicable jurisdiction
and facts determine enforceability; the manager does not promise unlimited legal control.

## Expiry and amendments

Date-only input means the **start of that date at 00:00 UTC**. Full timestamps use
`YYYY-MM-DDTHH:MM:SSZ`. The program displays the normalized timestamp before saving.
For permission through the whole UTC day of December 1, use December 2 at 00:00 UTC.

Option 4 preserves the original start and original grant reference. The private audit
stores the extension document/message reference and old/new expiry. Issue the extension
and retain the actual evidence first. Option 11 is for an effective amendment or a
factually wrong record, including a documented shortening or perpetual conversion.
It is not a way to retroactively rewrite an already granted right. New contractual
obligations may require actual agreement; do not invent acceptance or delivery.

## Registry format and public status fields

This repository uses schema **1.1**. The manager also accepts 1.0 and writes 1.1
on a confirmed save, retaining the original grant fields. Read-only operations
do not rewrite the file. See [REGISTRY-GUIDE.md](REGISTRY-GUIDE.md) and
[REGISTRY-MANAGER-NOTES.md](REGISTRY-MANAGER-NOTES.md) for all fields.

`permissionState` records a grant, revocation, or termination as an owner statement.
`statusEffectiveAt` and `statusReference` identify a recorded ending; both are null
for `grant-recorded`. Detailed authority and notice evidence stay in the private audit.
`registryStatus` remains administrative, and removal alone does not terminate permission.

`validate_registry.py` and `license_manager.py` are already included together.
The manager and validator are administration tools, not framework runtime scripts.

## Backups, history, and recovery

The startup screen prints the private storage path. On Windows it is normally:

```text
%LOCALAPPDATA%\RanuLicenseManager\<registry-path-hash>\
```

- `backups/`: exact registry bytes before each write.
- `events/`: one private JSON document per completed action, with full before/after
  records, UTC recording time, action, evidence notes, and file hashes.
- `pending.json`: an unfinished save, used for recovery; normally absent.
- `exports/`: copies of overwritten mirror files and their destination paths.
- `manager.lock`: prevents simultaneous manager writes to the same local registry path.

Back up this directory privately. It is normal local user storage, not encrypted or
tamper-proof. A hash helps compare bytes; it does not authenticate signatures or prove
when a legal event happened. Do not upload this directory to GitHub. If changing
computers or moving the registry path, retain its old history and backups; history
does not automatically follow the new path. Deleted IDs are reserved only by the
current registry and that path's retained history.

Writes stage a temporary file, flush it, and replace the destination. A pending journal
is written before replacement. On reopening, the manager finishes logging a completed
write or discards an uncommitted journal when the current bytes match the old file.
If neither version matches, it stops for manual inspection rather than overwriting data.

After a process crash, a lock file may remain. Close all instances using that registry,
then remove **only the `manager.lock` file printed in the error** and reopen. Keep
`pending.json`, backups, and events for recovery. Do not delete the whole state directory.

The manager detects an externally changed file before saving. Reload and re-enter
the operation if needed. Avoid editing the same file simultaneously in another app:
external editors do not honor this program's lock, so no cross-application race-free
guarantee is possible. Public and private repositories are exported separately, not
as a combined transaction; validate both after copying.

Backups restore file contents, not legal rights. Prefer a documented corrective action
or a new grant over manually replacing a file and losing the visible chronology.
The history is an administrative record and can be modified by whoever controls the
computer; it is not independent evidence verification.

## Boundaries

This manages local records. It does not sign or send grants, authenticate Roblox IDs
or agreements, enforce terms inside Roblox, monitor expiry, disable games, revoke
platform access, publish GitHub changes, or submit takedowns. No automated action occurs
when an expiry passes. Removing a row or recording an ending does not itself establish
infringement. Third-party rights, prior grants, and platform terms still matter.

The manager supports your listed workflow; it cannot encode every possible agreement
or jurisdiction. Keep complex scope and termination rules in actual referenced documents.

## Verification

Run the included regression tests in a terminal:

```text
python -m unittest discover -s tests -v
```

Tests use temporary registries and private-state folders; they do not modify your games.

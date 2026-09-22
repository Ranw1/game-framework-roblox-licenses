# Registry guide — version 1.1

This guide explains RanuRbx's record format. It is not an issued license or a
retroactive change to existing permissions. The registry summarizes grants;
the underlying grant or agreement and applicable law control discrepancies.

## 1. Choose the term and revocation rule separately

| Intended permission | `duration` | `expiresAt` | `revocableAtWill` |
| --- | --- | --- | --- |
| Ends on a specified date; revocation terms unknown | `fixed-term` | UTC timestamp | `null` |
| No scheduled end, but expressly revocable at will | `perpetual` | `null` | `true` |
| No scheduled end, expressly not revocable at will | `perpetual` | `null` | `false` |
| No scheduled end; revocation terms unknown | `perpetual` | `null` | `null` |

A fixed-term permission may also expressly allow or prohibit revocation at will.
Use a boolean only when the underlying terms support it. Unknown is not the same
as revocable or irrevocable. Never infer irrevocability just from no end date.

For permanent permission that survives removal from the registry, the actual
grant should state no scheduled expiry, no discretionary revocation, and survival
of registry removal. Then summarize it as `duration: "perpetual"`, `expiresAt: null`,
`revocableAtWill: false`, and `registryRemovalTerminatesPermission: false`.
These custom field names have no independent statutory effect.

An irrevocable-at-will grant can still contain express termination grounds.
For example, the actual terms might allow termination for a specified breach
after notice and an opportunity to cure. Such a provision must be deliberately
established; this guide does not add one. Mandatory law can also affect duration.
In the United States, certain author grants can be terminated under statutory
procedures despite their stated duration. See the [Copyright Office](https://www.copyright.gov/recordation/termination.html).

Enforceability of a promise not to revoke depends on jurisdiction and facts,
including consideration or reliance where relevant. A U.S. appellate software case
found a paid implied license irrevocable on its facts; it does not establish that
every free JSON declaration is irrevocable. See [Asset Marketing Systems v. Gagnon](https://cdn.ca9.uscourts.gov/datastore/opinions/2008/09/08/0755217.pdf).
Have permanent grants reviewed for the applicable jurisdiction before issuing them.

## 2. Field reference

The root is an object with `schemaVersion: "1.1"` and a `licenses` array.
Use JSON `null`, `true`, and `false`, not strings containing those words.

| Field | Type and meaning |
| --- | --- |
| `licenseId` | Unique, stable string such as `LIC-001`; a tracking reference, not proof of a contract. Do not reuse it for an unrelated grant. |
| `gameName` | Human-readable experience title; names can change. |
| `universeId` | Numeric ID stored as a string; identifies the experience, not an individual Place ID. Verify it before issuance. |
| `groupId` | Numeric string identifying the recorded Roblox group; does not establish its operator's legal identity. |
| `basis` | `owner-issued-permission` or `license-agreement`. The latter requires an actual agreement; a draft is insufficient. |
| `grantor` | Owner pseudonym or established grantor identification. Current records use `RanuRbx`. |
| `agreementId` | Separate agreement reference, or `null` if none is linked. Not a public signature or a claim that the agreement was signed. |
| `operatorAcceptanceRecorded` | Boolean; `false` means no acceptance is recorded, not rejection. `true` requires actual evidence; identify that evidence privately. |
| `startsAt` | Stated effective start, as `YYYY-MM-DDTHH:MM:SSZ`. It is not a delivery or signature timestamp. |
| `duration` | `fixed-term` or `perpetual`. Use the actual grant's term. |
| `expiresAt` | End timestamp for fixed-term records; `null` for perpetual records. |
| `revocableAtWill` | `true`, `false`, or `null` as explained above. It describes discretionary revocation, not every possible termination ground. |
| `registryRemovalTerminatesPermission` | Always `false` in this format: deletion alone is not a termination mechanism. This records registry policy and does not amend an earlier grant. |
| `registryStatus` | `listed` or `archived`; an administrative label only. |
| `permissionState` | `grant-recorded`, `revocation-recorded`, or `termination-recorded`; the owner's recorded assertion, not verified legal status. |
| `statusEffectiveAt` | Ending's stated effective UTC timestamp; `null` for `grant-recorded`. |
| `statusReference` | Non-sensitive reference to the recorded ending; `null` for `grant-recorded`. Evidence stays private. |
| `grantReference` | Stable non-sensitive reference to the actual permission text or evidence, or `null` if not recorded. A private document ID is sufficient; never expose a private document's access token. |
| `scopeReference` | Reference to the material and use specification, or `null` if not recorded. The registry does not fill in missing scope. |
| `terminationTermsReference` | Reference to the express revocation/termination provisions, or `null` if not recorded. Null does not mean there are no termination rights. |

The entries record the owner's stated start and end dates. Detailed scope,
delivery evidence, signatures, agreement IDs, and discretionary revocation rules
are not recorded for these permissions. A registry date does not prove that a
deadline was communicated or change the effect of an underlying informal grant.

## 3. Adding a new game

1. Verify your rights in the covered material and identify third-party exclusions.
2. Verify the Universe ID, group ID, actual operator, and who can act for that operator.
3. Decide the covered release/files/assets, permitted operations, allowed experience,
   duration, and any revocation or termination procedure. Record these in a durable grant.
4. Issue that grant to the intended recipient and retain the exact text and evidence
   of issuance. Do not call it an agreed contract if no agreement exists. Obligations
   such as fees or confidentiality may need a separate accepted agreement.
5. Assign the next unused `licenseId`, and add a summary matching the actual grant.
   Use `null` for missing references or unspecified revocation rules.
6. Use the manager's Add permission action to enter the record, inspect the preview,
   and save. It requires grant and scope references for newly entered permissions.
   Run `python validate_registry.py licenses.json`, then publish the saved JSON.
7. Save the relevant commit and give the operator a durable copy of the actual grant.
   Use the manager's Export mirror action to synchronize the private registry copy.

Adding an invented “signed agreement” to JSON is never a substitute for agreement.
An intentional owner-issued grant is different from an administrative summary:
keep its operative text separately identifiable. This package adopts a summary-only
registry so a routine metadata edit is not presented as a new grant.

## 4. Dates, expiry, and renewal

Times are UTC and the stated interval is start-inclusive, end-exclusive:
`startsAt <= time < expiresAt`. `2026-09-15T00:00:00Z` means the start of September
15 UTC, not the end of that day. Never use a far-future date as a substitute for perpetual.

For a perpetual entry, `expiresAt: null` means no scheduled expiry only when
`duration` is also `perpetual`. Missing or malformed data must not be interpreted
as an unlimited grant. The checker validates structure, not permission validity.

For renewal, first issue an effective extension or make the required agreement.
Then update the existing record if the same grant is amended; preserve the amendment
and previous terms in your evidence log. If there is a separate new grant, use a new
record ID and retain the old record. Do not silently backdate an extension to hide a gap.
Correcting an erroneous timestamp documents a correction; it does not establish that
a recipient previously received or accepted the corrected deadline.

## 5. Removing, archiving, and ending permission

| Action | Effect of that action alone |
| --- | --- |
| Delete a row or the repository | Removes accessible registry information; does not itself terminate rights. |
| Set `registryStatus: "archived"` | Changes record administration only; permission may continue. |
| Change `expiresAt` | Changes the summary; does not itself shorten or extend an underlying grant. |
| Change `revocableAtWill` | Changes the summary; does not itself establish a new revocation right. |
| Reach a valid fixed-term end | The underlying grant determines which rights end and which provisions survive. |
| Follow an effective termination provision | May end the rights covered by that provision; retain the basis and required notices. |

Prefer archiving to deleting: keep the record, its original grant, and its history.
After following an effective ending procedure, the manager can record
`revocation-recorded` or `termination-recorded`, its effective timestamp, and a
non-sensitive status reference. It also archives the listing. These fields describe
the owner's assertion, not an independent decision that permission legally ended.
Keep the authority, notice, and other evidence privately. A commit is not delivery
of a notice unless the effective terms specifically make that procedure sufficient.

The manager records completed endings, not scheduled future actions. An ending entered
manually with a future timestamp must not be treated as already effective. The stored
`startsAt` and `expiresAt` remain the grant's recorded term; ending metadata is separate.
`grant-recorded` does not mean currently authorized: a recorded grant may be expired,
not yet started, disputed, or subject to terms not resolved by this registry.

An irrevocable-at-will grant cannot simply be withdrawn because the owner changes
their mind. A genuinely revocable grant still requires the applicable procedure;
`true` does not mean “delete the row and DMCA immediately.” Earlier rights, platform
terms, and applicable law remain relevant.

## 6. Scope, versions, and changes of operator

Specify scripts/modules/assets, release or commit, permitted modification, production
publication, monetization, backups, and contractor access as appropriate. State whether
new versions, support, other universes, redistribution, transfer, or sublicensing are
included or excluded in the actual grant. A perpetual permission to use version 1.0.0
does not automatically define rights in future releases.

Group and Universe IDs are identifiers, not proof of contractual authority. A sale,
group-owner change, or experience transfer should be checked against the actual grant's
recipient and transfer provisions. Renaming a game usually needs a metadata correction;
do not assume that changing IDs is the same harmless correction.

## 7. Evidence, privacy, and enforcement

Keep original grant text, amendments, scope manifests, relevant source revisions,
issuance/delivery evidence, acceptance where actually obtained, and any termination
notices in private storage with backups. Git commit history is useful evidence of
repository changes, but neither a signature service nor conclusive proof of ownership,
receipt, consent, or an unalterable timestamp. A hash can identify a document's bytes;
it does not prove who signed it or when.

Public references should avoid legal names that need not be public, private addresses,
signatures, access credentials, correspondence, or confidential financial terms.
Using a public pseudonym does not remove identity requirements from private legal
agreements or formal enforcement procedures. Do not publish private evidence merely
to make a registry reference clickable.

A missing row or expired date is not itself a copyright infringement finding. Review
actual copying/use, your ownership, prior grants, third-party rights, platform terms,
and effective termination before making a claim. A contractual disagreement is not
automatically a copyright claim. The registry does not promise a DMCA takedown.

## 8. Consumers and availability

Consumers must read `schemaVersion`, handle nulls explicitly, and avoid equating
`listed` with authorized or `archived` with unauthorized. A network failure, invalid
JSON, repository deletion, or missing row means evidence is unavailable or incomplete,
not that permission has necessarily ended. This package provides documentation and
records; it adds no runtime license checking or game shutdown behavior.

## 9. Manager, validator, and local history

Use `START-WEB.cmd` for the browser dashboard; see [WEB-UI.md](WEB-UI.md).
The terminal interface remains available with `python license_manager.py` or `START.cmd`. Point it at the canonical public
registry's local file. [LICENSE-MANAGER.md](LICENSE-MANAGER.md) documents every menu
action, private storage, recovery, input rules, and export behavior.

The manager accepts schema 1.0 and 1.1 and writes 1.1 on a confirmed save. All records
and examples supplied here already use 1.1. Reading a file does not rewrite it.
Keep `validate_registry.py` and `license_manager.py` together: the validator imports
the manager's validation code. Neither script needs third-party Python packages.

Keep private state at the path printed by the manager, outside the public repository.
The private audit contains actual before/after snapshots, not just public metadata.
Do not upload it. `.gitignore` ignores an optional `.private/` folder but is not access
control, does not unpublish already tracked files, and cannot prevent every mistaken upload.

Renewal after an expired or ended permission uses a new grant ID in the manager.
Archiving, unarchiving, deleting, or recovering a row does not itself change permission.
A factual correction is recorded separately from a new grant.

## 10. Sources and limits

The legal sources above discuss U.S. law, not a selected governing law for these games.
This package does not choose a jurisdiction, create fees, invent acceptance, or
resolve the legal effect of earlier informal permissions. Have the actual grant
reviewed where permanence, termination, or disputed rights matter.

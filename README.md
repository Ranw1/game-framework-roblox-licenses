# Ranu's Framework — Permission and License Registry

Public records for Ranu's Framework. Source code and game assets are maintained
separately in a private repository. Registry format version: **1.1**.

## Ownership

Copyright (c) 2025-2026 RanuRbx. All rights reserved, subject to third-party rights.
RanuRbx is the developer pseudonym of the copyright owner.
See [LICENSE.txt](LICENSE.txt). Third-party materials retain their own notices and licenses.

## How permission works

Permission may come from an owner-issued permission or a separate license agreement.
The underlying grant or agreement and applicable law determine its scope and effect.
A registry entry is a summary, not proof of a signed contract, acceptance, or ownership
of a listed game. Public visibility or source access does not itself grant framework rights.

| Recorded term | Meaning |
| --- | --- |
| `duration: "fixed-term"` | A stated end timestamp is recorded. |
| `duration: "perpetual"` | No scheduled expiry; `expiresAt` must be `null`. |
| `revocableAtWill: true` | The underlying terms expressly allow discretionary revocation, following their procedure. |
| `revocableAtWill: false` | The underlying terms expressly prohibit discretionary revocation; other express termination grounds and mandatory law can still apply. |
| `revocableAtWill: null` | Discretionary revocation terms have not been established in this registry. |

Deleting or archiving a record does not itself terminate permission. A permanent
permission must actually be granted on appropriate terms; setting JSON fields does
not make an existing permission permanent. Changes to this repository do not by
themselves amend, renew, revoke, or replace underlying grants or earlier rights.

## Recorded permissions

The registry contains **fixed-term owner-issued permissions**. No separate agreement
or operator acceptance is recorded for these entries. Their discretionary revocation
terms and detailed scope are unspecified in this registry. Consult the underlying
permission records to establish the scope and effect of each grant.

`registryStatus` describes record administration, not legal authorization. An expired
record can remain listed; an archived record can describe permission that continues.
Absence, expiry, or a status change alone does not establish infringement or justify a DMCA notice.

`permissionState` distinguishes a recorded grant from an owner-recorded revocation
or termination. `statusEffectiveAt` and `statusReference` identify a recorded ending.
These are owner assertions, not independently verified legal determinations.

## Files and instructions

- [licenses.json](licenses.json): actual recorded permissions; the canonical published registry.
- [REGISTRY-GUIDE.md](REGISTRY-GUIDE.md): field definitions, permanent permission, dates, removal, renewals, and verification.
- [examples/README.md](examples/README.md): illustrative examples, including perpetual permission that survives removal.
- [examples/permission-records.json](examples/permission-records.json): examples only, not issued grants or real authorized games.
- [validate_registry.py](validate_registry.py): local structural checker; it does not determine legal validity.


- [license_manager.py](license_manager.py) / [START.cmd](START.cmd): interactive local registry manager.
- [LICENSE-MANAGER.md](LICENSE-MANAGER.md): setup, every menu action, backups, recovery, and mirror export.
- [REGISTRY-MANAGER-NOTES.md](REGISTRY-MANAGER-NOTES.md): recorded status fields and their interpretation.
- [tests/test_manager.py](tests/test_manager.py): regression tests using temporary data.

All timestamps use UTC. Read the guide before adding or changing a record.
Never publish private signatures, addresses, correspondence, or private source links here.

## Contact

- Email: [business.ranw@gmail.com](mailto:business.ranw@gmail.com)
- Roblox: [@RanuRbx](https://www.roblox.com/users/3267747943/profile) (3267747943)
- Discord: .ranu. (751118664471805974)

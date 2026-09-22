# Registry format and recorded actions

The registry supports schema version `1.1`. It retains the permission fields from
schema `1.0` and adds three fields to each record:

| Field | Meaning |
| --- | --- |
| `permissionState` | `grant-recorded`, `revocation-recorded`, or `termination-recorded`; describes the owner's record, not independently verified legal status. |
| `statusEffectiveAt` | Stated effective UTC timestamp of a recorded ending; null for `grant-recorded`. |
| `statusReference` | Public, non-sensitive reference identifying a recorded ending; null for `grant-recorded`. Detailed evidence is retained privately. |

`grant-recorded` does not guarantee that permission is currently effective: dates,
underlying terms, amendments, earlier rights, and applicable law still control.
Date-based expiry is determined from `duration`, `startsAt`, and `expiresAt`; the
manager does not automatically alter files when time passes.

`registryStatus` remains administrative: `listed` or `archived`. Deleting, recovering,
archiving, or unarchiving a record does not itself revoke or restore permission.
`registryRemovalTerminatesPermission` remains false.

Owner-issued permission may be fixed-term or perpetual and may reserve discretionary
revocation if the actual grant validly establishes it. `revocableAtWill: true` records
that express arrangement, not a power created by JSON. `false` records an express
prohibition on discretionary revocation; `null` means unspecified here. Other express
termination grounds and applicable law may still apply.

A new permission issued after expiry or termination receives a new grant ID. The old
record is retained when practical. A factual correction is recorded as a correction;
it must not be presented as a newly issued grant or fabricated evidence of acceptance.

The applicable grant or agreement and applicable law control discrepancies. Registry
changes and owner assertions alone do not establish infringement or entitlement to a
takedown. Public access does not itself grant use of the framework.

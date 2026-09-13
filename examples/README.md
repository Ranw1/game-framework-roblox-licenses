# Examples only — no grants issued

The records in [permission-records.json](permission-records.json) are format examples.
Their numeric IDs are placeholders, not verified experiences or authorized groups.
Do not merge these records into the real registry or treat them as issued permissions.

| Example | Demonstrates |
| --- | --- |
| EXAMPLE-001 | Fixed term with unspecified discretionary revocation rules. |
| EXAMPLE-002 | No scheduled expiry, with express discretionary revocation in a hypothetical grant. |
| EXAMPLE-003 | No scheduled expiry and no discretionary revocation in a hypothetical grant; registry removal does not end it. |
| EXAMPLE-004 | The same kind of enduring permission while its registry record is archived. |
| EXAMPLE-005 | An owner-recorded revocation, with effective time and a public reference. |
| EXAMPLE-006 | A separate grant for the same hypothetical universe after a gap; the old ending remains recorded. |

Before using a pattern, issue an actual grant defining materials, recipient, permitted
uses, and term. Replace example values with verified facts and references. Setting
`revocableAtWill: false` cannot by itself make a permission legally irrevocable.
Other express termination provisions and applicable law can still matter.
See [the guide](../REGISTRY-GUIDE.md).


Every example uses schema 1.1. A `grant-recorded` entry has null ending fields;
recorded endings have an effective timestamp and a non-sensitive status reference.
The fifth and sixth examples illustrate the distinction between recovering a row
and issuing new permission. They are fictional examples, not evidence of real events.

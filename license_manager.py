"""RanuRbx License Manager: local, interactive registry administration. Python 3.10+."""
from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

VERSION = '1.0.0'
SCHEMA = '1.1'
BASE_FIELDS = {
    'licenseId', 'gameName', 'universeId', 'groupId', 'basis', 'grantor',
    'agreementId', 'operatorAcceptanceRecorded', 'startsAt', 'expiresAt',
    'duration', 'revocableAtWill', 'registryRemovalTerminatesPermission',
    'registryStatus', 'grantReference', 'scopeReference', 'terminationTermsReference',
}
STATE_FIELDS = {'permissionState', 'statusEffectiveAt', 'statusReference'}
STATES = ('grant-recorded', 'revocation-recorded', 'termination-recorded')


class Cancelled(Exception):
    pass


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value):
        raise ValueError('Use YYYY-MM-DDTHH:MM:SSZ in UTC.')
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)


def entered_date(value):
    """A date alone means the START of that UTC date, never local end-of-day."""
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        value += 'T00:00:00Z'
    timestamp(value)
    return value


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError('Not a JSON value: ' + value)


def decode(raw):
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique_keys,
                      parse_constant=reject_constant)


def encode(data):
    return (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def validate(data):
    errors = []
    if not isinstance(data, dict) or data.get('schemaVersion') not in ('1.0', SCHEMA):
        return ['Expected schemaVersion 1.0 or 1.1.']
    if set(data) != {'schemaVersion', 'licenses'} or not isinstance(data['licenses'], list):
        return ['Root must contain only schemaVersion and a licenses array.']
    ids = set()
    for i, row in enumerate(data['licenses']):
        prefix = f'licenses[{i}]'
        def fail(message):
            errors.append(f'{prefix}: {message}')
        if not isinstance(row, dict):
            fail('must be an object')
            continue
        required = BASE_FIELDS | (STATE_FIELDS if data['schemaVersion'] == SCHEMA else set())
        if set(row) != required:
            fail(f'Missing fields: {sorted(required - set(row))}; unexpected: {sorted(set(row) - required)}')
        for field in ('licenseId', 'gameName', 'grantor'):
            if not isinstance(row.get(field), str) or not row[field].strip():
                fail(field + ' must be a nonempty string')
        ident = row.get('licenseId')
        if isinstance(ident, str):
            if ident in ids:
                fail('duplicate licenseId')
            ids.add(ident)
        for field in ('universeId', 'groupId'):
            if not isinstance(row.get(field), str) or not re.fullmatch(r'[1-9][0-9]*', row[field]):
                fail(field + ' must be a positive numeric string')
        if row.get('basis') not in ('owner-issued-permission', 'license-agreement'):
            fail('invalid basis')
        for field in ('agreementId', 'grantReference', 'scopeReference', 'terminationTermsReference',
                      *(['statusReference'] if data['schemaVersion'] == SCHEMA else [])):
            value = row.get(field)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                fail(field + ' must be null or a nonempty string')
        if row.get('basis') == 'license-agreement' and not row.get('agreementId'):
            fail('license-agreement requires agreementId')
        if type(row.get('operatorAcceptanceRecorded')) is not bool:
            fail('operatorAcceptanceRecorded must be boolean')
        revoke = row.get('revocableAtWill')
        if revoke is not None and type(revoke) is not bool:
            fail('revocableAtWill must be boolean or null')
        if row.get('registryRemovalTerminatesPermission') is not False:
            fail('registryRemovalTerminatesPermission must be false')
        if row.get('registryStatus') not in ('listed', 'archived'):
            fail('registryStatus must be listed or archived')
        try:
            start = timestamp(row.get('startsAt'))
            if row.get('duration') == 'fixed-term':
                if timestamp(row.get('expiresAt')) <= start:
                    fail('expiresAt must be later than startsAt')
            elif row.get('duration') == 'perpetual':
                if row.get('expiresAt') is not None:
                    fail('perpetual requires expiresAt: null')
            else:
                fail('invalid duration')
        except (TypeError, ValueError) as exc:
            fail('Invalid start/expiry: ' + str(exc))
        if data['schemaVersion'] == SCHEMA:
            state = row.get('permissionState')
            if state not in STATES:
                fail('invalid permissionState')
            elif state == 'grant-recorded':
                if row.get('statusEffectiveAt') is not None or row.get('statusReference') is not None:
                    fail('grant-recorded requires null statusEffectiveAt and statusReference')
            else:
                try:
                    if timestamp(row.get('statusEffectiveAt')) < timestamp(row.get('startsAt')):
                        fail('recorded ending cannot precede startsAt')
                except (TypeError, ValueError):
                    fail('recorded ending requires a valid statusEffectiveAt')
                if not row.get('statusReference'):
                    fail('recorded ending requires statusReference')
    return errors


def require_valid(data):
    errors = validate(data)
    if errors:
        raise ValueError('\n'.join(errors))


def upgrade(data):
    require_valid(data)
    result = copy.deepcopy(data)
    if result['schemaVersion'] == '1.0':
        result['schemaVersion'] = SCHEMA
        for row in result['licenses']:
            row.update(permissionState='grant-recorded', statusEffectiveAt=None, statusReference=None)
    return result


def atomic_write(path, raw):
    """Stage beside destination, flush, then replace; no in-place JSON truncation."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError(f'Another save may be running. Lock: {path}\n'
                         'After a crash, close other managers before removing ONLY this lock file.') from None
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(f'pid={os.getpid()} time={now()}\n')
        yield
    finally:
        path.unlink(missing_ok=True)


class Store:
    def __init__(self, path, state_dir=None):
        self.path = Path(path).expanduser().resolve()
        key = digest(os.path.normcase(str(self.path)).encode())[:24]
        home = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share')))
        self.state = Path(state_dir).resolve() if state_dir else home / 'RanuLicenseManager' / key
        # Journal contains private evidence. Never place it beside public files.
        if self.state == self.path.parent or self.path.parent in self.state.parents:
            raise ValueError('Private state directory must be outside the registry folder.')
        self.state.mkdir(parents=True, exist_ok=True)
        self.events = self.state / 'events'
        self.events.mkdir(exist_ok=True)
        with locked(self.state / 'manager.lock'):
            self.recover()
        self.reload()

    def recover(self):
        pending = self.state / 'pending.json'
        if not pending.exists():
            return
        event = decode(pending.read_bytes())
        actual = digest(self.path.read_bytes()) if self.path.exists() else None
        if actual == event['afterHash']:
            atomic_write(self.events / (event['eventId'] + '.json'), encode(event))
        elif actual != event['beforeHash']:
            raise ValueError('Interrupted save conflicts with an external edit. Retain pending.json and backups; '
                             'resolve the files before continuing. No automatic overwrite performed.')
        pending.unlink()

    def reload(self):
        self.raw = self.path.read_bytes() if self.path.exists() else None
        self.original = decode(self.raw) if self.raw is not None else {'schemaVersion':SCHEMA, 'licenses':[]}
        self.data = upgrade(self.original)

    def history(self):
        return [decode(path.read_bytes()) for path in sorted(self.events.glob('*.json'))]

    def all_used_ids(self):
        ids = {r['licenseId'] for r in self.data['licenses']}
        for event in self.history():
            ids.update(r['licenseId'] for r in event['before']['licenses'])
            ids.update(r['licenseId'] for r in event['after']['licenses'])
        return ids

    def next_id(self):
        used = self.all_used_ids()
        i = 1
        while f'LIC-{i:03d}' in used:
            i += 1
        return f'LIC-{i:03d}'

    def commit(self, data, action, evidence):
        require_valid(data)
        output = encode(data)
        event_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + uuid.uuid4().hex[:8]
        before_rows = {r['licenseId']:r for r in upgrade(self.original)['licenses']}
        after_rows = {r['licenseId']:r for r in data['licenses']}
        changed_ids = sorted(ident for ident in before_rows.keys() | after_rows.keys()
                             if before_rows.get(ident) != after_rows.get(ident))
        event = dict(eventId=event_id, recordedAt=now(), action=action, registryPath=str(self.path),
                     beforeHash=digest(self.raw) if self.raw is not None else None,
                     afterHash=digest(output), before=self.original, after=data, evidence=evidence,
                     changedLicenseIds=changed_ids)
        with locked(self.state / 'manager.lock'):
            self.recover()
            current = self.path.read_bytes() if self.path.exists() else None
            if current != self.raw:
                raise ValueError('Registry changed outside this session. Reload, review, and retry; nothing overwritten.')
            if self.raw is not None:
                atomic_write(self.state / 'backups' / (event_id + '.json'), self.raw)
            pending = self.state / 'pending.json'
            atomic_write(pending, encode(event))
            # Check again after preparing private records, just before replacement.
            if (self.path.read_bytes() if self.path.exists() else None) != self.raw:
                pending.unlink()
                raise ValueError('External edit detected before replacement; reload and retry.')
            atomic_write(self.path, output)
            atomic_write(self.events / (event_id + '.json'), encode(event))
            pending.unlink()
        self.reload()
        return event_id


def row_for(data, ident):
    for row in data['licenses']:
        if row['licenseId'] == ident:
            return row
    raise ValueError('Unknown licenseId: ' + ident)


def extend_record(row, end, reference, at=None):
    at = at or now()
    if row['permissionState'] != 'grant-recorded':
        raise ValueError('An ended permission needs a new grant, not an expiry extension.')
    if row['duration'] != 'fixed-term':
        raise ValueError('This permission already has no scheduled expiry. Use documented amendment for term changes.')
    if timestamp(row['expiresAt']) <= timestamp(at):
        raise ValueError('The recorded term has expired. Use Give permission again / new grant to preserve the gap.')
    if timestamp(end) <= timestamp(row['expiresAt']):
        raise ValueError('Extension must end later than the current expiry. Shortening requires a documented amendment.')
    if not reference.strip():
        raise ValueError('An extension reference is required.')
    row['expiresAt'] = end
    # Keep original grantReference; the amendment reference is retained in the private audit.


def end_record(row, mode, effective, reference, terms, at=None):
    at = at or now()
    if row['permissionState'] != 'grant-recorded':
        raise ValueError('An ending is already recorded. Use status correction if the record is mistaken.')
    if mode == 'at-will' and row['revocableAtWill'] is not True:
        raise ValueError('At-will revocation is not established. Do not change unknown/false just to bypass this check.')
    if mode not in ('at-will', 'other-ground'):
        raise ValueError('Unknown ending type.')
    if not terms.strip() or not reference.strip():
        raise ValueError('Authority/terms and public status references are required.')
    if not timestamp(row['startsAt']) <= timestamp(effective) <= timestamp(at):
        raise ValueError('Record completed endings only, between the recorded start and now. No scheduled shutdowns.')
    row.update(permissionState='revocation-recorded' if mode == 'at-will' else 'termination-recorded',
               statusEffectiveAt=effective, statusReference=reference, registryStatus='archived')


def derived_status(row):
    current = timestamp(now())
    if row['permissionState'] != 'grant-recorded':
        if timestamp(row['statusEffectiveAt']) > current:
            return 'future ending recorded; stated effective time has not arrived'
        return row['permissionState'] + ' (owner record)'
    if timestamp(row['startsAt']) > current:
        return 'not started (recorded dates)'
    if row['expiresAt'] and timestamp(row['expiresAt']) <= current:
        return 'past recorded expiry'
    return 'within recorded term; validity not checked'


def ask(label, default=None, optional=False):
    suffix = f' [{default}]' if default is not None else ''
    while True:
        value = input(label + suffix + ': ').strip()
        if value.lower() == '/cancel':
            raise Cancelled()
        if not value and default is not None:
            return str(default)
        if value or optional:
            return value
        print('A value is required. Enter /cancel to return to the menu.')


def choice(label, values, default=None):
    while True:
        value = ask(label + ' (' + '/'.join(values) + ')', default)
        if value in values:
            return value
        print('Choose one of the displayed values.')


def reference(label, old=None):
    value = ask(label + ' (public reference only; - for null)', old or '-', optional=True)
    return None if value in ('', '-') else value


def date_input(label, default=None):
    while True:
        value = ask(label + ' (UTC date or timestamp; a date means 00:00 UTC)', default)
        try:
            result = entered_date(value)
            print('Recorded timestamp:', result)
            return result
        except ValueError as exc:
            print(exc)


def evidence(kind):
    print('The following references/notes stay in the PRIVATE audit log.')
    result = {'reference':ask(kind + ' document/message reference'),
              'explanation':ask('What actually happened / basis for this record'),
              'deliveryEvidence':ask('Delivery evidence or why notice was not required')}
    return result


def acceptance(row):
    answer = choice('Operator acceptance actually recorded', ['yes', 'no'],
                    'yes' if row.get('operatorAcceptanceRecorded') else 'no')
    row['operatorAcceptanceRecorded'] = answer == 'yes'
    return ask('PRIVATE acceptance evidence reference') if answer == 'yes' else None


def terms_form(row):
    row['basis'] = choice('Permission basis', ['owner-issued-permission', 'license-agreement'], row['basis'])
    row['agreementId'] = reference('Agreement reference', row['agreementId'])
    row['startsAt'] = date_input('Permission start', row['startsAt'])
    row['duration'] = choice('Duration', ['fixed-term', 'perpetual'], row['duration'])
    row['expiresAt'] = date_input('Expiry', row['expiresAt']) if row['duration'] == 'fixed-term' else None
    default = {True:'yes', False:'no', None:'unknown'}[row['revocableAtWill']]
    print('YES means the actual grant reserves at-will revocation. NO means it prohibits it.')
    answer = choice('At-will revocation expressly established', ['unknown', 'yes', 'no'], default)
    row['revocableAtWill'] = {'unknown':None, 'yes':True, 'no':False}[answer]
    row['grantReference'] = reference('Original grant reference', row['grantReference'])
    row['scopeReference'] = reference('Covered materials / scope reference', row['scopeReference'])
    row['terminationTermsReference'] = reference('Termination / revocation terms reference', row['terminationTermsReference'])
    if row['revocableAtWill'] is not None and not row['terminationTermsReference']:
        raise ValueError('Express yes/no revocation settings require a terms reference. Use unknown if unspecified.')
    return acceptance(row)


def new_record(store, source=None):
    row = dict(licenseId=store.next_id(), gameName='', universeId='', groupId='',
               basis='owner-issued-permission', grantor='RanuRbx', agreementId=None,
               operatorAcceptanceRecorded=False, startsAt=now(), expiresAt=None,
               duration='fixed-term', revocableAtWill=None,
               registryRemovalTerminatesPermission=False, registryStatus='listed',
               grantReference=None, scopeReference=None, terminationTermsReference=None,
               permissionState='grant-recorded', statusEffectiveAt=None, statusReference=None)
    if source:
        for key in ('gameName', 'universeId', 'groupId', 'grantor'):
            row[key] = source[key]
        print('A NEW grant ID preserves the old permission and any gap. Set terms from the new grant.')
    row['licenseId'] = ask('License ID', row['licenseId'])
    if row['licenseId'] in store.all_used_ids():
        raise ValueError('This ID is in the registry or private history. Use a new ID.')
    for field in ('gameName', 'universeId', 'groupId', 'grantor'):
        row[field] = ask(field, row[field] or None)
    matches = [r['licenseId'] for r in store.data['licenses'] if r['universeId'] == row['universeId']]
    if matches:
        print('Other records for this Universe ID:', ', '.join(matches))
        if choice('A separate grant for this same universe is intentional', ['no', 'yes'], 'no') != 'yes':
            raise Cancelled()
    acceptance_ref = terms_form(row)
    if not row['grantReference'] or not row['scopeReference']:
        raise ValueError('New grants require grantReference and scopeReference; establish the actual grant first.')
    ev = evidence('Issued grant')
    ev['acceptanceEvidence'] = acceptance_ref
    if source:
        ev['relatedLicenseId'] = source['licenseId']
    return row, ev


def save_preview(store, data, action, ev):
    require_valid(data)
    print('\nPUBLIC FILE CHANGES:')
    before = encode(store.original).decode().splitlines()
    after = encode(data).decode().splitlines()
    print('\n'.join(difflib.unified_diff(before, after, fromfile='current', tofile='proposed', lineterm='')))
    print('\nPRIVATE AUDIT DETAILS:\n' + json.dumps(ev, ensure_ascii=False, indent=2))
    print('Registry:', store.path)
    print('Private audit/backups:', store.state)
    print('This records your statement; it does not send notice, verify authority, or publish to GitHub.')
    if ask('Type SAVE to write; anything else cancels', optional=True) != 'SAVE':
        raise Cancelled()
    event_id = store.commit(data, action, ev)
    print('Saved. Audit event:', event_id)


def choose_row(store):
    return row_for(store.data, ask('License ID'))


def list_rows(store):
    query = ask('Search name / ID (Enter for all)', optional=True).casefold()
    for row in store.data['licenses']:
        if query and query not in ' '.join(str(v) for v in row.values()).casefold():
            continue
        print(f'\n{row["licenseId"]} | {row["gameName"]} | universe {row["universeId"]}')
        print(f'  {row["registryStatus"]}; {row["duration"]}; expiry {row["expiresAt"]}; at-will {row["revocableAtWill"]}')
        print(' ', derived_status(row))
    print('\nThese are recorded terms and owner statements, not verified legal status.')


def export_copy(store):
    # Export the bytes actually on disk, not an unsaved in-memory format migration.
    if store.raw is None:
        raise ValueError('Save the registry before exporting.')
    target = Path(ask('Private mirror / export JSON path')).expanduser().resolve()
    if target == store.path or target == store.state or store.state in target.parents:
        raise ValueError('Choose a separate mirror file outside the manager state folder.')
    if target.name.lower() != 'licenses.json':
        raise ValueError('Export target must be named licenses.json to avoid overwriting unrelated files.')
    previous = target.read_bytes() if target.exists() else None
    if previous is not None:
        require_valid(decode(previous))
    print('Copy current saved registry to:', target)
    if ask('Type EXPORT to confirm', optional=True) != 'EXPORT':
        raise Cancelled()
    with locked(store.state / 'manager.lock'):
        if store.path.read_bytes() != store.raw or (target.read_bytes() if target.exists() else None) != previous:
            raise ValueError('Source or target changed. Reload and retry.')
        if previous is not None:
            ident = uuid.uuid4().hex
            atomic_write(store.state / 'exports' / (ident + '.json'), previous)
            atomic_write(store.state / 'exports' / (ident + '-destination.txt'), str(target).encode())
        atomic_write(target, store.raw)
    print('Exported. No GitHub upload performed.')


def run_action(store, command):
    data = copy.deepcopy(store.data)
    if command == '1':
        list_rows(store)
        return
    if command == '2':
        print(json.dumps(choose_row(store), ensure_ascii=False, indent=2))
        return
    if command == '3':
        row, ev = new_record(store)
        data['licenses'].append(row)
        action = 'add-grant'
    elif command == '4':
        row = row_for(data, choose_row(store)['licenseId'])
        ev = evidence('Effective expiry extension')
        end = date_input('New expiry')
        extend_record(row, end, ev['reference'])
        action = 'extend-expiry'
    elif command == '5':
        row = row_for(data, choose_row(store)['licenseId'])
        print('Record only a completed, effective action. Archive/delete alone cannot end permission.')
        mode = choice('Ending basis', ['at-will', 'other-ground'])
        terms = ask('PRIVATE authority / applicable termination terms reference')
        public_ref = ask('PUBLIC non-sensitive ending reference')
        effective = date_input('Actual effective ending', now())
        ev = evidence('Ending and notice compliance')
        ev['authorityReference'] = terms
        end_record(row, mode, effective, public_ref, terms)
        action = 'record-ending'
    elif command == '6':
        source = choose_row(store)
        row, ev = new_record(store, source)
        data['licenses'].append(row)
        action = 'new-grant-related-to-prior'
    elif command == '7':
        row = row_for(data, choose_row(store)['licenseId'])
        row['registryStatus'] = choice('Administrative listing', ['listed', 'archived'], row['registryStatus'])
        ev = {'reason':ask('PRIVATE reason for listing change')}
        action = 'archive-or-unarchive'
    elif command == '8':
        row = choose_row(store)
        print('REMOVE deletes the public row. It does not revoke permission. Private history retains the row.')
        if ask('Type the exact licenseId again to select removal') != row['licenseId']:
            raise Cancelled()
        data['licenses'] = [r for r in data['licenses'] if r['licenseId'] != row['licenseId']]
        ev = {'reason':ask('PRIVATE reason for removing the row'), 'removedLicenseId':row['licenseId']}
        action = 'remove-row'
    elif command == '9':
        ident = ask('Removed licenseId to recover')
        if any(r['licenseId'] == ident for r in data['licenses']):
            raise ValueError('This ID is already listed or archived.')
        found = None
        for event in reversed(store.history()):
            if event['action'] == 'remove-row' and event['evidence']['removedLicenseId'] == ident:
                found = copy.deepcopy(row_for(upgrade(event['before']), ident))
                break
        if not found:
            raise ValueError('No removal found in this registry path\'s private history.')
        found['registryStatus'] = 'archived'
        data['licenses'].append(found)
        ev = {'reason':ask('PRIVATE reason for restoring the row'), 'restoredLicenseId':ident}
        action = 'restore-row-only'
    elif command == '10':
        row = row_for(data, choose_row(store)['licenseId'])
        for field in ('gameName', 'universeId', 'groupId', 'grantor'):
            row[field] = ask(field, row[field])
        ev = evidence('Metadata correction (ID changes must describe the same intended recipient/experience)')
        action = 'correct-metadata'
    elif command == '11':
        row = row_for(data, choose_row(store)['licenseId'])
        if row['permissionState'] != 'grant-recorded':
            raise ValueError('Use a new grant for an ended permission, or correct a factually mistaken status first.')
        print('This can record changed duration, revocation, scope, dates, or basis ONLY from an effective amendment/correction.')
        acceptance_ref = terms_form(row)
        ev = evidence('Effective amendment or factual correction')
        ev['acceptanceEvidence'] = acceptance_ref
        action = 'amend-or-correct-terms'
    elif command == '12':
        row = row_for(data, choose_row(store)['licenseId'])
        print('Use only for a factually mistaken ending entry. To give permission again, use option 6.')
        if row['permissionState'] == 'grant-recorded':
            raise ValueError('No ending is recorded.')
        ev = evidence('Evidence that the recorded ending was mistaken')
        row.update(permissionState='grant-recorded', statusEffectiveAt=None, statusReference=None)
        action = 'correct-mistaken-ending'
    elif command == '13':
        query = ask('History licenseId filter (Enter for all)', optional=True)
        for event in store.history():
            if query and query not in event.get('changedLicenseIds', []) and query != event['evidence'].get('relatedLicenseId'):
                continue
            print(event['eventId'], event['action'], json.dumps(event['evidence'], ensure_ascii=False))
        print('Private full before/after records and backups:', store.state)
        return
    elif command == '14':
        require_valid(store.original)
        print('PASS: file structure valid. Legal validity and Roblox IDs are not verified.')
        return
    elif command == '15':
        export_copy(store)
        return
    elif command == '16':
        store.reload()
        print('Reloaded current file; no changes saved.')
        return
    elif command == '17':
        ev = {'reason':'Initialize empty registry or record format 1.1 without altering grant terms.'}
        action = 'save-format'
    else:
        print('Choose a displayed menu number.')
        return
    save_preview(store, data, action, ev)


MENU = '''
 1 List/search games              2 View full record
 3 Add newly issued permission    4 Extend unexpired fixed term
 5 Record revocation/termination   6 Give permission again (NEW grant)
 7 Archive/unarchive listing       8 Remove public row (not revocation)
 9 Recover removed row           10 Correct name/IDs/owner metadata
11 Amend/correct permission terms 12 Correct mistaken ending record
13 Private audit history         14 Validate saved JSON
15 Export private mirror         16 Reload external edits
17 Initialize/save format        0 Exit
'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('registry', nargs='?', help='Path to licenses.json')
    parser.add_argument('--validate', action='store_true', help='Read-only validation; no private state created')
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='replace')
    try:
        registry = args.registry
        if not registry:
            if args.validate:
                registry = 'licenses.json'
            else:
                registry = ask('Path to public/local licenses.json', str(Path(__file__).resolve().with_name('licenses.json')))
        if args.validate:
            require_valid(decode(Path(registry).read_bytes()))
            print('PASS: registry structure valid; legal validity not checked.')
            return 0
        store = Store(registry)
        print(f'\nRanuRbx License Manager {VERSION} | schema 1.0 / 1.1')
        print('Registry:', store.path)
        print('PRIVATE audit/backups:', store.state)
        print('Local files only. No messages, GitHub publishing, DMCA, or Roblox shutdowns.')
        print('Enter /cancel at a prompt to cancel the unsaved action. Dates are UTC.')
        while True:
            print(MENU)
            command = input('Choose: ').strip()
            if command == '0':
                return 0
            try:
                run_action(store, command)
            except Cancelled:
                print('Cancelled; nothing saved.')
            except (OSError, ValueError, TypeError) as exc:
                print('Action stopped:', exc)
                print('If a save failed, close and reopen to recover any pending transaction.')
    except (EOFError, KeyboardInterrupt, Cancelled):
        print('\nClosed. Unsaved form input was discarded; any interrupted save is checked next launch.')
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print('Unable to open/validate:', exc)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

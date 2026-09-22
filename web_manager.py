"""Loopback-only web interface for RanuRbx's local permission registry. Python 3.10+."""
from __future__ import annotations

import argparse
import copy
import csv
import difflib
import io
import json
import secrets
import sys
import threading
import time
import webbrowser
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import license_manager as core

ASSETS = Path(__file__).resolve().parent / 'web'
LIMIT = 1024 * 1024


class Conflict(ValueError):
    pass


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + ' is required.')
    if len(value) > 12000:
        raise ValueError(name + ' is too long.')
    return value.strip()


def revision(store):
    return core.digest(store.raw) if store.raw is not None else 'new-file'


def date_state(row):
    current = core.timestamp(core.now())
    if row['permissionState'] != 'grant-recorded':
        return 'ending-future' if core.timestamp(row['statusEffectiveAt']) > current else 'ending-recorded'
    if core.timestamp(row['startsAt']) > current:
        return 'not-started'
    if row['expiresAt']:
        end = core.timestamp(row['expiresAt'])
        if end <= current:
            return 'expired'
        if end <= current + timedelta(days=30):
            return 'expiring'
    return 'within-term'


def csv_export(data):
    data = core.upgrade(data)
    stream = io.StringIO(newline='')
    fields = ['licenseId', 'gameName', 'universeId', 'groupId', 'duration', 'startsAt',
              'expiresAt', 'revocableAtWill', 'registryStatus', 'permissionState', 'statusEffectiveAt']
    writer = csv.writer(stream)
    writer.writerow(fields)
    for row in data['licenses']:
        cells = []
        for field in fields:
            value = row[field]
            value = '' if value is None else str(value)
            # Prevent spreadsheet formulas when opening a user-controlled game name.
            if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')):
                value = "'" + value
            cells.append(value)
        writer.writerow(cells)
    return ('\ufeff' + stream.getvalue()).encode('utf-8')


class Application:
    def __init__(self, registry, state_dir=None, mirror=None):
        self.store = core.Store(registry, state_dir)
        self.mirror = Path(mirror).expanduser().resolve() if mirror else None
        if self.mirror:
            if self.mirror == self.store.path or self.mirror.name.lower() != 'licenses.json':
                raise ValueError('Mirror must be a different file named licenses.json.')
            if self.mirror == self.store.state or self.store.state in self.mirror.parents:
                raise ValueError('Mirror must be outside private manager storage.')
        self.lock = threading.RLock()
        self.previews = {}

    def refresh(self):
        # In-process recovery also prevents continuing from an interrupted pending write.
        with core.locked(self.store.state / 'manager.lock'):
            self.store.recover()
        self.store.reload()

    def records_removed(self, events):
        present = {r['licenseId'] for r in self.store.data['licenses']}
        removed = {}
        for event in events:
            after_ids = {r['licenseId'] for r in event['after']['licenses']}
            for row in core.upgrade(event['before'])['licenses']:
                if row['licenseId'] not in after_ids and row['licenseId'] not in present:
                    removed[row['licenseId']] = row
        return removed

    def state(self):
        self.refresh()
        data = copy.deepcopy(self.store.data)
        summary = {'total':len(data['licenses']), 'expiring':0, 'expired':0, 'archived':0, 'ended':0}
        for row in data['licenses']:
            row['dateState'] = date_state(row)
            row['dateDescription'] = core.derived_status(row)
            summary['expiring'] += row['dateState'] == 'expiring'
            summary['expired'] += row['dateState'] == 'expired'
            summary['ended'] += row['dateState'] == 'ending-recorded'
            summary['archived'] += row['registryStatus'] == 'archived'
        events = self.store.history()
        mirror_state = 'not-configured'
        if self.mirror:
            mirror_state = 'missing' if not self.mirror.exists() else (
                'matches' if self.mirror.read_bytes() == self.store.raw else 'different')
        return dict(revision=revision(self.store), records=data['licenses'], summary=summary,
                    registryPath=str(self.store.path), privatePath=str(self.store.state),
                    mirrorPath=str(self.mirror) if self.mirror else None, mirrorState=mirror_state,
                    nextId=self.store.next_id(), now=core.now(), schemaVersion=core.SCHEMA,
                    removed=list(self.records_removed(events).values()),
                    history=[{k:e.get(k) for k in ('eventId','recordedAt','action','changedLicenseIds','evidence')}
                             for e in reversed(events[-100:])], historyTotal=len(events))

    def evidence(self, payload, full=False):
        ev = payload.get('evidence')
        if not isinstance(ev, dict):
            raise ValueError('Private audit details are required.')
        result = {'explanation':text(ev.get('explanation'), 'Private reason')}
        if full:
            result['reference'] = text(ev.get('reference'), 'Evidence reference')
            result['deliveryEvidence'] = text(ev.get('deliveryEvidence'), 'Delivery evidence / why not required')
        if ev.get('acceptanceEvidence'):
            result['acceptanceEvidence'] = text(ev['acceptanceEvidence'], 'Acceptance evidence')
        return result

    def plan(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('Expected an action object.')
        action = payload.get('action')
        data = copy.deepcopy(self.store.data)
        full = action in ('create', 'regrant', 'edit', 'extend', 'end', 'correct-ending')
        ev = self.evidence(payload, full)
        if action in ('create', 'regrant', 'edit'):
            submitted = payload.get('record')
            if not isinstance(submitted, dict) or set(submitted) != core.BASE_FIELDS:
                raise ValueError('The record must contain exactly the editable registry fields.')
            row = copy.deepcopy(submitted)
            ident = row['licenseId']
            if action == 'edit':
                previous = core.row_for(data, text(payload.get('licenseId'), 'License ID'))
                if ident != previous['licenseId']:
                    raise ValueError('The existing license ID cannot be changed.')
                if previous['permissionState'] != 'grant-recorded':
                    raise ValueError('Use a new grant after an ending, or correct a mistaken ending first.')
                row.update({k:previous[k] for k in core.STATE_FIELDS})
                data['licenses'][data['licenses'].index(previous)] = row
            else:
                text(ident, 'License ID')
                if ident in self.store.all_used_ids():
                    raise ValueError('This license ID has already been used; choose another.')
                text(row.get('grantReference'), 'Grant reference')
                text(row.get('scopeReference'), 'Scope reference')
                matches = [r for r in data['licenses'] if r['universeId'] == row['universeId']]
                if matches and payload.get('allowSameUniverse') is not True:
                    raise ValueError('A record already exists for this universe. Confirm a separate grant is intentional.')
                row.update(permissionState='grant-recorded', statusEffectiveAt=None, statusReference=None)
                data['licenses'].append(row)
                if action == 'regrant':
                    prior = core.row_for(self.store.data, text(payload.get('licenseId'), 'Prior license ID'))
                    if row['universeId'] != prior['universeId']:
                        raise ValueError('A related new grant must identify the same universe. Use Add game for another.')
                    ev['relatedLicenseId'] = prior['licenseId']
            if row['revocableAtWill'] is not None:
                text(row['terminationTermsReference'], 'Express revocation/termination terms reference')
            if row['operatorAcceptanceRecorded'] is True and not ev.get('acceptanceEvidence'):
                raise ValueError('Recorded acceptance requires private evidence of actual acceptance.')
        elif action == 'extend':
            row = core.row_for(data, text(payload.get('licenseId'), 'License ID'))
            core.extend_record(row, core.entered_date(text(payload.get('expiresAt'), 'New expiry')), ev['reference'])
        elif action == 'end':
            row = core.row_for(data, text(payload.get('licenseId'), 'License ID'))
            terms = text(payload.get('authorityReference'), 'Ending authority / terms')
            core.end_record(row, payload.get('mode'), core.entered_date(text(payload.get('effectiveAt'), 'Effective timestamp')),
                            text(payload.get('statusReference'), 'Public ending reference'), terms)
            ev['authorityReference'] = terms
        elif action in ('archive', 'unarchive', 'remove'):
            ids = payload.get('licenseIds')
            if not isinstance(ids, list) or not ids or not all(isinstance(i,str) for i in ids) or len(set(ids)) != len(ids):
                raise ValueError('Select one or more distinct license IDs.')
            for ident in ids:
                row = core.row_for(data, ident)
                if action == 'remove':
                    data['licenses'].remove(row)
                else:
                    row['registryStatus'] = 'archived' if action == 'archive' else 'listed'
            ev['affectedLicenseIds'] = ids
        elif action == 'recover':
            ident = text(payload.get('licenseId'), 'Removed ID')
            removed = self.records_removed(self.store.history())
            if ident not in removed:
                raise ValueError('No removed record exists for that ID in this path\'s local history.')
            row = copy.deepcopy(removed[ident])
            row['registryStatus'] = 'archived'
            data['licenses'].append(row)
        elif action == 'correct-ending':
            row = core.row_for(data, text(payload.get('licenseId'), 'License ID'))
            if row['permissionState'] == 'grant-recorded':
                raise ValueError('No ending is recorded.')
            row.update(permissionState='grant-recorded', statusEffectiveAt=None, statusReference=None)
        elif action != 'initialize':
            raise ValueError('Unknown action.')
        core.require_valid(data)
        return data, 'web-' + action, ev

    def preview(self, payload):
        self.refresh()
        if payload.get('revision') != revision(self.store):
            raise Conflict('The registry changed. Refresh the dashboard and review your action again.')
        for ident, item in list(self.previews.items()):
            if item['expires'] < time.monotonic():
                del self.previews[ident]
        if len(self.previews) >= 50:
            raise ValueError('Too many open previews. Finish or discard one, or wait ten minutes.')
        if payload.get('action') == 'mirror':
            if self.mirror is None or self.store.raw is None:
                raise ValueError('Configure a mirror at startup and save the registry first.')
            prior = self.mirror.read_bytes() if self.mirror.exists() else None
            if prior is not None:
                core.require_valid(core.decode(prior))
            before, after = prior.decode('utf-8-sig') if prior else '', self.store.raw.decode('utf-8-sig')
            data, action, ev = None, 'mirror', self.evidence(payload)
            target_hash = core.digest(prior) if prior is not None else None
        else:
            data, action, ev = self.plan(payload)
            before, after = core.encode(self.store.original).decode(), core.encode(data).decode()
            target_hash = None
        diff = '\n'.join(difflib.unified_diff(before.splitlines(), after.splitlines(),
                    fromfile='current', tofile='proposed', lineterm=''))
        if not diff:
            raise ValueError('No file changes to save.')
        ident = secrets.token_urlsafe(24)
        self.previews[ident] = dict(payload=copy.deepcopy(payload), data=data, action=action, evidence=ev,
                                    revision=revision(self.store), expires=time.monotonic()+600,
                                    targetHash=target_hash)
        return dict(previewId=ident, diff=diff, evidence=ev, action=action,
                    target=str(self.mirror if action == 'mirror' else self.store.path))

    def commit(self, ident):
        item = self.previews.pop(text(ident, 'Preview ID'), None)
        if not item or item['expires'] < time.monotonic():
            raise Conflict('Preview expired or already used. Review a fresh preview.')
        self.refresh()
        if item['revision'] != revision(self.store):
            raise Conflict('The registry changed after preview. Nothing overwritten; create a fresh preview.')
        if item['action'] == 'mirror':
            with core.locked(self.store.state/'manager.lock'):
                prior = self.mirror.read_bytes() if self.mirror.exists() else None
                current_hash = core.digest(prior) if prior is not None else None
                if current_hash != item['targetHash'] or self.store.path.read_bytes() != self.store.raw:
                    raise Conflict('Source or mirror changed after preview. Nothing overwritten.')
                event_id = secrets.token_hex(16)
                if prior is not None:
                    core.atomic_write(self.store.state/'exports'/(event_id+'.json'), prior)
                core.atomic_write(self.store.state/'exports'/(event_id+'-destination.txt'), str(self.mirror).encode())
                core.atomic_write(self.mirror, self.store.raw)
            return {'message':'Private mirror exported. No GitHub upload performed.'}
        # Time-sensitive rules are evaluated again, not just at preview time.
        data, action, ev = self.plan(item['payload'])
        if data != item['data']:
            raise Conflict('The proposed data changed. Review a fresh preview.')
        event_id = self.store.commit(data, action, ev)
        return {'message':'Saved locally with a private backup and audit record.', 'eventId':event_id}


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, app, port=8765):
        self.app = app
        self.token = secrets.token_urlsafe(32)
        super().__init__(('127.0.0.1', port), Handler)
        self.authority = f'127.0.0.1:{self.server_port}'
        self.origin = 'http://' + self.authority


class Handler(BaseHTTPRequestHandler):
    server_version = 'RanuLocal/1.0'

    def log_message(self, *args):
        # Do not log tokens, evidence, or user-controlled strings.
        pass

    def respond(self, status, body, content_type='application/json; charset=utf-8', filename=None):
        if isinstance(body, (dict,list)):
            body = core.encode(body)
        elif isinstance(body,str):
            body = body.encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        if filename:
            self.send_header('Content-Disposition', 'attachment; filename="'+filename+'"')
        self.end_headers()
        self.wfile.write(body)

    def allowed(self, api=False):
        if self.headers.get('Host') != self.server.authority:
            self.respond(403, {'error':'Use the exact local address printed by the launcher.'})
            return False
        origin = self.headers.get('Origin')
        if origin is not None and origin != self.server.origin:
            self.respond(403, {'error':'Cross-origin requests are not allowed.'})
            return False
        if api:
            expected = 'Bearer ' + self.server.token
            if not secrets.compare_digest(self.headers.get('Authorization', '').encode('utf-8'), expected.encode('utf-8')):
                self.respond(401, {'error':'Session unavailable. Open the full launch address again.'})
                return False
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        if not self.allowed(path.startswith('/api/')):
            return
        try:
            with self.server.app.lock:
                app = self.server.app
                if path == '/api/state':
                    return self.respond(200, app.state())
                if path in ('/api/download/json', '/api/download/csv'):
                    app.refresh()
                    if path.endswith('json'):
                        return self.respond(200, app.store.raw or core.encode(app.store.data), filename='licenses.json')
                    return self.respond(200, csv_export(app.store.data), 'text/csv; charset=utf-8', 'licenses.csv')
                if path.startswith('/api/history/'):
                    ident = path.rsplit('/',1)[1]
                    # Match known IDs; never map user-controlled paths to the filesystem.
                    event = next((e for e in app.store.history() if e['eventId'] == ident), None)
                    return self.respond(200 if event else 404, event or {'error':'Event not found.'})
            files = {'/':('index.html','text/html; charset=utf-8'),
                     '/app.js':('app.js','text/javascript; charset=utf-8'),
                     '/style.css':('style.css','text/css; charset=utf-8')}
            if path in files:
                name, kind = files[path]
                return self.respond(200, (ASSETS/name).read_bytes(), kind)
            self.respond(404, {'error':'Not found.'})
        except (OSError, ValueError, TypeError) as exc:
            self.respond(400, {'error':str(exc)})

    def do_POST(self):
        if not self.allowed(True):
            return
        try:
            if self.headers.get_content_type() != 'application/json':
                raise ValueError('Expected application/json.')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= LIMIT:
                raise ValueError('Request size must be between 1 byte and 1 MiB.')
            self.connection.settimeout(10)
            payload = core.decode(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('Expected a JSON object.')
            with self.server.app.lock:
                app = self.server.app
                path = urlsplit(self.path).path
                if path == '/api/preview':
                    return self.respond(200, app.preview(payload))
                if path == '/api/commit':
                    return self.respond(200, app.commit(payload.get('previewId')))
                if path == '/api/discard':
                    app.previews.pop(text(payload.get('previewId'), 'Preview ID'), None)
                    return self.respond(200, {'message':'Preview discarded.'})
                self.respond(404, {'error':'Not found.'})
        except Conflict as exc:
            self.respond(409, {'error':str(exc)})
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self.respond(400, {'error':str(exc)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('registry', nargs='?', default=str(Path(__file__).with_name('licenses.json')))
    parser.add_argument('--mirror', help='Optional fixed private licenses.json export destination')
    parser.add_argument('--port', type=int, default=8765, help='Local port; 0 selects a free port')
    parser.add_argument('--state-dir', help='Private state directory outside the registry folder; normally automatic')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--choose-registry', action='store_true', help='Ask for the canonical public registry path before starting')
    args = parser.parse_args()
    try:
        if args.choose_registry:
            print('Choose the canonical PUBLIC registry working copy, not an independent private mirror.')
            args.registry = input('Full path to public licenses.json: ').strip().strip('"')
            if not args.registry:
                raise ValueError('A canonical registry path is required.')
        app = Application(args.registry, args.state_dir, args.mirror)
        server = Server(app, args.port)
    except (OSError,ValueError,EOFError) as exc:
        print('Cannot start:', exc, '\nIf the port is busy, retry with --port 0.', file=sys.stderr)
        return 1
    url = server.origin + '/#token=' + server.token
    print('Registry:', app.store.path, flush=True)
    print('Private history:', app.store.state, flush=True)
    print('Open this private local session address:', url, flush=True)
    print('Keep this terminal open. Ctrl+C stops the server. No GitHub publishing occurs.', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

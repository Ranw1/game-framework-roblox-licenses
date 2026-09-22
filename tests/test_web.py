import copy
from contextlib import redirect_stdout
import http.client
import json
import io
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import license_manager as core
import web_manager as web
from test_manager import sample


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.path=self.root/'public/licenses.json'
        self.path.parent.mkdir()
        self.path.write_bytes(core.encode(sample()))
        self.mirror=self.root/'private/licenses.json'
        self.mirror.parent.mkdir()
        self.mirror.write_bytes(core.encode(sample()))
        self.app=web.Application(self.path,self.root/'audit',self.mirror)

    def tearDown(self):
        self.tmp.cleanup()

    def payload(self,action,**kwargs):
        return dict(action=action,revision=self.app.state()['revision'],
            evidence={'reference':'DOC-1','explanation':'Actual event recorded','deliveryEvidence':'Delivered message'},**kwargs)

    def newrow(self,ident='LIC-002'):
        row=copy.deepcopy(sample()['licenses'][0])
        row.update(licenseId=ident,universeId='23456',grantReference='GRANT-2',scopeReference='SCOPE-2')
        return row

    def test_preview_is_read_only_and_commit_is_one_use(self):
        original=self.path.read_bytes()
        preview=self.app.preview(self.payload('create',record=self.newrow()))
        self.assertEqual(self.path.read_bytes(),original)
        self.app.commit(preview['previewId'])
        self.assertEqual(len(core.decode(self.path.read_bytes())['licenses']),2)
        with self.assertRaises(web.Conflict):self.app.commit(preview['previewId'])

    def test_missing_private_reason_rejected(self):
        payload=self.payload('archive',licenseIds=['LIC-001']);payload['evidence']={}
        with self.assertRaises(ValueError):self.app.preview(payload)

    def test_changed_on_disk_blocks_stale_form(self):
        payload=self.payload('archive',licenseIds=['LIC-001'])
        changed=sample();changed['licenses'][0]['gameName']='external'
        self.path.write_bytes(core.encode(changed))
        with self.assertRaises(web.Conflict):self.app.preview(payload)

    def test_changed_after_preview_blocks_save(self):
        preview=self.app.preview(self.payload('archive',licenseIds=['LIC-001']))
        changed=sample();changed['licenses'][0]['gameName']='external'
        self.path.write_bytes(core.encode(changed))
        with self.assertRaises(web.Conflict):self.app.commit(preview['previewId'])
        self.assertEqual(core.decode(self.path.read_bytes()),changed)

    def test_two_tabs_cannot_overwrite_each_other(self):
        p1=self.app.preview(self.payload('archive',licenseIds=['LIC-001']))
        p2=self.app.preview(self.payload('create',record=self.newrow()))
        self.app.commit(p1['previewId'])
        with self.assertRaises(web.Conflict):self.app.commit(p2['previewId'])

    def test_unknown_fields_and_lifecycle_injection_rejected(self):
        for extra in ('permissionState','arbitraryField'):
            row=self.newrow();row[extra]='revocation-recorded'
            with self.assertRaises(ValueError):self.app.preview(self.payload('create',record=row))

    def test_acceptance_needs_evidence(self):
        row=self.newrow();row['operatorAcceptanceRecorded']=True
        with self.assertRaises(ValueError):self.app.preview(self.payload('create',record=row))

    def test_same_universe_needs_confirmation(self):
        row=self.newrow();row['universeId']=sample()['licenses'][0]['universeId']
        with self.assertRaises(ValueError):self.app.preview(self.payload('create',record=row))
        self.assertIn('previewId',self.app.preview(self.payload('create',record=row,allowSameUniverse=True)))

    def test_required_references_for_new_grant(self):
        row=self.newrow();row['scopeReference']=None
        with self.assertRaises(ValueError):self.app.preview(self.payload('create',record=row))
        row['scopeReference']='SCOPE';row['revocableAtWill']=True
        with self.assertRaises(ValueError):self.app.preview(self.payload('create',record=row))

    def test_extension_and_shortening(self):
        with self.assertRaises(ValueError):self.app.preview(self.payload('extend',licenseId='LIC-001',expiresAt='2098-01-01'))
        preview=self.app.preview(self.payload('extend',licenseId='LIC-001',expiresAt='2100-01-01'))
        self.app.commit(preview['previewId'])
        self.assertEqual(self.app.state()['records'][0]['expiresAt'],'2100-01-01T00:00:00Z')

    def test_at_will_unknown_is_not_revocable(self):
        with self.assertRaises(ValueError):self.app.preview(self.payload('end',licenseId='LIC-001',mode='at-will',
            effectiveAt=core.now(),statusReference='END-1',authorityReference='TERMS'))

    def test_ending_and_new_grant_keep_chronology(self):
        preview=self.app.preview(self.payload('end',licenseId='LIC-001',mode='other-ground',
            effectiveAt=core.now(),statusReference='END-1',authorityReference='TERMS'))
        self.app.commit(preview['previewId'])
        row=self.newrow();row['universeId']=sample()['licenses'][0]['universeId']
        preview=self.app.preview(self.payload('regrant',licenseId='LIC-001',record=row,allowSameUniverse=True))
        self.app.commit(preview['previewId'])
        rows=self.app.state()['records'];self.assertEqual(rows[0]['permissionState'],'termination-recorded')
        self.assertEqual(rows[1]['permissionState'],'grant-recorded')

    def test_remove_recover_keeps_id_reserved_and_archived(self):
        p=self.app.preview(self.payload('remove',licenseIds=['LIC-001']));self.app.commit(p['previewId'])
        self.assertEqual(self.app.state()['nextId'],'LIC-002')
        self.assertEqual(len(self.app.state()['removed']),1)
        p=self.app.preview(self.payload('recover',licenseId='LIC-001'));self.app.commit(p['previewId'])
        self.assertEqual(self.app.state()['records'][0]['registryStatus'],'archived')

    def test_atomic_bulk_rejects_missing_id(self):
        before=self.path.read_bytes()
        with self.assertRaises(ValueError):self.app.preview(self.payload('archive',licenseIds=['LIC-001','NOPE']))
        self.assertEqual(self.path.read_bytes(),before)

    def test_cli_recovers_web_removed_record(self):
        p=self.app.preview(self.payload('remove',licenseIds=['LIC-001']));self.app.commit(p['previewId'])
        with patch('builtins.input',side_effect=['LIC-001','Recover the web-removed row','SAVE']),redirect_stdout(io.StringIO()):
            core.run_action(self.app.store,'9')
        self.assertEqual(self.app.state()['records'][0]['registryStatus'],'archived')

    def test_mirror_has_preview_and_backup(self):
        p=self.app.preview(self.payload('archive',licenseIds=['LIC-001']));self.app.commit(p['previewId'])
        before=self.mirror.read_bytes()
        p=self.app.preview(self.payload('mirror'));self.assertEqual(self.mirror.read_bytes(),before)
        self.app.commit(p['previewId'])
        self.assertEqual(self.mirror.read_bytes(),self.path.read_bytes())
        self.assertEqual(len(list((self.app.store.state/'exports').glob('*.json'))),1)

    def test_changed_mirror_not_overwritten(self):
        p=self.app.preview(self.payload('archive',licenseIds=['LIC-001']));self.app.commit(p['previewId'])
        p=self.app.preview(self.payload('mirror'));self.mirror.write_bytes(b'changed')
        with self.assertRaises(web.Conflict):self.app.commit(p['previewId'])
        self.assertEqual(self.mirror.read_bytes(),b'changed')

    def test_csv_formula_injection_neutralized(self):
        data=sample();data['licenses'][0]['gameName']=' =HYPERLINK("bad")'
        output=web.csv_export(data).decode('utf-8-sig')
        self.assertIn("' =HYPERLINK",output)

    def test_expired_dashboard_preserves_original_dates(self):
        data=sample();data['licenses'][0]['expiresAt']='2026-02-01T00:00:00Z';self.path.write_bytes(core.encode(data))
        state=self.app.state();self.assertEqual(state['summary']['expired'],1)
        self.assertEqual(core.decode(self.path.read_bytes()),data)

    def test_audit_private_only(self):
        payload=self.payload('archive',licenseIds=['LIC-001']);payload['evidence']['explanation']='PRIVATE SECRET'
        p=self.app.preview(payload);self.app.commit(p['previewId'])
        self.assertNotIn(b'PRIVATE SECRET',self.path.read_bytes())
        self.assertIn('PRIVATE SECRET',json.dumps(self.app.store.history()))


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        path=root/'public/licenses.json';path.parent.mkdir();path.write_bytes(core.encode(sample()))
        self.app=web.Application(path,root/'audit')
        self.server=web.Server(self.app,0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()

    def request(self,path,method='GET',payload=None,auth=True,host=None,origin=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        headers={'Host':host or self.server.authority}
        if auth:headers['Authorization']='Bearer '+self.server.token
        if origin:headers['Origin']=origin
        raw=None
        if payload is not None:headers['Content-Type']='application/json';raw=json.dumps(payload)
        connection.request(method,path,raw,headers)
        response=connection.getresponse();body=response.read();status=response.status;reply_headers=dict(response.getheaders())
        connection.close();return status,body,reply_headers

    def test_auth_required_for_private_data(self):
        self.assertEqual(self.request('/api/state',auth=False)[0],401)
        self.assertEqual(self.request('/api/state')[0],200)

    def test_host_and_origin_protected(self):
        self.assertEqual(self.request('/api/state',host='evil.example')[0],403)
        self.assertEqual(self.request('/api/state',origin='https://evil.example')[0],403)
        self.assertEqual(self.request('/api/state',origin=self.server.origin)[0],200)

    def test_static_assets_and_security_headers(self):
        status,body,headers=self.request('/',auth=False)
        self.assertEqual(status,200);self.assertIn(b'Permission desk',body)
        self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
        self.assertNotIn(self.server.token.encode(),body)
        for asset in ('/app.js','/style.css'):self.assertEqual(self.request(asset,auth=False)[0],200)

    def test_no_arbitrary_files(self):
        for path in ('/../license_manager.py','/licenses.json','/api/history/../../licenses.json'):
            self.assertEqual(self.request(path)[0],404)

    def test_http_preview_commit_and_repeat(self):
        state=json.loads(self.request('/api/state')[1])
        payload={'action':'archive','revision':state['revision'],'licenseIds':['LIC-001'],'evidence':{'explanation':'archive only'}}
        status,body,_=self.request('/api/preview','POST',payload,origin=self.server.origin)
        self.assertEqual(status,200);ident=json.loads(body)['previewId']
        self.assertEqual(self.request('/api/commit','POST',{'previewId':ident})[0],200)
        self.assertEqual(self.request('/api/commit','POST',{'previewId':ident})[0],409)

    def test_downloads_are_authenticated(self):
        self.assertEqual(self.request('/api/download/json',auth=False)[0],401)
        self.assertEqual(self.request('/api/download/csv')[0],200)


if __name__=='__main__':unittest.main()

import copy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import license_manager as m


def sample():
    return {'schemaVersion':'1.0', 'licenses':[dict(
        licenseId='LIC-001', gameName='Test Game 🏝️', universeId='1234567890', groupId='123456',
        basis='owner-issued-permission', grantor='RanuRbx', agreementId=None,
        operatorAcceptanceRecorded=False, startsAt='2026-01-01T00:00:00Z',
        expiresAt='2099-01-01T00:00:00Z', duration='fixed-term', revocableAtWill=None,
        registryRemovalTerminatesPermission=False, registryStatus='listed',
        grantReference=None, scopeReference=None, terminationTermsReference=None)]}


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry = self.root / 'public/licenses.json'
        self.registry.parent.mkdir()
        self.registry.write_bytes(m.encode(sample()))
        self.state = self.root / 'private-state'
        self.store = m.Store(self.registry, self.state)

    def tearDown(self):
        self.temp.cleanup()

    def test_upgrade_preserves_every_original_field(self):
        original = sample()
        converted = m.upgrade(original)
        self.assertEqual(original, sample())
        self.assertFalse(m.validate(original))
        self.assertFalse(m.validate(converted))
        for key, value in original['licenses'][0].items():
            self.assertEqual(converted['licenses'][0][key], value)

    def test_open_does_not_rewrite_file(self):
        self.assertEqual(self.registry.read_bytes(), m.encode(sample()))
        self.assertFalse(list(self.store.events.glob('*.json')))

    def test_empty_registry_not_created_until_save(self):
        path = self.root / 'empty/licenses.json'
        store = m.Store(path, self.root/'empty-state')
        self.assertFalse(path.exists())
        store.commit(store.data, 'initialize', {})
        self.assertEqual(m.decode(path.read_bytes())['licenses'], [])

    def test_dates_and_unicode_round_trip(self):
        self.assertEqual(m.entered_date('2030-12-01'), '2030-12-01T00:00:00Z')
        self.assertEqual(m.decode(m.encode(sample())), sample())
        for value in ('2030-02-30', '2030-01-01T24:00:00Z', '2030-01-01T00:00:00+03:00'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.entered_date(value)

    def test_validator_rejects_dangerous_or_ambiguous_fields(self):
        changes = [
            {'duration':'perpetual'}, {'expiresAt':None}, {'revocableAtWill':'false'},
            {'revocableAtWill':0}, {'registryRemovalTerminatesPermission':True},
            {'operatorAcceptanceRecorded':1}, {'universeId':123}, {'groupId':'0'},
            {'basis':'license-agreement'}, {'expiresAt':'2026-01-01T00:00:00Z'},
            {'permissionState':'active'}, {'permissionState':'revocation-recorded'},
            {'unknownField':True}, {'statusReference':'unexpected'},
        ]
        for change in changes:
            data = copy.deepcopy(self.store.data)
            data['licenses'][0].update(change)
            with self.subTest(change=change):
                self.assertTrue(m.validate(data))

    def test_duplicate_keys_constants_and_ids_rejected(self):
        for raw in (b'{"licenses":[],"licenses":[]}', b'{"x":NaN}'):
            with self.assertRaises(ValueError):
                m.decode(raw)
        data = copy.deepcopy(self.store.data)
        data['licenses'].append(copy.deepcopy(data['licenses'][0]))
        self.assertTrue(m.validate(data))

    def test_perpetual_unknown_false_true_are_distinct(self):
        for revoke in (None, False, True):
            data = copy.deepcopy(self.store.data)
            data['licenses'][0].update(duration='perpetual', expiresAt=None, revocableAtWill=revoke)
            self.assertFalse(m.validate(data))

    def test_extension_preserves_start_and_original_grant(self):
        row = self.store.data['licenses'][0]
        before = copy.deepcopy(row)
        m.extend_record(row, '2100-01-01T00:00:00Z', 'EXT-1', at='2026-09-01T00:00:00Z')
        before['expiresAt'] = '2100-01-01T00:00:00Z'
        self.assertEqual(row, before)

    def test_shortening_equal_and_expired_extensions_blocked(self):
        for new, at in [('2098-01-01T00:00:00Z','2026-09-01T00:00:00Z'),
                        ('2099-01-01T00:00:00Z','2026-09-01T00:00:00Z'),
                        ('2100-01-01T00:00:00Z','2099-01-01T00:00:00Z')]:
            with self.subTest(new=new, at=at), self.assertRaises(ValueError):
                m.extend_record(self.store.data['licenses'][0], new, 'EXT', at=at)

    def test_at_will_revoke_unknown_or_false_blocked(self):
        row = self.store.data['licenses'][0]
        for value in (None, False):
            row['revocableAtWill'] = value
            with self.assertRaises(ValueError):
                m.end_record(row, 'at-will', '2026-05-01T00:00:00Z', 'END-1', 'TERMS', at='2026-09-01T00:00:00Z')
        self.assertEqual(row['permissionState'], 'grant-recorded')

    def test_record_revocation_without_destroying_term(self):
        row = self.store.data['licenses'][0]
        row['revocableAtWill'] = True
        original_expiry = row['expiresAt']
        m.end_record(row, 'at-will', '2026-05-01T00:00:00Z', 'END-1', 'TERMS', at='2026-09-01T00:00:00Z')
        self.assertEqual(row['permissionState'], 'revocation-recorded')
        self.assertEqual(row['registryStatus'], 'archived')
        self.assertEqual(row['expiresAt'], original_expiry)
        self.assertFalse(m.validate(self.store.data))
        with self.assertRaises(ValueError):
            m.extend_record(row, '2100-01-01T00:00:00Z', 'EXT', at='2026-09-01T00:00:00Z')

    def test_other_ground_requires_evidence_and_valid_time(self):
        row = self.store.data['licenses'][0]
        for effective, terms in [('2027-01-01T00:00:00Z','TERMS'),
                                 ('2025-01-01T00:00:00Z','TERMS'),
                                 ('2026-05-01T00:00:00Z','')]:
            with self.assertRaises(ValueError):
                m.end_record(row, 'other-ground', effective, 'END', terms, at='2026-09-01T00:00:00Z')
        m.end_record(row, 'other-ground', '2026-05-01T00:00:00Z', 'END', 'TERMS', at='2026-09-01T00:00:00Z')
        self.assertEqual(row['permissionState'], 'termination-recorded')

    def test_backup_and_private_audit_are_exact(self):
        raw = self.registry.read_bytes()
        data = copy.deepcopy(self.store.data)
        data['licenses'][0]['expiresAt'] = '2100-01-01T00:00:00Z'
        event = self.store.commit(data, 'extend-expiry', {'privateNote':'SECRET NOTE'})
        self.assertEqual((self.state/'backups'/f'{event}.json').read_bytes(), raw)
        self.assertNotIn(b'SECRET NOTE', self.registry.read_bytes())
        self.assertEqual(self.store.history()[0]['before'], sample())
        self.assertEqual(self.store.history()[0]['after'], data)
        self.assertEqual(self.store.history()[0]['changedLicenseIds'], ['LIC-001'])

    def test_future_ending_import_not_shown_as_already_effective(self):
        row = self.store.data['licenses'][0]
        row.update(permissionState='revocation-recorded', statusEffectiveAt='2099-01-01T00:00:00Z', statusReference='END')
        self.assertIn('has not arrived', m.derived_status(row))

    def test_history_filter_excludes_changes_to_other_games(self):
        data = copy.deepcopy(self.store.data)
        added = copy.deepcopy(data['licenses'][0])
        added['licenseId'] = 'LIC-002'
        data['licenses'].append(added)
        self.store.commit(data, 'add-grant', {'reference':'ONLY-SECOND-GAME'})
        output = io.StringIO()
        with patch('builtins.input', return_value='LIC-001'), redirect_stdout(output):
            m.run_action(self.store, '13')
        self.assertNotIn('ONLY-SECOND-GAME', output.getvalue())

    def test_external_edit_blocks_save(self):
        externally_changed = sample()
        externally_changed['licenses'][0]['gameName'] = 'External edit'
        self.registry.write_bytes(m.encode(externally_changed))
        with self.assertRaises(ValueError):
            self.store.commit(self.store.data, 'save', {})
        self.assertEqual(m.decode(self.registry.read_bytes()), externally_changed)

    def test_second_manager_stale_snapshot_blocks_save(self):
        second = m.Store(self.registry, self.state)
        self.store.commit(self.store.data, 'first', {})
        with self.assertRaises(ValueError):
            second.commit(second.data, 'second', {})

    def test_lock_blocks_overlapping_save(self):
        with m.locked(self.state/'manager.lock'):
            with self.assertRaises(ValueError):
                self.store.commit(self.store.data, 'blocked', {})

    def test_recover_after_registry_written_but_audit_failed(self):
        real_write = m.atomic_write
        def failing_write(path, raw):
            if Path(path).parent == self.store.events:
                raise OSError('simulated audit failure')
            real_write(path, raw)
        with patch.object(m, 'atomic_write', side_effect=failing_write):
            with self.assertRaises(OSError):
                self.store.commit(self.store.data, 'save', {'reference':'RECOVERY'})
        self.assertTrue((self.state/'pending.json').exists())
        reopened = m.Store(self.registry, self.state)
        self.assertEqual(len(reopened.history()), 1)
        self.assertFalse((self.state/'pending.json').exists())

    def test_recover_when_registry_write_never_happened(self):
        original = self.registry.read_bytes()
        real_write = m.atomic_write
        def failing_write(path, raw):
            if Path(path) == self.registry:
                raise OSError('simulated registry write failure')
            real_write(path, raw)
        with patch.object(m, 'atomic_write', side_effect=failing_write):
            with self.assertRaises(OSError):
                self.store.commit(self.store.data, 'save', {})
        reopened = m.Store(self.registry, self.state)
        self.assertEqual(self.registry.read_bytes(), original)
        self.assertFalse(reopened.history())

    def test_recovery_conflict_does_not_overwrite_external_data(self):
        real_write = m.atomic_write
        def failing_write(path, raw):
            if Path(path).parent == self.store.events:
                raise OSError('simulated audit failure')
            real_write(path, raw)
        with patch.object(m, 'atomic_write', side_effect=failing_write):
            with self.assertRaises(OSError):
                self.store.commit(self.store.data, 'save', {})
        external = b'{"edited":true}\n'
        self.registry.write_bytes(external)
        with self.assertRaises(ValueError):
            m.Store(self.registry, self.state)
        self.assertEqual(self.registry.read_bytes(), external)
        self.assertTrue((self.state/'pending.json').exists())

    def test_private_state_cannot_be_under_public_folder(self):
        with self.assertRaises(ValueError):
            m.Store(self.registry, self.registry.parent/'private')

    def test_cancelled_preview_writes_nothing(self):
        original = self.registry.read_bytes()
        with patch('builtins.input', return_value='NO'), redirect_stdout(io.StringIO()):
            with self.assertRaises(m.Cancelled):
                m.save_preview(self.store, self.store.data, 'save', {})
        self.assertEqual(self.registry.read_bytes(), original)
        self.assertFalse(self.store.history())

    def test_remove_recover_and_id_reservation(self):
        with patch('builtins.input', side_effect=['LIC-001','LIC-001','remove listing only','SAVE']), redirect_stdout(io.StringIO()):
            m.run_action(self.store, '8')
        self.assertFalse(self.store.data['licenses'])
        self.assertEqual(self.store.next_id(), 'LIC-002')
        with patch('builtins.input', side_effect=['LIC-001','recover listing','SAVE']), redirect_stdout(io.StringIO()):
            m.run_action(self.store, '9')
        row = self.store.data['licenses'][0]
        self.assertEqual(row['permissionState'], 'grant-recorded')
        self.assertEqual(row['registryStatus'], 'archived')

    def test_unarchive_keeps_recorded_ending(self):
        self.store.data['licenses'][0].update(permissionState='revocation-recorded',
            statusEffectiveAt='2026-05-01T00:00:00Z', statusReference='END', registryStatus='archived')
        with patch('builtins.input', side_effect=['LIC-001','listed','display record','SAVE']), redirect_stdout(io.StringIO()):
            m.run_action(self.store, '7')
        self.assertEqual(self.store.data['licenses'][0]['permissionState'], 'revocation-recorded')

    def test_interactive_extend_records_evidence(self):
        with patch('builtins.input', side_effect=['LIC-001','EXT-1','extension issued','message delivered',
                                                 '2100-01-01','SAVE']), redirect_stdout(io.StringIO()):
            m.run_action(self.store, '4')
        self.assertEqual(self.store.data['licenses'][0]['expiresAt'], '2100-01-01T00:00:00Z')
        self.assertEqual(self.store.history()[0]['evidence']['reference'], 'EXT-1')

    def test_new_grant_uses_new_id_and_preserves_previous(self):
        answers = ['', '', '', '', '', 'yes', '', '-', '2030-01-01', 'perpetual', 'yes',
                   'GRANT-2','SCOPE-2','TERMS-2','no','MESSAGE-2','grant issued','delivered','SAVE']
        before = copy.deepcopy(self.store.data['licenses'][0])
        with patch('builtins.input', side_effect=['LIC-001', *answers]), redirect_stdout(io.StringIO()):
            m.run_action(self.store, '6')
        self.assertEqual(self.store.data['licenses'][0], before)
        new = self.store.data['licenses'][1]
        self.assertEqual(new['licenseId'], 'LIC-002')
        self.assertEqual(new['revocableAtWill'], True)
        self.assertIsNone(new['expiresAt'])
        self.assertEqual(self.store.history()[0]['evidence']['relatedLicenseId'], 'LIC-001')

    def test_export_saved_bytes_and_backup_existing_mirror(self):
        target = self.root/'mirror/licenses.json'
        target.parent.mkdir()
        old = sample()
        old['licenses'][0]['gameName'] = 'Old mirror'
        target.write_bytes(m.encode(old))
        with patch('builtins.input', side_effect=[str(target),'EXPORT']), redirect_stdout(io.StringIO()):
            m.export_copy(self.store)
        self.assertEqual(target.read_bytes(), self.registry.read_bytes())
        backups = list((self.state/'exports').glob('*.json'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(m.decode(backups[0].read_bytes()), old)

    def test_read_only_cli_and_wrapper(self):
        program = Path(m.__file__)
        for argv in ([str(program), '--validate', str(self.registry)],
                     [str(program.with_name('validate_registry.py')), str(self.registry)]):
            result = subprocess.run([sys.executable, *argv], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.registry.read_bytes(), m.encode(sample()))


if __name__ == '__main__':
    unittest.main()

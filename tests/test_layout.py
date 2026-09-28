import contextlib
import io
import copy
import json
import subprocess
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch
SKILL_ROOT = Path(__file__).resolve().parents[1] / "skills" / "iphone-home-screen-layout"
sys.path.insert(0, str(SKILL_ROOT))

from iphone_layout.core import LayoutError, decode, encode, validate, classify, conserved
from iphone_layout.workflow import snapshot, check_snapshot, plan, execute, save, device_lock
from iphone_layout.adapter import Cfgutil
from iphone_layout.cli import main

RAW = [['dock.app'], ['app.a', ['旧分类', 'app.b', 'app.c'], 'https://example.com']]
RULES = {'groups': [{'name': '工作', 'ids': ['app.a', 'app.b']}]}


class FakeDevice:
    ecid = '123'

    def __init__(self, raw=RAW):
        self.raw = copy.deepcopy(raw)
        self.writes = 0
        self.fail = False
        self.ignore = False

    def read(self):
        return copy.deepcopy(self.raw)

    def write(self, raw):
        self.writes += 1
        if self.fail:
            raise LayoutError('write timed out')
        if not self.ignore:
            self.raw = copy.deepcopy(raw)


class CoreTests(unittest.TestCase):
    def test_roundtrip_formats(self):
        for raw in [RAW, [[], [['多页', ['a', 'b'], ['c']]]], [[], []]]:
            self.assertEqual(encode(decode(raw)), raw)

    def test_conservation_and_unassigned(self):
        original = decode(RAW)
        result = classify(original, RULES)
        conserved(original, result)
        self.assertEqual(original, decode(RAW))
        self.assertEqual(result['dock'], original['dock'])
        self.assertEqual(result['pages'][0][0]['pages'][0][0]['id'], 'app.c')
        self.assertEqual(result['pages'][0][1]['id'], 'https://example.com')

    def test_reject_unknown_formats(self):
        for raw in [{}, [[], [{'widget': 'x'}]], [[], [['F', 'a', ['b']]]], [[], [['empty']]], [[], ['a', 'a']]]:
            with self.subTest(raw=raw), self.assertRaises(LayoutError):
                decode(raw)

    def test_missing_or_new_ids(self):
        for ids in [['app.a'], ['app.a', 'new.app']]:
            with self.assertRaises(LayoutError):
                conserved(decode(RAW), decode([[], ids]))

    def test_invalid_assignments(self):
        for ids in [['dock.app'], ['missing'], ['app.a', 'app.a']]:
            with self.assertRaises(LayoutError):
                classify(decode(RAW), {'groups': [{'name': 'F', 'ids': ids}]})

    def test_pagination(self):
        ids = ['app.%s' % n for n in range(25)]
        source = decode([[], ids[:24], ids[24:]])
        result = classify(source, {'groups': [{'name': 'F', 'ids': ids}]})
        self.assertEqual([len(p) for p in result['pages'][-1][-1]['pages']], [9, 9, 7])
        with self.assertRaises(LayoutError):
            decode([[], ids])
        with self.assertRaises(LayoutError):
            decode([ids[:5], []])

    def test_full_last_page_spills(self):
        ids = ['app.%s' % n for n in range(25)]
        source = decode([[], [ids[0]], ids[1:]])
        result = classify(source, {'groups': [{'name': 'F', 'ids': [ids[0]]}]})
        self.assertEqual(len(result['pages']), 3)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.device = FakeDevice()
        self.source = snapshot('0x7b', RAW)
        self.proposal = plan(self.source, classify(decode(RAW), RULES))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def test_device_lock_rejects_concurrent_commit(self):
        with device_lock('123'):
            with self.assertRaisesRegex(LayoutError, 'device lock'):
                execute(self.device, self.proposal, self.temp.name, True)
        self.assertEqual(self.device.writes, 0)

    def test_cli_requires_preview_digest(self):
        path = Path(self.temp.name) / 'proposal.json'
        save(path, self.proposal)
        with patch('iphone_layout.cli.Cfgutil', return_value=self.device), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['apply', str(path), '--ecid', '123', '--commit']), 2)
        self.assertEqual(self.device.writes, 0)

    def test_preview_never_writes(self):
        result = execute(self.device, self.proposal, self.temp.name)
        self.assertFalse(result['committed'])
        self.assertEqual(self.device.writes, 0)
        self.assertFalse(list(Path(self.temp.name).iterdir()))

    def test_apply_restore(self):
        result = execute(self.device, self.proposal, self.temp.name, True)
        self.assertTrue(result['committed'])
        backup = json.loads(Path(result['backup']).read_text())
        self.assertEqual(backup['raw'], RAW)
        self.assertEqual(Path(result['backup']).stat().st_mode & 0o777, 0o600)
        restored = execute(self.device, backup, self.temp.name, True, True)
        self.assertTrue(restored['committed'])
        self.assertEqual(self.device.raw, RAW)
        self.assertEqual(len(list(Path(self.temp.name).glob('*.json'))), 2)

    def test_restore_preserves_raw_folder_encoding(self):
        # A one-page folder may use the paged encoding; restore must preserve it.
        raw = [['dock.app'], ['app.a', ['旧分类', ['app.b', 'app.c']], 'https://example.com']]
        backup = snapshot('123', raw)
        self.device.raw = encode(self.proposal['target'])
        execute(self.device, backup, self.temp.name, True, True)
        self.assertEqual(self.device.raw, raw)

    def test_stale_or_wrong_device(self):
        for field, value in [('base_sha256', 'bad'), ('ecid', '999')]:
            proposal = dict(self.proposal, **{field: value})
            with self.assertRaises(LayoutError):
                execute(self.device, proposal, self.temp.name, True)
        self.assertEqual(self.device.writes, 0)

    def test_corrupt_backup(self):
        self.source['raw'][1].append('new')
        with self.assertRaises(LayoutError):
            check_snapshot(self.source)

    def test_restore_reject_inventory_changes(self):
        self.device.raw[1].append('new')
        with self.assertRaises(LayoutError):
            execute(self.device, self.source, self.temp.name, True, True)
        self.assertEqual(self.device.writes, 0)

    def test_backup_failure_prevents_write(self):
        with patch('iphone_layout.workflow.save', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                execute(self.device, self.proposal, self.temp.name, True)
        self.assertEqual(self.device.writes, 0)

    def test_write_failure_and_mismatch_keep_backup(self):
        for attribute in ['fail', 'ignore']:
            device = FakeDevice()
            setattr(device, attribute, True)
            with self.assertRaisesRegex(LayoutError, 'backup:'):
                execute(device, self.proposal, self.temp.name, True)
            self.assertEqual(device.writes, 1)
        self.assertEqual(len(list(Path(self.temp.name).glob('*.json'))), 2)

    def test_change_before_write(self):
        with patch.object(self.device, 'read', side_effect=[RAW, [[], ['new']]]):
            with self.assertRaisesRegex(LayoutError, 'changed before write'):
                execute(self.device, self.proposal, self.temp.name, True)
        self.assertEqual(self.device.writes, 0)

    def test_exclusive_save(self):
        path = Path(self.temp.name) / 'snapshot.json'
        save(path, self.source)
        with self.assertRaises(FileExistsError):
            save(path, {})
        self.assertEqual(json.loads(path.read_text()), self.source)

    def test_cli_offline(self):
        root = SKILL_ROOT
        source = str(Path(self.temp.name) / 'current.json')
        proposal = str(Path(self.temp.name) / 'plan.json')
        self.assertEqual(main(['import', str(root/'examples/raw-layout.json'), '--ecid', '123', '--out', source]), 0)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['plan', source, str(root/'examples/categories.json'), '--out', proposal]), 0)
        self.assertIn('target', json.loads(Path(proposal).read_text()))


class AdapterTests(unittest.TestCase):
    @patch('iphone_layout.adapter.platform.system', return_value='Darwin')
    def test_exact_arguments(self, _):
        with patch('iphone_layout.adapter.subprocess.run', return_value=subprocess.CompletedProcess([], 0, json.dumps(RAW), '')) as run:
            adapter = Cfgutil('0x7b', '/path with spaces/cfgutil')
            self.assertEqual(adapter.read(), RAW)
            self.assertEqual(run.call_args.args[0], ['/path with spaces/cfgutil', '--ecid', '0x7b', 'get-icon-layout'])
            adapter.write(RAW)
            self.assertEqual(run.call_args.args[0][3], 'set-icon-layout')
            self.assertNotIn('--force', run.call_args.args[0])

    @patch('iphone_layout.adapter.platform.system', return_value='Darwin')
    def test_errors(self, _):
        adapter = Cfgutil('123')
        for effect in [subprocess.TimeoutExpired('cfgutil', 60), OSError('not found')]:
            with patch('iphone_layout.adapter.subprocess.run', side_effect=effect), self.assertRaises(LayoutError):
                adapter.read()
        for code, stdout in [(134, ''), (0, 'garbage'), (0, '{"Output": {}}')]:
            with patch('iphone_layout.adapter.subprocess.run', return_value=subprocess.CompletedProcess([], code, stdout, 'error')), self.assertRaises(LayoutError):
                adapter.read()

    @patch('iphone_layout.adapter.platform.system', return_value='Windows')
    def test_no_windows_adapter(self, _):
        with self.assertRaises(LayoutError):
            Cfgutil('123')


if __name__ == '__main__':
    unittest.main()

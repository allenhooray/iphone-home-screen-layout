"""Snapshots, plans and recoverable device mutations."""
import copy
import contextlib
import tempfile
import datetime
import json
import os
import uuid
from pathlib import Path
from .core import require, ecid, decode, encode, digest, conserved, preview, LayoutError


def save(path, value):
    """Exclusive creation prevents accidental overwrite; fsync before writing device."""
    path = Path(path)
    with os.fdopen(os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def snapshot(device, raw):
    return {'version': 1, 'ecid': ecid(device), 'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'raw': copy.deepcopy(raw), 'layout': decode(raw), 'raw_sha256': digest(raw)}


def check_snapshot(value):
    require(isinstance(value, dict) and value.get('version') == 1, 'Invalid snapshot')
    require(value.get('raw_sha256') == digest(value.get('raw')), 'Backup checksum mismatch')
    require(decode(value['raw']) == value.get('layout'), 'Snapshot raw/layout mismatch')
    ecid(value['ecid'])
    return value


def plan(source, target):
    check_snapshot(source)
    conserved(source['layout'], target)
    return {'version': 1, 'ecid': source['ecid'], 'base_sha256': digest(source['layout']), 'target': target}


@contextlib.contextmanager
def device_lock(device):
    # Stable path independent of cwd/backup directory; lock auto-releases on exit.
    import fcntl
    path = Path(tempfile.gettempdir()) / ('iphone-layout-%s-%s.lock' % (os.getuid(), ecid(device)))
    descriptor = os.open(str(path), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LayoutError('Another layout operation holds this device lock') from exc
        yield
    finally:
        os.close(descriptor)


def execute(adapter, proposal, backup_dir, commit=False, restore=False):
    if commit:
        with device_lock(adapter.ecid):
            return _execute(adapter, proposal, backup_dir, commit, restore)
    return _execute(adapter, proposal, backup_dir, commit, restore)


def _execute(adapter, proposal, backup_dir, commit=False, restore=False):
    require(isinstance(proposal, dict) and proposal.get('version') == 1, 'Invalid plan/backup version')
    require(ecid(proposal['ecid']) == adapter.ecid, 'Device ECID mismatch')
    if restore:
        check_snapshot(proposal)
        target, raw_target = proposal['layout'], proposal['raw']
    else:
        target = proposal['target']
        raw_target = encode(target)
    raw = adapter.read()
    current = decode(raw)
    if not restore:
        require(digest(current) == proposal['base_sha256'], 'Stale plan: re-read and re-plan')
    conserved(current, target)
    result = {'diff': preview(current, target), 'plan_sha256': digest(proposal), 'committed': False}
    if not commit or current == target:
        return result
    directory = Path(backup_dir)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup = directory / (uuid.uuid4().hex + '.json')
    save(backup, snapshot(adapter.ecid, raw))
    result['backup'] = str(backup.resolve())
    try:
        # Detect edits during backup preparation. cfgutil offers no atomic compare-and-set.
        require(decode(adapter.read()) == current, 'Device changed before write; re-plan')
        adapter.write(raw_target)
        actual = decode(adapter.read())
        require(actual == target, 'Read-back differs from requested layout')
    except (LayoutError, OSError) as exc:
        raise LayoutError('%s; backup: %s; no automatic retry or rollback' % (exc, backup.resolve())) from exc
    result['committed'] = True
    return result

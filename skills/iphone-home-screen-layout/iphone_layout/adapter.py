"""macOS cfgutil boundary: one explicit ECID, bounded calls, no shell."""
import json
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from .core import LayoutError, ecid, decode, encode


class Cfgutil:
    def __init__(self, device, executable=None, timeout=60):
        if platform.system() != 'Darwin':
            raise LayoutError('Device operations require macOS')
        self.ecid = ecid(device)
        self.executable = executable or shutil.which('cfgutil') or '/Applications/Apple Configurator.app/Contents/MacOS/cfgutil'
        self.timeout = timeout

    def run(self, *args):
        try:
            result = subprocess.run([self.executable, '--ecid', hex(int(self.ecid)), *args],
                                    capture_output=True, text=True, timeout=self.timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise LayoutError('cfgutil failed or timed out; device state may be uncertain: ' + str(exc)) from exc
        if result.returncode:
            raise LayoutError('cfgutil exit %s: %s' % (result.returncode, result.stderr.strip()))
        return result.stdout

    def read(self):
        try:
            raw = json.loads(self.run('get-icon-layout'))
        except json.JSONDecodeError as exc:
            raise LayoutError('cfgutil returned invalid JSON') from exc
        decode(raw)
        return raw

    def write(self, raw):
        decode(raw)
        with tempfile.TemporaryDirectory(prefix='iphone-layout-') as directory:
            path = Path(directory) / 'layout.json'
            path.write_text(json.dumps(raw, ensure_ascii=False), encoding='utf-8')
            path.chmod(0o600)
            self.run('set-icon-layout', str(path))

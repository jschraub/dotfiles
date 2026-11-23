"""Build the branch-selector PAM module; no authentication is executed here."""
from pathlib import Path
import subprocess
import tempfile


def build(source):
    with tempfile.TemporaryDirectory(prefix='atelier-pam-build-') as directory:
        output = Path(directory) / 'pam_atelier_method.so'
        subprocess.run(['/usr/bin/cc', '-std=c11', '-O2', '-D_FORTIFY_SOURCE=2',
                        '-fPIC', '-shared', '-fstack-protector-strong', '-Wall', '-Wextra', '-Werror',
                        '-Wl,-z,relro,-z,now', '-o', str(output), str(source), '-lpam'],
                       env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}, check=True)
        return output.read_bytes()

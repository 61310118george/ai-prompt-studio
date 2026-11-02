"""Compare .NET loading of an ordinary and internet-marked bundled assembly."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pythonnet

source = Path(pythonnet.__file__).parent / 'runtime' / 'Python.Runtime.dll'
probe = "from clr_loader import get_netfx; import sys; r=get_netfx(); r.get_assembly(sys.argv[1]).get_function('Python.Runtime.Loader.Initialize')"
with tempfile.TemporaryDirectory(prefix='prompt-dll-zone-') as folder:
    target = Path(folder) / 'Python.Runtime.dll'
    shutil.copy2(source, target)
    clean = subprocess.run([sys.executable, '-c', probe, str(target)], capture_output=True, text=True)
    Path(str(target) + ':Zone.Identifier').write_text('[ZoneTransfer]\r\nZoneId=3\r\n', encoding='ascii')
    marked = subprocess.run([sys.executable, '-c', probe, str(target)], capture_output=True, text=True)
    print(json.dumps({'clean_exit': clean.returncode, 'internet_marked_exit': marked.returncode,
                      'same_loader_error': 'Failed to resolve Python.Runtime.Loader.Initialize' in marked.stderr}))
    if clean.returncode:
        raise RuntimeError(clean.stderr)

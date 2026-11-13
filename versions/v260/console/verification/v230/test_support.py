"""Use the shipped firmware archive, or the explicit local build directory."""
import os
from pathlib import Path
import tarfile
import tempfile

PC = Path(__file__).resolve().parents[2]
_work = None
if os.environ.get('MICRODUCK_FIRMWARE_ROOT'):
    FW = Path(os.environ['MICRODUCK_FIRMWARE_ROOT']).resolve()
else:
    _work = tempfile.TemporaryDirectory(prefix='v230-firmware-tests-')
    with tarfile.open(PC / 'updates/Microduck-Robotd-FT6-R17.tar.gz') as archive:
        archive.extractall(_work.name, filter='data')
    FW = Path(_work.name) / 'Microduck-Robotd-FT6-R17'

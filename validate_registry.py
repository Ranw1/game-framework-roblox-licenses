"""Read-only registry validator. Keep license_manager.py in the same folder."""
import sys
from license_manager import main

if __name__ == '__main__':
    raise SystemExit(main(['--validate', *(sys.argv[1:] or ['licenses.json'])]))

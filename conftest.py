import sys
from pathlib import Path

ROOT = Path(__file__).parent

# Glob instead of listing so deleting a service never breaks test discovery.
for path in [ROOT / "libs", *ROOT.glob("services/*/src")]:
    sys.path.insert(0, str(path))

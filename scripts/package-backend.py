import sys
import zipfile
from pathlib import Path

root, output = map(Path, sys.argv[1:3])
with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted((root / "app").rglob("*.py")):
        archive.write(path, path.relative_to(root).as_posix())
    for filename in ("requirements.txt", "startup.sh"):
        archive.write(root / filename, filename)
print(f"Packaged backend: {output}")

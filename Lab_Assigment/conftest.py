"""
conftest.py — Add 06-lab-complete parent to sys.path so that
`import Lab_Assigment` resolves to the 06-lab-complete package.

pytest auto-discovers this file and executes it before any test.
"""
import sys
from pathlib import Path

# The repo root (2A202600890_PhanQuocAnh_Day12) is the parent of this conftest.
# Adding it to sys.path makes "Lab_Assigment" resolve to the 06-lab-complete folder
# via the Lab_Assigment.pth file or because we rename the package.
REPO_ROOT = Path(__file__).resolve().parent.parent
LAB_PARENT = Path(__file__).resolve().parent  # e.g. …/06-lab-complete

# Allow `import Lab_Assigment.xxx` to resolve from the parent directory
# (where 06-lab-complete lives as Lab_Assigment via symlink/alias created below)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

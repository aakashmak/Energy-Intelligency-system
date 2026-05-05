# conftest.py — shared pytest configuration
import sys
from pathlib import Path

# Ensure project root is on the path so `src.*` imports resolve
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

"""Use the shared two-source physical-adjacency builder without touching J0/JT0."""
from pathlib import Path
import runpy


runpy.run_path(str(Path(__file__).parents[1] / "local_phase_coupling_physical/build.py"), run_name="__main__")

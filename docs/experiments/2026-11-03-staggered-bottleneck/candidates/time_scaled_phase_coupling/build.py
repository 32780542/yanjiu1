"""JT shares the small J builder; the sole increment is its phase scale."""
from pathlib import Path
import runpy


runpy.run_path(str(Path(__file__).parents[1] / "local_phase_coupling/build.py"), run_name="__main__")

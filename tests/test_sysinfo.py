"""A missing sensor or damaged cache must not break eww's JSON contract."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile

spec = importlib.util.spec_from_file_location("sysinfo", Path(__file__).resolve().parents[1] / "scripts/sysinfo.py")
sysinfo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sysinfo)


class CollectorTests(unittest.TestCase):
    def test_corrupt_cpu_cache_is_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "cpu-prev.json").write_text("broken")
            (root / "stat").write_text("cpu0 10 0 10 100 0 0 0\n")
            with patch.object(sysinfo, "PROC_ROOT", root), patch.object(sysinfo, "CACHE_ROOT", root):
                values, _ = sysinfo.cpu_percentages(cores=1)
            self.assertEqual(values, [0])
            self.assertIn("cpu0", json.loads((root / "cpu-prev.json").read_text()))

    def test_missing_metrics_still_emit_complete_json(self):
        with patch.object(sysinfo, "memory_info", side_effect=OSError("missing")), \
                patch.object(sysinfo, "cpu_percentages", side_effect=OSError("missing")), \
                patch.object(sysinfo, "top_processes", return_value=[]):
            data = sysinfo.collect()
        self.assertEqual(len(data["cpu"]), 8)
        self.assertEqual(len(data["top_cpu"]), 5)
        self.assertEqual(len(data["top_ram"]), 5)
        self.assertIn("gpu_available", data)
        json.dumps(data, allow_nan=False)


if __name__ == "__main__":
    unittest.main()

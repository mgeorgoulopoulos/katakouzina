import tempfile
import unittest
from pathlib import Path
from katakouzina.graph import load_edges
from katakouzina.editing import save_reason

class EditingTests(unittest.TestCase):
    def test_save_preserves_other_fields_and_backup(self):
        original=(Path(__file__).resolve().parents[1]/'example-data/demo/edges.tsv').read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'edges.tsv';path.write_bytes(original)
            before=load_edges(path);row=before[0]
            save_reason(path,row,'Edited explanation\nSecond line')
            after=load_edges(path)
            self.assertEqual(after[1:],before[1:])
            self.assertEqual(after[0],dict(row,reason='Edited explanation\nSecond line'))
            self.assertEqual(next((path.parent/'.history').iterdir()).read_bytes(),original)
            with self.assertRaises(ValueError):save_reason(path,row,'Stale edit')
            self.assertEqual(load_edges(path),after)

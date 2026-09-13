import tempfile
import unittest
from pathlib import Path
from katakouzina.special_nodes import load_special_nodes

class SpecialNodeTests(unittest.TestCase):
    def test_optional_file_and_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.assertEqual(load_special_nodes(root),{})
            p=root/'special_nodes.json';p.write_text('{"Moon":"#dc2626"}')
            self.assertEqual(load_special_nodes(root),{'Moon':'#dc2626'})
            p.write_text('{"Moon":"invalid"}')
            with self.assertRaises(ValueError):load_special_nodes(root)

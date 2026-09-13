import json
import tempfile
import unittest
from pathlib import Path
from katakouzina.config import load_config,DEFAULTS,read_settings,save_preferences

class ConfigTests(unittest.TestCase):
    def test_defaults_preservation_and_path_resolution(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.assertEqual(load_config(root,create=False),(root/'example-data').resolve());self.assertFalse((root/'config.json').exists())
            self.assertEqual(load_config(root),(root/'example-data').resolve())
            self.assertEqual(json.loads((root/'config.json').read_text()),DEFAULTS)
            (root/'config.json').write_text('{"data_path":"fixtures"}')
            self.assertEqual(load_config(root),(root/'fixtures').resolve())
            (root/'config.json').write_text(json.dumps({'data_path':str(root/'absolute')}))
            self.assertEqual(load_config(root),(root/'absolute').resolve())
            (root/'config.json').write_text('{"data_path":23}')
            with self.assertRaises(ValueError):load_config(root)

    def test_preferences_preserve_data_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            load_config(root)
            save_preferences(root,{'hide_leaves':True,'graph_font_size':22})
            self.assertEqual(json.loads((root/'config.json').read_text())['data_path'],'example-data')
            self.assertTrue(read_settings(root)['hide_leaves'])
            (root/'config.json').write_text('{"data_path":"fixtures","custom":123}')
            save_preferences(root,{'show_rejected_edges':True})
            settings=read_settings(root)
            self.assertEqual(settings['data_path'],'fixtures')
            self.assertEqual(settings['custom'],123)

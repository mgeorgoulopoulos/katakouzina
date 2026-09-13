import tempfile
import unittest
from pathlib import Path
from katakouzina.positions import PositionStore

class PositionTests(unittest.TestCase):
    def test_roundtrip_and_view_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            store=PositionStore(Path(folder)/'edges.tsv')
            points={'Node Alpha':(12.5,-7),'Node Beta':(100,300)}
            store.save('whole',points);store.save('focus',{'Node Alpha':(1,2)})
            other=PositionStore(Path(folder)/'edges.tsv')
            self.assertEqual(other.load('whole',points),points)
            self.assertEqual(other.load('focus',['Node Alpha']),{'Node Alpha':(1,2)})
            self.assertIsNone(other.load('whole',['new node']))

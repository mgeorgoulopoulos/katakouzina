import tempfile
import unittest
from pathlib import Path
from katakouzina.deletions import DeletionStore
from katakouzina.review import ReviewStore

class DeletionTests(unittest.TestCase):
    def test_delete_restore_history_and_review_independence(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'edges.tsv';path.write_text('untouched')
            review=ReviewStore(path);row={'edge_id':'a'};review.set_rejected(row,'Human reason')
            before=review.path.read_bytes()
            store=DeletionStore(path);store.set('edges','a');store.set('nodes','Example')
            self.assertEqual(DeletionStore(path).active(),({'Example'},{'a'}))
            store.set('edges','a',False)
            self.assertEqual(store.active(),({'Example'},set()))
            self.assertEqual(len(store.read()['edges']['a']['history']),2)
            self.assertEqual(review.path.read_bytes(),before)
            self.assertEqual(path.read_text(),'untouched')

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from katakouzina.review import ReviewStore

class ReviewTests(unittest.TestCase):
    def test_persistence_uncheck_and_changed_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            graph=Path(folder)/'edges.tsv';graph.write_text('original',encoding='utf-8')
            row={'edge_id':'one','evidence':'original evidence'}
            store=ReviewStore(graph)
            self.assertFalse(store.verified(row))
            self.assertFalse(store.path.exists())
            store.set_verified(row,True)
            self.assertTrue(ReviewStore(graph).verified(row))
            self.assertFalse(store.verified(dict(row,evidence='changed')))
            store.set_verified(row,False)
            self.assertFalse(ReviewStore(graph).verified(row))
            self.assertEqual(graph.read_text(), 'original')

    def test_separate_graphs_and_preserve_other_reviews(self):
        with tempfile.TemporaryDirectory() as folder:
            first=ReviewStore(Path(folder)/'first.tsv');other=Path(folder)/'other';other.mkdir();second=ReviewStore(other/'edges.tsv')
            a={'edge_id':'a'};b={'edge_id':'b'}
            first.set_verified(a,True);first.set_verified(b,True);first.set_verified(a,False)
            self.assertTrue(first.verified(b));self.assertFalse(second.verified(b))

    def test_failed_save_does_not_verify(self):
        with tempfile.TemporaryDirectory() as folder:
            store=ReviewStore(Path(folder)/'edges.tsv');row={'edge_id':'a'}
            with patch('katakouzina.review.os.replace',side_effect=OSError('denied')):
                with self.assertRaises(OSError):store.set_verified(row,True)
            self.assertFalse(store.verified(row))

    def test_rejection_restore_and_mutual_exclusion(self):
        from katakouzina.graph import project
        with tempfile.TemporaryDirectory() as folder:
            store=ReviewStore(Path(folder)/'edges.tsv')
            row={'edge_id':'a','from':'one','to':'two','status':'CONFIRMED','layer':'LEXICAL'}
            store.set_rejected(row,'')
            self.assertEqual(store.rejections(),{'a':''})
            store.set_verified(row,True)
            store.set_rejected(row,'Unsupported by dialogue')
            self.assertFalse(store.verified(row))
            self.assertEqual(ReviewStore(store.graph_path).rejections(),{'a':'Unsupported by dialogue'})
            graph=project([row],status='ALL',rejected_ids=store.rejections())
            self.assertEqual(graph.number_of_edges(),0)
            self.assertEqual(set(graph),{'one','two'})
            store.set_rejected(row,None)
            self.assertEqual(project([row],rejected_ids=store.rejections()).number_of_edges(),1)
            self.assertFalse(store.verified(row))
            store.set_rejected(row,'Still unsupported')
            store.set_verified(row,True)
            self.assertEqual(store.rejections(),{})
            self.assertTrue(store.verified(row))

    def test_rejected_visibility_and_review_colors(self):
        from katakouzina.graph import project
        from katakouzina.theme import edge_color,RED,GREEN,BLUE
        row={'edge_id':'a','from':'one','to':'two','status':'REJECTED','layer':'LEXICAL'}
        self.assertEqual(project([row],rejected_ids={'a'}).number_of_edges(),0)
        self.assertEqual(project([row],rejected_ids={'a'},show_rejected=True).number_of_edges(),1)
        self.assertEqual(project([row],layer='NARRATIVE',rejected_ids={'a'},show_rejected=True).number_of_edges(),0)
        self.assertEqual(edge_color(row,set(),{'a'}),RED)
        self.assertEqual(edge_color(row,{'a'},set()),GREEN)
        self.assertEqual(edge_color(row,set(),set()),BLUE)

    def test_checkbox_applies_rejection_immediately(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from katakouzina.inspector import Inspector
        with tempfile.TemporaryDirectory() as folder:
            store=ReviewStore(Path(folder)/'edges.tsv');row={'edge_id':'a'}
            ui=SimpleNamespace(inspected_edge=row,human_rejected=Mock(),review_store=store,rejected_reasons={},verified_ids={'a'},refresh_review_graph=Mock())
            ui.human_rejected.get.return_value=True
            Inspector.toggle_rejected(ui)
            self.assertEqual(store.rejections(),{'a':''})
            self.assertEqual(ui.rejected_reasons,store.rejections())
            self.assertNotIn('a',ui.verified_ids)
            ui.refresh_review_graph.assert_called_once_with(row)
            store.set_rejected(row,'Reason added later')
            self.assertEqual(store.rejections(),{'a':'Reason added later'})

    def test_explanations_restore_and_ai_cannot_verify(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            store=ReviewStore(Path(folder)/'edges.tsv');row={'edge_id':'a','reason':'Original'}
            store.save(row,'Exact\nexplanation')
            store.set_rejected(row,'Rejected reason')
            self.assertEqual(store.reason(row),'Rejected reason')
            store.set_rejected(row,None)
            self.assertEqual(store.reason(row),'Exact\nexplanation')
            store.set_verified(row,True)
            values=store.records();values['a']['author']='ai'
            store.path.write_text(json.dumps(values),encoding='utf-8')
            self.assertFalse(store.verified(row))
            self.assertTrue(store.stale(dict(row,reason='Changed')))

    def test_save_failure_releases_lock_and_preserves_content(self):
        with tempfile.TemporaryDirectory() as folder:
            store=ReviewStore(Path(folder)/'edges.tsv');row={'edge_id':'a'}
            store.save(row,'Before');before=store.path.read_bytes()
            with patch('katakouzina.review.os.replace',side_effect=OSError('denied')):
                with self.assertRaises(OSError):store.save(row,'After')
            self.assertEqual(store.path.read_bytes(),before)
            self.assertFalse(store.path.with_suffix('.json.lock').exists())
            store.save(row,'Retry')
            self.assertEqual(store.reason(row),'Retry')

    def test_interleaved_stores_preserve_other_edges_and_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'edges.tsv';first=ReviewStore(path);second=ReviewStore(path)
            first.save({'edge_id':'a'},'A');second.save({'edge_id':'b'},'B')
            self.assertEqual(set(first.records()),{'a','b'})
            lock=first.path.with_suffix('.json.lock');lock.write_text('')
            with self.assertRaises(FileExistsError):first.save({'edge_id':'a'},'Changed')
            self.assertEqual(first.reason({'edge_id':'a'}),'A')

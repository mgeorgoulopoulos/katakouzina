import csv
from pathlib import Path
import tempfile
import unittest
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from katakouzina.graph import discover,load_edges,project,layout

class GraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rows=load_edges(ROOT/'example-data/demo/edges.tsv')
    def test_canonical_projections(self):
        self.assertEqual(len(self.rows),2)
        self.assertEqual(project(self.rows).number_of_edges(),2)
        self.assertEqual(project(self.rows,layer='LEXICAL').number_of_edges(),0)
        self.assertEqual(project(self.rows,status='HYPOTHESIS').number_of_edges(),0)
        self.assertEqual(project(self.rows,status='ALL').number_of_edges(),2)
    def test_ai_rejection_is_visible_until_human_rejects(self):
        row=dict(self.rows[0],status='REJECTED')
        self.assertEqual(project([row]).number_of_edges(),1)
        self.assertEqual(project([row],rejected_ids={row['edge_id']}).number_of_edges(),0)
        self.assertEqual(project([row],rejected_ids={row['edge_id']},show_rejected=True).number_of_edges(),1)

    def test_demo_nodes(self):
        self.assertEqual(set(project(self.rows)),{'Moon','Telescope','Notebook'})
    def test_layout_is_finite_and_repeatable(self):
        import math
        g=project(self.rows);a=layout(g);b=layout(g)
        self.assertEqual(a,b);self.assertEqual(set(a),set(g))
        self.assertTrue(all(math.isfinite(v) for xy in a.values() for v in xy))
        self.assertEqual(layout(project([],status='ALL')), {})
    def test_focus_and_global_leaves(self):
        def edge(a,b):return {'from':a,'to':b,'status':'CONFIRMED','layer':'LEXICAL'}
        rows=[edge('a','b'),edge('b','c'),edge('c','d'),edge('d','e')]
        g=project(rows,focus='b',hide_leaves=True)
        self.assertEqual(set(g),{'b','c','d'}) # d is a local leaf but not a global leaf
        with self.assertRaises(ValueError):project(rows,focus='missing')
    def test_discovery_new_episode_and_empty_root(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.assertEqual(discover(p),{})
            (p/'2x01').mkdir();(p/'2x01/edges.tsv').touch()
            self.assertEqual(list(discover(p)),['2x01'])
    def test_bad_input_and_duplicate_pair(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.tsv';p.write_text('from\tto\na\tb\n',encoding='utf-8')
            with self.assertRaises(ValueError):load_edges(p)
            rows=[self.rows[0],dict(self.rows[0],edge_id='different')]
            with p.open('w',encoding='utf-8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t');w.writeheader();w.writerows(rows)
            with self.assertRaises(ValueError):load_edges(p)
    def test_read_only(self):
        import hashlib
        p=ROOT/'example-data/demo/edges.tsv';before=hashlib.sha256(p.read_bytes()).hexdigest()
        layout(project(load_edges(p)))
        self.assertEqual(before,hashlib.sha256(p.read_bytes()).hexdigest())

if __name__=='__main__':unittest.main()

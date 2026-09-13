import csv
import json
import tempfile
import unittest
from pathlib import Path
from katakouzina.evidence import EvidenceLibrary,references
from katakouzina.graph import load_edges

class EvidenceTests(unittest.TestCase):
    def test_local_priority_renumbering_overlap_and_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'srt').mkdir(parents=True)
            ref={'episode':'demo','start':'00:00:02,000','end':'00:00:03,000'}
            library=EvidenceLibrary(root)
            self.assertEqual(library.resolve(ref),[])
            (root/'srt/demo.srt').write_text('999\n00:00:01,500 --> 00:00:02,500\nThe invented telescope is ready.\n\n1005\n00:00:02,500 --> 00:00:04,000\nLet us inspect the imaginary moon.\n',encoding='utf-8')
            library=EvidenceLibrary(root);rows=library.resolve(ref)
            self.assertEqual(len(rows),2)
            self.assertTrue(all(r['kind']=='LOCAL_SRT' for r in rows))
            boundary=dict(ref,start='00:00:04,000',end='00:00:05,000')
            self.assertEqual(library.resolve(boundary),[])
            self.assertEqual(library.resolve(dict(ref,start='00:00:08,000',end='00:00:09,000')),[])
    def test_invalid_reference_and_source_text_rejected(self):
        for ref in ({'episode':'../x','start':'00:00:01,000','end':'00:00:02,000'},{'episode':'x','start':'00:00:02,000','end':'00:00:01,000'},{'episode':'x','start':'00:00:01,000','end':'00:00:02,000','text':'forbidden'}):
            with self.assertRaises(ValueError):references({'evidence_refs':json.dumps([ref])})
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'graph.tsv';p.write_text('edge_id\tevidence\na\tdialogue\n')
            with self.assertRaises(ValueError):load_edges(p)
    def test_all_public_references_are_valid_without_text(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            import shutil
            public=Path(folder)
            library=EvidenceLibrary(public)
            count=0
            for row in load_edges(root/'example-data/demo/edges.tsv'):
                for ref in references(row):
                    self.assertEqual(library.resolve(ref),[]);self.assertEqual(library.preview(ref),('',''));count+=1
            self.assertEqual(count,2)

    def test_bundled_synthetic_subtitles_and_missing_directory(self):
        import shutil
        root=Path(__file__).resolve().parents[1]/'example-data'
        row=load_edges(root/'demo/edges.tsv')[0]
        ref=references(row)[0]
        self.assertTrue(EvidenceLibrary(root).resolve(ref)[0]['text'].startswith('[SYNTHETIC]'))
        with tempfile.TemporaryDirectory() as folder:
            clone=Path(folder);shutil.copytree(root/'demo',clone/'demo')
            self.assertEqual(EvidenceLibrary(clone).resolve(ref),[])

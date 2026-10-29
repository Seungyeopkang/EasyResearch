"""Local search must reach body hits beyond the first 200 results."""
import os
import sys
import tempfile
import tracemalloc
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import library_management, storage
from app.main import app


class LocalSearchPagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'EASYRESEARCH_DATA_DIR': self.temp.name})
        self.env.start()
        self.client = TestClient(app)
        self.client.__enter__()
        with storage.transaction() as con:
            con.executemany('INSERT INTO projects(id,name) VALUES(?,?)', [('a', 'A'), ('b', 'B')])
            con.execute("INSERT INTO papers(id,title,page_count) VALUES('p','Paper',1)")
            con.execute("INSERT INTO project_papers(project_id,paper_id) VALUES('a','p')")
            con.executemany("INSERT INTO evidence(id,paper_id,page_index,quote) VALUES(?,'p',0,'unique-term')",
                            [(f'e{i:03}',) for i in range(205)])
            con.execute("INSERT INTO pages(paper_id,page_index,text,status) VALUES('p',0,'unique-term page body','extracted')")

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    def test_body_hit_after_first_page_and_scope(self):
        first = self.client.get('/api/projects/a/library-search', params={'q': 'unique-term'}).json()
        self.assertEqual((len(first['results']), first['offset'], first['limit'], first['total'], first['next_offset']),
                         (200, 0, 200, 206, 200))
        self.assertTrue(first['truncated'])
        self.assertTrue(all(item['kind'] == 'evidence' for item in first['results']))
        last = self.client.get('/api/projects/a/library-search', params={'q': 'unique-term', 'offset': 200}).json()
        self.assertEqual((len(last['results']), last['offset'], last['total'], last['next_offset']), (6, 200, 206, None))
        self.assertFalse(last['truncated'])
        self.assertEqual(last['results'][-1]['kind'], 'page')
        self.assertEqual(last['results'][-1]['page_index'], 0)
        other = self.client.get('/api/projects/b/library-search', params={'q': 'unique-term'}).json()
        self.assertEqual((other['total'], other['results'], other['next_offset']), (0, [], None))

    def test_invalid_offsets_and_limits_are_rejected(self):
        for params in ({'offset': -1}, {'limit': 0}, {'limit': 201}):
            self.assertEqual(self.client.get('/api/projects/a/library-search', params={'q': 'unique-term', **params}).status_code, 422)
        self.assertEqual(self.client.get('/api/projects/a/library-search', params={'q': 'unique-term', 'offset': 999}).json()['results'], [])

    def test_large_result_set_does_not_retain_every_snippet(self):
        with storage.transaction() as con:
            con.executemany("INSERT INTO evidence(id,paper_id,page_index,quote) VALUES(?,'p',0,?)",
                            ((f'bulk{i:05}', 'unique-term ' + 'x' * 9500) for i in range(4000)))
        tracemalloc.start()
        try:
            result = library_management.library_search('a', 'unique-term', offset=1000, limit=3)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual((result['total'], len(result['results']), result['next_offset']), (4206, 3, 1003))
        # The SQLite C cache is outside this measurement; it checks that Python
        # does not retain the roughly 38 MB of all matching text or snippets.
        self.assertLess(peak, 8 * 1024 * 1024)


"""Conservative duplicate suggestions; no network or user database."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import library_management, storage
from app.main import app


class DuplicateCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'EASYRESEARCH_DATA_DIR': self.temp.name})
        self.env.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.title = 'A survey of deep learning methods for scientific document analysis'
        self.insert('base', self.title, ['Jane Doe'], 2024, '10.1234/x')

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    def insert(self, ident, title, authors, year, doi=None):
        with storage.transaction() as con:
            con.execute('INSERT INTO papers(id,title,authors,year,doi) VALUES(?,?,?,?,?)',
                        (ident, title, json.dumps(authors), year, doi))

    def results(self):
        response = self.client.get('/api/papers/base/duplicate-candidates')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_exact_title_and_doi_and_conservative_similar_title(self):
        self.insert('title', self.title.upper(), [], 1980)
        self.insert('doi', 'Completely different title', [], None, '10.1234/X')
        self.insert('near', self.title.replace('document', 'documents'), ['Jane Doe'], 2025)
        data = self.results()
        items = {x['id']: x for x in data['candidates']}
        self.assertEqual(set(items), {'title', 'doi', 'near'})
        self.assertEqual(items['title']['reasons'], ['title'])
        self.assertEqual(items['doi']['reasons'], ['doi'])
        self.assertEqual(items['near']['reasons'], ['similar_title', 'shared_author', 'year_close'])
        self.assertIn('후보', data['notice'])
        self.assertIn('병합하지', data['notice'])
        with storage.transaction() as con:
            self.assertEqual(con.execute('SELECT count(*) FROM papers').fetchone()[0], 4)

    def test_different_research_term_author_year_and_short_titles_are_not_fuzzy_matches(self):
        self.insert('term', self.title.replace('scientific', 'clinical'), ['Jane Doe'], 2024)
        self.insert('author', self.title.replace('document', 'documents'), ['Other Author'], 2024)
        self.insert('year', self.title.replace('document', 'documents'), ['Jane Doe'], 2021)
        self.insert('short', 'short title', ['Jane Doe'], 2024)
        self.assertEqual(self.results()['candidates'], [])

    def test_missing_year_is_disclosed_and_no_fuzzy_without_author(self):
        self.insert('unknown', self.title.replace('document', 'documents'), ['JANE DOE'], None)
        self.insert('noauthor', self.title.replace('document', 'documents'), [], None)
        items = self.results()['candidates']
        self.assertEqual([x['id'] for x in items], ['unknown'])
        self.assertIn('year_unknown', items[0]['reasons'])

    def test_bounded_fuzzy_checks_and_candidate_count_preserve_exact_doi(self):
        for i in range(5):
            self.insert(f'n{i}', self.title.replace('document', 'documents'), ['Jane Doe'], 2024)
        # Exact DOI is still found after the fuzzy budget is exhausted.
        self.insert('z-exact', 'Different document', [], 2010, '10.1234/x')
        with patch.object(library_management, 'MAX_DUPLICATE_SIMILARITY_CHECKS', 2), \
                patch.object(library_management, 'MAX_DUPLICATE_CANDIDATES', 2):
            data = self.results()
        self.assertTrue(data['similarity_limited'])
        self.assertTrue(data['truncated'])
        self.assertEqual(len(data['candidates']), 2)
        self.assertEqual(data['candidates'][0]['id'], 'z-exact')
        self.assertEqual(data['candidates'][0]['reasons'], ['doi'])


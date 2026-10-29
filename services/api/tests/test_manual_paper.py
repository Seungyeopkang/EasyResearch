"""Manual bibliography creation is local and uses disposable libraries."""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from unittest.mock import patch

from fastapi.testclient import TestClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import storage
from app.main import app


class ManualPaperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'EASYRESEARCH_DATA_DIR': self.temp.name})
        self.env.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.h = {'X-EasyResearch': '1'}
        with storage.transaction() as con:
            con.executemany('INSERT INTO projects(id,name) VALUES(?,?)', [('a', 'A'), ('b', 'B')])

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    def create(self, payload, project='a'):
        return self.client.post(f'/api/projects/{project}/papers', headers=self.h, json=payload)

    def test_create_edit_attach_and_export(self):
        response = self.create({'title': ' Paper title ', 'authors': [' Jane Doe ', '김 연구'],
                                'year': 2024, 'doi': 'https://doi.org/10.1234/AbC'})
        self.assertEqual(response.status_code, 201, response.text)
        paper = response.json()
        self.assertEqual((paper['title'], paper['authors'], paper['year'], paper['doi']),
                         ('Paper title', ['Jane Doe', '김 연구'], 2024, '10.1234/abc'))
        self.assertEqual((paper['file_id'], paper['source'], paper['reading_status']), (None, 'manual', 'to_read'))
        self.assertEqual(self.client.get('/api/papers', params={'project_id': 'b'}).json(), [])
        edit = self.client.patch('/api/papers/' + paper['id'], headers=self.h, json={'year': 2025})
        self.assertEqual(edit.json()['year'], 2025)
        exported = self.client.get('/api/projects/a/export', params={'format': 'json'}).json()
        self.assertEqual(exported['papers'][0]['title'], 'Paper title')
        attach = self.client.post('/api/papers/import', headers=self.h,
                                  data={'project_id': 'a', 'paper_id': paper['id']},
                                  files={'file': ('paper.pdf', b'%PDF-1.4\nfixture\n%%EOF', 'application/pdf')})
        self.assertEqual(attach.status_code, 201, attach.text)
        self.assertEqual((attach.json()['id'], attach.json()['import_action']), (paper['id'], 'attached_pdf'))
        self.assertIsNotNone(attach.json()['file_id'])

    def test_duplicate_records_are_distinct_and_never_overwrite(self):
        one = self.create({'title': 'Same title', 'authors': ['First'], 'doi': '10.1234/same'}).json()
        two = self.create({'title': 'Same title', 'authors': ['Second'], 'doi': '10.1234/same'}).json()
        self.assertNotEqual(one['id'], two['id'])
        items = self.client.get('/api/papers', params={'project_id': 'a'}).json()
        by_id = {item['id']: item for item in items}
        self.assertEqual(by_id[one['id']]['authors'], ['First'])
        self.assertEqual(by_id[two['id']]['authors'], ['Second'])
        candidates = self.client.get('/api/papers/' + two['id'] + '/duplicate-candidates').json()
        self.assertEqual(candidates['candidates'][0]['id'], one['id'])
        self.assertIn('doi', candidates['candidates'][0]['reasons'])

    def test_reject_invalid_fields_without_creating_data(self):
        invalid = [
            {}, {'title': '  '}, {'title': 'x', 'authors': [' ']},
            {'title': 'x', 'authors': ['x' * 501]}, {'title': 'x', 'authors': ['x'] * 101},
            {'title': 'x', 'year': 0}, {'title': 'x', 'year': 10000},
            {'title': 'x', 'year': True}, {'title': 'x', 'year': 2024.5},
            {'title': 'x', 'doi': 'invalid'}, {'title': 'x' * 501},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                self.assertEqual(self.create(payload).status_code, 422)
        self.assertEqual(self.client.get('/api/papers', params={'project_id': 'a'}).json(), [])

    def test_missing_or_trashed_project_and_trashed_duplicate(self):
        old = self.create({'title': 'Title', 'doi': '10.1234/one'}).json()
        self.assertEqual(self.client.delete('/api/papers/' + old['id'], headers=self.h).status_code, 204)
        new = self.create({'title': 'Title', 'doi': '10.1234/one'})
        self.assertEqual(new.status_code, 201, new.text)
        self.assertNotEqual(new.json()['id'], old['id'])
        trash = self.client.get('/api/trash').json()
        self.assertEqual([item['id'] for item in trash['papers']], [old['id']])
        self.assertEqual(self.create({'title': 'x'}, 'missing').status_code, 404)
        self.assertEqual(self.client.delete('/api/projects/a', headers=self.h).status_code, 204)
        self.assertEqual(self.create({'title': 'x'}).status_code, 404)
        self.assertEqual(self.client.post('/api/trash/projects/a/restore', headers=self.h).status_code, 200)
        self.assertEqual(self.create({'title': 'After restore'}).status_code, 201)

    def test_metadata_only_record_survives_backup_restore(self):
        item = self.create({'title': 'Saved bibliography', 'authors': ['Jane Doe'], 'year': 2024, 'doi': '10.1234/save'}).json()
        backup = self.client.post('/api/backups', headers=self.h)
        self.assertEqual(backup.status_code, 201, backup.text)
        archive = self.client.get(backup.json()['download_url']).content
        restored = self.client.post('/api/backups/restore', headers=self.h,
                                    files={'file': ('backup.zip', archive, 'application/zip')})
        self.assertEqual(restored.status_code, 201, restored.text)
        with closing(sqlite3.connect(str(Path(restored.json()['restore_path']) / 'library.sqlite3'))) as con:
            row = con.execute('SELECT title,year,doi,file_id,source FROM papers WHERE id=?', (item['id'],)).fetchone()
            self.assertEqual(row, ('Saved bibliography', 2024, '10.1234/save', None, 'manual'))
            self.assertEqual(con.execute('SELECT project_id FROM project_papers WHERE paper_id=?', (item['id'],)).fetchone()[0], 'a')


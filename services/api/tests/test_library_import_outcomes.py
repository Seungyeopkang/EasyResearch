"""Distinguish file reuse, a new paper, and a project link in batch import."""
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


class ImportOutcomeTests(unittest.TestCase):
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

    def upload(self, project, raw, paper_id=None):
        data = {'project_id': project}
        if paper_id:
            data['paper_id'] = paper_id
        return self.client.post('/api/papers/import', headers=self.h, data=data,
                                files={'file': ('test.pdf', raw, 'application/pdf')})

    def test_batch_outcomes_distinguish_file_reuse_from_paper_and_link(self):
        primary = b'%PDF-1.4\nprimary fixture\n%%EOF'
        alternative = b'%PDF-1.4\nalternative fixture\n%%EOF'
        first = self.upload('a', primary)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual((first.json()['duplicate'], first.json()['import_action']), (False, 'created_paper'))
        repeated = self.upload('a', primary).json()
        self.assertEqual((repeated['id'], repeated['duplicate'], repeated['import_action']),
                         (first.json()['id'], True, 'already_linked'))
        linked = self.upload('b', primary).json()
        self.assertEqual((linked['id'], linked['duplicate'], linked['import_action']),
                         (first.json()['id'], True, 'linked_existing'))
        version = self.client.post('/api/papers/' + first.json()['id'] + '/versions', headers=self.h,
                                   files={'file': ('version.pdf', alternative, 'application/pdf')})
        self.assertEqual(version.status_code, 201, version.text)
        # Existing file, but no paper uses it as its primary PDF yet.
        created = self.upload('a', alternative)
        self.assertEqual(created.status_code, 201, created.text)
        self.assertNotEqual(created.json()['id'], first.json()['id'])
        self.assertEqual((created.json()['duplicate'], created.json()['import_action']), (True, 'created_paper'))

    def test_attach_original_to_existing_metadata_only_paper(self):
        with storage.transaction() as con:
            con.execute("INSERT INTO papers(id,title) VALUES('metadata','Paper')")
            con.execute("INSERT INTO project_papers(project_id,paper_id) VALUES('a','metadata')")
        raw = b'%PDF-1.4\nattached fixture\n%%EOF'
        attached = self.upload('a', raw, 'metadata').json()
        self.assertEqual((attached['id'], attached['import_action']), ('metadata', 'attached_pdf'))
        again = self.upload('a', raw, 'metadata').json()
        self.assertEqual((again['id'], again['duplicate'], again['import_action']), ('metadata', True, 'already_attached'))

    def test_detach_during_upload_is_not_undone(self):
        with storage.transaction() as con:
            con.execute("INSERT INTO papers(id,title) VALUES('metadata','Paper')")
            con.execute("INSERT INTO project_papers(project_id,paper_id) VALUES('a','metadata')")
        original = storage.store_stream
        def detach_before_save(stream):
            result = original(stream)
            library_management.detach('a', 'metadata')
            return result
        with patch.object(storage, 'store_stream', side_effect=detach_before_save):
            response = self.upload('a', b'%PDF-1.4\nseparate fixture\n%%EOF', 'metadata')
        self.assertEqual(response.status_code, 409, response.text)
        with storage.transaction() as con:
            self.assertIsNone(con.execute("SELECT 1 FROM project_papers WHERE project_id='a' AND paper_id='metadata'").fetchone())
            self.assertIsNone(con.execute("SELECT file_id FROM papers WHERE id='metadata'").fetchone()['file_id'])
            self.assertIsNotNone(con.execute("SELECT 1 FROM link_trash WHERE project_id='a' AND paper_id='metadata'").fetchone())


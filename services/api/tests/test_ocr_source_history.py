"""OCR source identity, migration and backup tests use isolated libraries."""
import hashlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import jobs, storage
from app.main import app, analysis_inputs


class OCRSourceHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": self.temp.name})
        self.env.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.h = {"X-EasyResearch": "1"}
        raw = b"%PDF-1.4\nsynthetic\n%%EOF"
        sha = hashlib.sha256(raw).hexdigest()
        key = f"files/{sha[:2]}/{sha}.pdf"
        path = Path(self.temp.name) / key
        path.parent.mkdir(parents=True)
        path.write_bytes(raw)
        with storage.transaction() as con:
            con.execute("INSERT INTO projects(id,name) VALUES('pr','Project')")
            con.execute("INSERT INTO files(id,sha256,size,storage_key) VALUES('f',?,?,?)", (sha, len(raw), key))
            con.execute("INSERT INTO papers(id,file_id,title,page_count) VALUES('p','f','Paper',1)")
            con.execute("INSERT INTO project_papers(project_id,paper_id) VALUES('pr','p')")
            for job, text in [('one', 'old OCR quote'), ('two', 'new unrelated text')]:
                con.execute("INSERT INTO jobs(id,kind,target_id,status) VALUES(?,'ocr_page','p','completed')", (job,))
                con.execute("INSERT INTO ocr_pages(job_id,paper_id,page_index,text,language,source,status) VALUES(?,'p',0,?,'en','ocr_windows','ocr_unverified')", (job, text))

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    def create(self, **kwargs):
        return self.client.post('/api/papers/p/evidence', headers=self.h,
                                json={'page_index': 0, 'quote': 'old OCR quote', 'capture_method': 'ocr', **kwargs})

    def test_source_frozen_across_new_ocr_edit_history_and_backup(self):
        self.assertEqual(self.create().status_code, 409)
        self.assertEqual(self.create(ocr_job_id='two').status_code, 422)
        response = self.create(ocr_job_id='one')
        self.assertEqual(response.status_code, 201, response.text)
        evidence = response.json()
        self.assertEqual((evidence['ocr_job_id'], evidence['status']), ('one', 'candidate'))
        self.assertEqual(self.client.get('/api/ocr-results/one').json()['text'], 'old OCR quote')
        with storage.transaction() as con:
            con.execute("INSERT INTO jobs(id,kind,target_id,status) VALUES('three','ocr_page','p','completed')")
            con.execute("INSERT INTO ocr_pages(job_id,paper_id,page_index,text,language,source,status) VALUES('three','p',0,'third result','en','ocr_windows','ocr_unverified')")
        current = self.client.get('/api/papers/p/evidence').json()[0]
        self.assertEqual((current['ocr_job_id'], current['status']), ('one', 'candidate'))
        edit = self.client.put('/api/evidence/' + evidence['id'], headers=self.h,
                               json={'page_index': 0, 'quote': 'old OCR quote', 'note': 'edited', 'capture_method': 'ocr'})
        self.assertEqual(edit.status_code, 200, edit.text)
        self.assertEqual((edit.json()['ocr_job_id'], edit.json()['status']), ('one', 'candidate'))
        revisions = self.client.get('/api/evidence/' + evidence['id'] + '/revisions').json()
        self.assertEqual(revisions[0]['ocr_job_id'], 'one')
        backup = self.client.post('/api/backups', headers=self.h)
        self.assertEqual(backup.status_code, 201, backup.text)
        archive = self.client.get(backup.json()['download_url']).content
        restore = self.client.post('/api/backups/restore', headers=self.h, files={'file': ('backup.zip', archive, 'application/zip')})
        self.assertEqual(restore.status_code, 201, restore.text)
        with closing(sqlite3.connect(str(Path(restore.json()['restore_path']) / 'library.sqlite3'))) as con:
            self.assertEqual(con.execute('SELECT job_id FROM evidence_ocr_source').fetchone()[0], 'one')
            self.assertEqual(con.execute('SELECT job_id FROM revision_ocr_source').fetchone()[0], 'one')
            self.assertEqual(con.execute("SELECT text FROM ocr_pages WHERE job_id='one'").fetchone()[0], 'old OCR quote')

    def test_migrated_ambiguous_legacy_source_stays_unknown_after_note_edit(self):
        with storage.transaction() as con:
            con.execute("INSERT INTO evidence(id,paper_id,page_index,quote,note) VALUES('legacy','p',0,'old OCR quote','old note')")
            con.execute("INSERT INTO evidence_provenance(evidence_id,capture_method) VALUES('legacy','ocr')")
        item = self.client.get('/api/papers/p/evidence').json()[0]
        self.assertTrue(item['ocr_source_unknown'])
        self.assertEqual(item['status'], 'ocr_unavailable')
        edit = self.client.put('/api/evidence/legacy', headers=self.h,
                               json={'page_index': 0, 'quote': 'old OCR quote', 'note': 'new note', 'capture_method': 'ocr'})
        self.assertEqual(edit.status_code, 200, edit.text)
        self.assertTrue(edit.json()['ocr_source_unknown'])
        self.assertIsNone(edit.json()['ocr_job_id'])
        self.assertIsNone(self.client.get('/api/evidence/legacy/revisions').json()[0]['ocr_job_id'])

    def test_pdf_reprocessing_does_not_replace_ocr_match_status(self):
        response = self.create(ocr_job_id='one')
        self.assertEqual(response.status_code, 201, response.text)
        with storage.transaction() as con:
            file = con.execute("SELECT sha256,size FROM files WHERE id='f'").fetchone()
            con.execute("INSERT INTO jobs(id,kind,target_id,status,lease_token) VALUES('extract','pdf_extract','p','running','token')")
        result = {'sha256': file['sha256'], 'size_bytes': file['size'], 'page_count': 1, 'status': 'completed',
                  'pages': [{'page_index': 0, 'page_label': '1', 'text': 'different PDF text', 'rotation': 0,
                             'status': 'extracted', 'warnings': [], 'image_count': 0}]}
        with patch.object(jobs, 'inspect_pdf', return_value=result):
            jobs.execute_pdf('extract', 'token')
        with storage.transaction() as con:
            self.assertEqual(con.execute("SELECT status FROM jobs WHERE id='extract'").fetchone()['status'], 'completed')
            self.assertEqual(con.execute('SELECT status FROM evidence WHERE id=?', (response.json()['id'],)).fetchone()['status'], 'candidate')

    def test_existing_analysis_uses_selected_ocr_only_and_refuses_unknown_source(self):
        response = self.create(ocr_job_id='one', verified_with_original=True)
        self.assertEqual(response.status_code, 201, response.text)
        # An old record without the job association cannot borrow a later OCR
        # result just because that later run happens to contain its quote.
        with storage.transaction() as con:
            con.execute("INSERT INTO evidence(id,paper_id,page_index,quote,source) VALUES('unknown','p',0,'new unrelated text','user_verified_ocr')")
            con.execute("INSERT INTO evidence_provenance(evidence_id,capture_method,original_checked) VALUES('unknown','ocr',1)")
        _, excerpts = analysis_inputs(['p'])
        self.assertEqual([item['id'] for item in excerpts], [response.json()['id']])
        self.assertEqual(excerpts[0]['verification'], 'user_verified_ocr')

    def test_invalid_manifest_is_reported_as_bad_archive(self):
        for bad in ([], None, 'incorrect', 12):
            out = io.BytesIO()
            with zipfile.ZipFile(out, 'w') as z:
                z.writestr('manifest.json', json.dumps(bad))
                z.writestr('library.sqlite3', b'wrong')
            res = self.client.post('/api/backups/inspect', headers=self.h,
                                   files={'file': ('backup.zip', out.getvalue(), 'application/zip')})
            self.assertEqual(res.status_code, 400, res.text)
            self.assertIn('백업', res.json()['detail'])


class OCRSourceMigrationTests(unittest.TestCase):
    def test_v3_migration_does_not_infer_legacy_ocr_identity(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'EASYRESEARCH_DATA_DIR': folder}):
            path = Path(folder) / 'library.sqlite3'
            with closing(sqlite3.connect(str(path))) as con:
                con.executescript(storage.SCHEMA_V3)
                con.execute('PRAGMA user_version=3')
                con.execute("INSERT INTO papers(id,title) VALUES('p','paper')")
                con.execute("INSERT INTO evidence(id,paper_id,page_index,quote) VALUES('e','p',0,'old OCR quote')")
                con.execute("INSERT INTO evidence_provenance(evidence_id,capture_method) VALUES('e','ocr')")
                con.execute("INSERT INTO jobs(id,kind,target_id,status) VALUES('j','ocr_page','p','completed')")
                con.execute("INSERT INTO ocr_pages(job_id,paper_id,page_index,text,language,source,status) VALUES('j','p',0,'old OCR quote','en','ocr_windows','ocr_unverified')")
                con.commit()
            storage.init_db()
            with closing(sqlite3.connect(str(path))) as con:
                self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0], storage.SCHEMA_VERSION)
                self.assertEqual(con.execute('SELECT count(*) FROM evidence_ocr_source').fetchone()[0], 0)
                self.assertEqual(con.execute('SELECT capture_method FROM evidence_provenance').fetchone()[0], 'ocr')
            snapshot = list((Path(folder) / 'migration-backups').glob('*.sqlite3'))
            self.assertEqual(len(snapshot), 1)
            with closing(sqlite3.connect(str(snapshot[0]))) as con:
                self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0], 3)


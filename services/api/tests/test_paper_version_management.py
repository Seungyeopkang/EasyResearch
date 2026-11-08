"""Version changes preserve shared PDF bytes, other papers, evidence and backups."""
import hashlib
import io
import os
import sqlite3
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import storage
from app.main import app


class PaperVersionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'EASYRESEARCH_DATA_DIR': self.temp.name})
        self.env.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {'X-EasyResearch': '1'}
        self.primary = b'%PDF-1.4\nprimary fixture\n%%EOF'
        self.alternative = b'%PDF-1.4\nalternative fixture\n%%EOF'
        sha, size, key = storage.store_stream(io.BytesIO(self.primary))
        with storage.transaction() as con:
            con.executemany('INSERT INTO projects(id,name) VALUES(?,?)', [('a','A'),('b','B')])
            con.execute('INSERT INTO files(id,sha256,size,storage_key) VALUES(?,?,?,?)', ('f',sha,size,key))
            con.execute("INSERT INTO papers(id,file_id,title,page_count) VALUES('p','f','Paper',1)")
            con.executemany("INSERT INTO project_papers(project_id,paper_id) VALUES(?,'p')", [('a',),('b',)])
            con.execute("INSERT INTO evidence(id,paper_id,page_index,quote,note) VALUES('e','p',0,'quote','keep')")
        add = self.client.post('/api/papers/p/versions', headers=self.headers, data={'label':'initial'},
                               files={'file':('version.pdf',self.alternative,'application/pdf')})
        self.assertEqual(add.status_code, 201, add.text)
        self.version = add.json()
        self.url = '/api/papers/p/versions/' + self.version['id']
        with storage.transaction() as con:
            con.execute("INSERT INTO papers(id,file_id,title,page_count) VALUES('other',?,'Other',1)", (self.version['file_id'],))
            con.execute("INSERT INTO project_papers(project_id,paper_id) VALUES('b','other')")

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    def send(self, method, path, **kwargs):
        return self.client.request(method, path, headers=self.headers, **kwargs)

    def test_rename_trash_duplicate_restore_keeps_shared_files_and_backup(self):
        before = self.client.get('/api/papers/p/versions').json()['versions'][0]
        renamed = self.send('PATCH', self.url, json={'label':'published', 'expected_revision':before['revision']})
        self.assertEqual(renamed.status_code, 200, renamed.text)
        self.assertEqual(renamed.json()['label'], 'published')
        self.assertNotEqual(renamed.json()['revision'], before['revision'])
        stale = self.send('DELETE', self.url, json={'expected_revision':before['revision']})
        self.assertEqual(stale.status_code, 409)
        removed = self.send('DELETE', self.url, json={'expected_revision':renamed.json()['revision']})
        self.assertEqual(removed.status_code, 200, removed.text)
        listing = self.client.get('/api/papers/p/versions').json()
        self.assertEqual(listing['versions'], [])
        self.assertEqual(listing['trashed_versions'][0]['label'], 'published')
        self.assertEqual(self.client.get(self.url+'/file').status_code, 404)
        self.assertEqual(self.client.get('/api/papers/p/file').content, self.primary)
        self.assertEqual(self.client.get('/api/papers/other/file').content, self.alternative)
        self.assertEqual(self.client.get('/api/papers/p/evidence').json()[0]['note'], 'keep')
        self.assertEqual({item['id'] for item in self.client.get('/api/papers?project_id=b').json()}, {'p','other'})
        duplicate = self.client.post('/api/papers/p/versions', headers=self.headers,
                                     files={'file':('version.pdf',self.alternative,'application/pdf')})
        self.assertEqual(duplicate.status_code, 201, duplicate.text)
        self.assertTrue(duplicate.json()['duplicate'])
        self.assertTrue(duplicate.json()['trashed'])
        self.assertEqual(duplicate.json()['revision'], removed.json()['revision'])
        backup = self.send('POST', '/api/backups')
        self.assertEqual(backup.status_code, 201, backup.text)
        self.assertEqual(backup.json()['file_count'], 2)
        archive = self.client.get(backup.json()['download_url']).content
        restored = self.send('POST', '/api/backups/restore', files={'file':('backup.zip',archive,'application/zip')})
        self.assertEqual(restored.status_code, 201, restored.text)
        root = Path(restored.json()['restore_path'])
        with closing(sqlite3.connect(str(root/'library.sqlite3'))) as con, con:
            con.execute('PRAGMA foreign_keys=ON')
            self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertEqual(con.execute('SELECT label FROM paper_versions WHERE id=?', (self.version['id'],)).fetchone()[0], 'published')
            self.assertIsNotNone(con.execute('SELECT 1 FROM paper_version_trash WHERE version_id=?', (self.version['id'],)).fetchone())
            self.assertEqual(con.execute("SELECT note FROM evidence WHERE id='e'").fetchone()[0], 'keep')
            key = con.execute('SELECT storage_key FROM files WHERE id=?', (self.version['file_id'],)).fetchone()[0]
        self.assertEqual((root/key).read_bytes(), self.alternative)
        restored_version = self.send('POST', self.url+'/restore', json={'expected_revision':removed.json()['revision']})
        self.assertEqual(restored_version.status_code, 200, restored_version.text)
        self.assertEqual(self.client.get(self.url+'/file').content, self.alternative)
        # Returning to the old visible label must not revive an old token.
        self.assertNotEqual(restored_version.json()['revision'], renamed.json()['revision'])
        self.assertEqual(self.send('DELETE',self.url,json={'expected_revision':renamed.json()['revision']}).status_code,409)

    def test_concurrent_renames_have_exactly_one_winner(self):
        revision = self.client.get('/api/papers/p/versions').json()['versions'][0]['revision']
        gate = Barrier(2)
        def change(label):
            gate.wait(timeout=5)
            return self.send('PATCH',self.url,json={'label':label,'expected_revision':revision})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(change, ['first','second']))
        self.assertEqual(sorted(r.status_code for r in results), [200,409])
        current = self.client.get('/api/papers/p/versions').json()['versions'][0]
        self.assertIn(current['label'], ['first','second'])
        self.assertEqual(self.client.get('/api/papers/other/file').content,self.alternative)

    def test_restore_requires_active_paper_and_current_revision(self):
        revision = self.client.get('/api/papers/p/versions').json()['versions'][0]['revision']
        trashed = self.send('DELETE',self.url,json={'expected_revision':revision}).json()
        self.assertEqual(self.send('POST',self.url+'/restore',json={'expected_revision':revision}).status_code,409)
        self.assertEqual(self.send('DELETE','/api/papers/p').status_code,204)
        self.assertEqual(self.send('POST',self.url+'/restore',json={'expected_revision':trashed['revision']}).status_code,409)
        self.assertEqual(self.send('POST','/api/trash/papers/p/restore').status_code,200)
        self.assertEqual(self.send('POST',self.url+'/restore',json={'expected_revision':trashed['revision']}).status_code,200)
        self.assertEqual(self.client.get('/api/papers/other/file').content,self.alternative)


class VersionMigrationTests(unittest.TestCase):
    def test_v4_migration_and_failure_leave_snapshot_and_pdf_untouched(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'EASYRESEARCH_DATA_DIR':folder}):
            root=Path(folder)
            raw=b'%PDF-1.4\noriginal fixture\n%%EOF'
            sha,size,key=storage.store_stream(io.BytesIO(raw))
            database=root/'library.sqlite3'
            with closing(sqlite3.connect(str(database))) as con:
                con.executescript(storage.SCHEMA_V4)
                con.execute('PRAGMA user_version=4')
                con.execute('INSERT INTO files(id,sha256,size,storage_key) VALUES(?,?,?,?)',('f',sha,size,key))
                con.execute("INSERT INTO papers(id,file_id,title) VALUES('p','f','Paper')")
                con.execute("INSERT INTO paper_versions(id,paper_id,file_id,label) VALUES('v','p','f','old')")
                con.commit()
            def fail(con):
                con.execute("UPDATE paper_versions SET label='bad'")
                raise RuntimeError('migration failed')
            with patch.dict(storage.MIGRATIONS,{4:fail}):
                with self.assertRaisesRegex(RuntimeError,'migration failed'):
                    storage.init_db()
            with closing(sqlite3.connect(str(database))) as con:
                self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0],4)
                self.assertEqual(con.execute('SELECT label FROM paper_versions').fetchone()[0],'old')
            snapshots=list((root/'migration-backups').glob('*.sqlite3'))
            self.assertEqual(len(snapshots),1)
            with closing(sqlite3.connect(str(snapshots[0]))) as con:
                self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0],4)
                self.assertEqual(con.execute('SELECT label FROM paper_versions').fetchone()[0],'old')
            self.assertEqual((root/key).read_bytes(),raw)
            storage.init_db()
            with closing(sqlite3.connect(str(database))) as con:
                self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0],5)
                self.assertEqual(con.execute('SELECT label FROM paper_versions').fetchone()[0],'old')
                self.assertEqual(con.execute('SELECT count(*) FROM paper_version_trash').fetchone()[0],0)
            self.assertEqual((root/key).read_bytes(),raw)

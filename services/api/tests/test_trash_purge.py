"""Permanent purge of trashed items: preview, confirmation token, blocking, and file rules.

Uses an isolated temporary data folder and a synthetic PDF only.
"""
import hashlib
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import storage
from app.main import app


class TrashPurgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'EASYRESEARCH_DATA_DIR': self.temp.name})
        self.env.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.h = {'X-EasyResearch': '1'}
        self.pdf = b'%PDF-1.4\nsynthetic purge fixture\n%%EOF'
        digest = hashlib.sha256(self.pdf).hexdigest()
        self.key = 'files/' + digest[:2] + '/' + digest + '.pdf'
        self.pdf_path = Path(self.temp.name) / self.key
        self.pdf_path.parent.mkdir(parents=True, exist_ok=True)
        self.pdf_path.write_bytes(self.pdf)
        with storage.transaction() as con:
            con.executemany('INSERT INTO projects(id,name) VALUES(?,?)', [('a', 'A'), ('b', 'B')])
            con.execute('INSERT INTO files(id,sha256,size,storage_key) VALUES(?,?,?,?)',
                        ('f', digest, len(self.pdf), self.key))
            con.execute("INSERT INTO papers(id,file_id,title,page_count) VALUES('p','f','Paper',1)")
            con.executemany('INSERT INTO project_papers(project_id,paper_id,reading_status,last_page) VALUES(?,?,?,?)',
                            [('a', 'p', 'reading', 2), ('b', 'p', 'done', 0)])
            con.execute("INSERT INTO evidence(id,paper_id,page_index,quote,note) VALUES('e','p',0,'same','shared')")
            con.execute("INSERT INTO evidence_revisions(evidence_id,page_index,quote,note,prefix,suffix,status) "
                        "VALUES('e',0,'old','note','','','unverified')")

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    # helpers -------------------------------------------------------------
    def request(self, method, path, **kwargs):
        return self.client.request(method, path, headers=self.h, **kwargs)

    def preview(self, kind, item_id):
        return self.client.get(f'/api/trash/{kind}/{item_id}/purge-preview')

    def purge(self, kind, item_id, token, delete_files=False):
        return self.request('POST', f'/api/trash/{kind}/{item_id}/purge',
                            json={'confirm_token': token, 'delete_files': delete_files})

    def save_note(self, project, note):
        path = f'/api/projects/{project}/papers/p/note'
        revision = self.client.get(path).json()['revision']
        return self.request('PUT', path, json={'note': note, 'expected_revision': revision})

    def scalar(self, sql, params=()):
        with closing(storage.connect()) as con:
            return con.execute(sql, params).fetchone()[0]

    def write(self, *statements):
        with closing(storage.connect()) as con:
            for sql, params in statements:
                con.execute(sql, params)
            con.commit()

    def revision_id(self):
        return self.scalar("SELECT id FROM evidence_revisions WHERE evidence_id='e'")

    def assert_integrity(self):
        with closing(storage.connect()) as con:
            self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(), [])

    # tests ---------------------------------------------------------------
    def test_preview_counts_and_notice_for_trashed_evidence(self):
        self.assertEqual(self.request('DELETE', '/api/evidence/e').status_code, 204)
        response = self.preview('evidence', 'e')
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual((body['counts']['evidence'], body['counts']['evidence_revisions'],
                          body['counts']['evidence_trash']), (1, 1, 1))
        self.assertEqual(body['blocked_by'], [])
        self.assertEqual(body['deletable_files'], [])
        self.assertIn('되돌릴 수 없', body['notice'])
        self.assertIn('백업 ZIP', body['notice'])
        self.assertRegex(body['confirm_token'], r'^[0-9a-f]{64}$')

    def test_active_missing_or_unknown_items_return_404(self):
        self.assertEqual(self.preview('papers', 'p').status_code, 404)
        self.assertEqual(self.preview('evidence', 'e').status_code, 404)
        self.assertEqual(self.preview('projects', 'a').status_code, 404)
        self.assertEqual(self.preview('links', 'missing').status_code, 404)
        self.assertEqual(self.preview('bogus', 'p').status_code, 404)
        self.assertEqual(self.purge('papers', 'p', 'x' * 64).status_code, 404)
        self.assertEqual(self.purge('papers', 'missing', 'x' * 64).status_code, 404)
        self.assert_integrity()

    def test_purge_evidence_removes_only_its_rows(self):
        self.write(("INSERT INTO evidence(id,paper_id,page_index,quote,note) VALUES('e2','p',0,'other','kept')", ()))
        self.assertEqual(self.request('DELETE', '/api/evidence/e').status_code, 204)
        token = self.preview('evidence', 'e').json()['confirm_token']
        response = self.purge('evidence', 'e', token)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual((body['status'], body['deleted']['evidence']), ('purged', 1))
        self.assertEqual(body['deleted_files'], [])
        self.assertEqual(self.scalar("SELECT count(*) FROM evidence WHERE id='e'"), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM evidence_revisions WHERE evidence_id='e'"), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM evidence_trash WHERE evidence_id='e'"), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM evidence WHERE id='e2'"), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM papers WHERE id='p'"), 1)
        self.assertEqual(self.client.get('/api/trash').json()['evidence'], [])
        self.assertEqual(self.pdf_path.read_bytes(), self.pdf)
        self.assert_integrity()

    def test_purge_link_removes_link_trash_but_keeps_project_note(self):
        self.assertEqual(self.save_note('a', 'A note').status_code, 200)
        self.assertEqual(self.request('DELETE', '/api/projects/a/papers/p').status_code, 204)
        link_id = self.client.get('/api/trash').json()['links'][0]['id']
        token = self.preview('links', link_id).json()['confirm_token']
        response = self.purge('links', link_id, token)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['deleted'], {'link_trash': 1})
        self.assertEqual(self.scalar('SELECT count(*) FROM link_trash'), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM project_papers WHERE project_id='a'"), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM project_papers WHERE project_id='b'"), 1)
        self.assertEqual(self.scalar("SELECT note FROM project_paper_notes WHERE project_id='a' AND paper_id='p'"), 'A note')
        self.assertEqual(self.scalar("SELECT count(*) FROM papers WHERE id='p'"), 1)
        self.assert_integrity()

    def test_purge_project_removes_its_ideas_and_runs_but_keeps_papers(self):
        self.assertEqual(self.save_note('a', 'A').status_code, 200)
        self.write(
            ("INSERT INTO ideas(id,project_id,title) VALUES('i','a','idea')", ()),
            ("INSERT INTO idea_evidence(idea_id,evidence_id) VALUES('i','e')", ()),
            ("INSERT INTO experiments(id,project_id,title,status,config_json) VALUES('x','a','t','draft','{}')", ()),
            ("INSERT INTO search_runs(id,project_id,source,query,status) VALUES('s','a','arxiv','q','done')", ()),
        )
        self.assertEqual(self.request('DELETE', '/api/projects/a').status_code, 204)
        body = self.preview('projects', 'a').json()
        self.assertEqual(body['blocked_by'], [])
        self.assertEqual((body['counts']['ideas'], body['counts']['idea_evidence'],
                          body['counts']['experiments'], body['counts']['search_runs'],
                          body['counts']['projects']), (1, 1, 1, 1, 1))
        response = self.purge('projects', 'a', body['confirm_token'])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.scalar("SELECT count(*) FROM projects WHERE id='a'"), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM ideas WHERE project_id='a'"), 0)
        self.assertEqual(self.scalar('SELECT count(*) FROM idea_evidence'), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM experiments WHERE project_id='a'"), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM search_runs WHERE project_id='a'"), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM project_paper_notes WHERE project_id='a'"), 0)
        # Papers, evidence and the other project are not part of the purge.
        self.assertEqual(self.scalar("SELECT count(*) FROM papers WHERE id='p'"), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM evidence WHERE id='e'"), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM projects WHERE id='b'"), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM project_papers WHERE project_id='b' AND paper_id='p'"), 1)
        self.assert_integrity()

    def test_purge_paper_removes_dependents_and_keeps_pdf_without_delete_files(self):
        self.assertEqual(self.save_note('a', 'memo').status_code, 200)
        rev = self.revision_id()
        self.write(
            ("INSERT INTO pages(paper_id,page_index,text,status) VALUES('p',0,'text','extracted')", ()),
            ("INSERT INTO page_extraction_details(paper_id,page_index,parser_version,warning_json,image_count) "
             "VALUES('p',0,'v1','[]',0)", ()),
            ("INSERT INTO jobs(id,kind,target_id,status) VALUES('j','ocr','p','done')", ()),
            ("INSERT INTO job_events(job_id,status) VALUES('j','done')", ()),
            ("INSERT INTO ocr_pages(job_id,paper_id,page_index,text,language,source,status) "
             "VALUES('j','p',0,'ocr text','en','ocr','ok')", ()),
            ("INSERT INTO evidence_ocr_source(evidence_id,job_id) VALUES('e','j')", ()),
            ("INSERT INTO evidence_provenance(evidence_id,capture_method,original_checked,file_sha256) "
             "VALUES('e','manual',0,NULL)", ()),
            ("INSERT INTO revision_provenance(revision_id,capture_method,original_checked,file_sha256) "
             "VALUES(?,'manual',0,NULL)", (rev,)),
            ("INSERT INTO revision_ocr_source(revision_id,job_id) VALUES(?,'j')", (rev,)),
        )
        self.assertEqual(self.request('DELETE', '/api/papers/p').status_code, 204)
        body = self.preview('papers', 'p').json()
        expected = {'papers': 1, 'pages': 1, 'page_extraction_details': 1, 'ocr_pages': 1, 'jobs': 1,
                    'job_events': 1, 'evidence': 1, 'evidence_revisions': 1, 'revision_provenance': 1,
                    'revision_ocr_source': 1, 'evidence_provenance': 1, 'evidence_ocr_source': 1,
                    'project_papers': 2, 'project_paper_notes': 1}
        for table, count in expected.items():
            self.assertEqual(body['counts'][table], count, table)
        self.assertEqual(body['blocked_by'], [])
        self.assertEqual([f['file_id'] for f in body['deletable_files']], ['f'])
        self.assertEqual(body['retained_files_reason'], '')

        response = self.purge('papers', 'p', body['confirm_token'], delete_files=False)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['deleted_files'], [])
        for sql in ["SELECT count(*) FROM papers WHERE id='p'",
                    "SELECT count(*) FROM pages WHERE paper_id='p'",
                    "SELECT count(*) FROM ocr_pages WHERE paper_id='p'",
                    "SELECT count(*) FROM jobs WHERE target_id='p'",
                    "SELECT count(*) FROM evidence WHERE paper_id='p'",
                    "SELECT count(*) FROM project_papers WHERE paper_id='p'",
                    "SELECT count(*) FROM project_paper_notes WHERE paper_id='p'"]:
            self.assertEqual(self.scalar(sql), 0, sql)
        # delete_files=false keeps both the file row and the physical PDF.
        self.assertEqual(self.scalar("SELECT count(*) FROM files WHERE id='f'"), 1)
        self.assertEqual(self.pdf_path.read_bytes(), self.pdf)
        self.assert_integrity()

    def test_purge_paper_with_delete_files_removes_pdf_and_version_file(self):
        other = b'%PDF-1.7\nsynthetic purge version\n%%EOF'
        upload = self.request('POST', '/api/papers/p/versions', data={'label': 'v2'},
                              files={'file': ('other.pdf', other, 'application/pdf')})
        self.assertEqual(upload.status_code, 201, upload.text)
        other_sha = hashlib.sha256(other).hexdigest()
        other_path = Path(self.temp.name) / 'files' / other_sha[:2] / (other_sha + '.pdf')
        self.assertTrue(other_path.is_file())
        self.assertEqual(self.request('DELETE', '/api/papers/p').status_code, 204)
        body = self.preview('papers', 'p').json()
        self.assertEqual(body['counts']['paper_versions'], 1)
        self.assertEqual(sorted(f['sha256'] for f in body['deletable_files']),
                         sorted([hashlib.sha256(self.pdf).hexdigest(), other_sha]))
        response = self.purge('papers', 'p', body['confirm_token'], delete_files=True)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(sorted(response.json()['deleted_files']), sorted([hashlib.sha256(self.pdf).hexdigest(), other_sha]))
        self.assertFalse(self.pdf_path.exists())
        self.assertFalse(other_path.exists())
        self.assertEqual(self.scalar("SELECT count(*) FROM files WHERE id='f'"), 0)
        self.assertEqual(self.scalar('SELECT count(*) FROM paper_versions'), 0)
        self.assert_integrity()

    def test_shared_pdf_is_not_deleted_while_another_paper_uses_it(self):
        self.write(("INSERT INTO papers(id,file_id,title) VALUES('q','f','Other paper')", ()))
        self.assertEqual(self.request('DELETE', '/api/papers/p').status_code, 204)
        body = self.preview('papers', 'p').json()
        self.assertEqual(body['deletable_files'], [])
        self.assertTrue(body['retained_files_reason'])
        response = self.purge('papers', 'p', body['confirm_token'], delete_files=True)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['deleted_files'], [])
        self.assertEqual(self.pdf_path.read_bytes(), self.pdf)
        self.assertEqual(self.scalar("SELECT count(*) FROM files WHERE id='f'"), 1)
        self.assertEqual(self.scalar("SELECT file_id FROM papers WHERE id='q'"), 'f')
        self.assertEqual(self.scalar("SELECT count(*) FROM papers WHERE id='p'"), 0)
        self.assert_integrity()

    def test_reupload_between_commit_and_unlink_keeps_pdf(self):
        digest = hashlib.sha256(self.pdf).hexdigest()
        self.assertEqual(self.request('DELETE', '/api/papers/p').status_code, 204)
        body = self.preview('papers', 'p').json()
        original_connect = storage.connect
        calls = {'n': 0}

        def connect_with_reupload():
            # Call 1 is the purge transaction; call 2 is the per-file lock check
            # that runs after that commit. A re-upload of the same bytes lands here.
            calls['n'] += 1
            con = original_connect()
            if calls['n'] == 2:
                con.execute("INSERT INTO files(id,sha256,size,storage_key) VALUES('g',?,?,?)",
                            (digest, len(self.pdf), self.key))
                con.commit()
            return con

        with patch.object(storage, 'connect', side_effect=connect_with_reupload):
            response = self.purge('papers', 'p', body['confirm_token'], delete_files=True)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['deleted_files'], [])
        self.assertEqual(response.json()['files_not_removed'], [{'sha256': digest, 'reason': 'reuploaded'}])
        self.assertEqual(self.scalar("SELECT count(*) FROM files WHERE id='g' AND sha256=?", (digest,)), 1)
        self.assertEqual(self.pdf_path.read_bytes(), self.pdf)
        self.assert_integrity()
    def test_idea_linked_paper_is_blocked_with_409(self):
        self.write(
            ("INSERT INTO ideas(id,project_id,title) VALUES('i','b','idea')", ()),
            ("INSERT INTO idea_evidence(idea_id,evidence_id) VALUES('i','e')", ()),
        )
        self.assertEqual(self.request('DELETE', '/api/papers/p').status_code, 204)
        body = self.preview('papers', 'p').json()
        self.assertEqual(body['blocked_by'][0]['reason'], 'idea_linked_evidence')
        self.assertEqual(body['blocked_by'][0]['ids'], ['e'])
        response = self.purge('papers', 'p', body['confirm_token'], delete_files=True)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.scalar("SELECT count(*) FROM papers WHERE id='p'"), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM evidence WHERE id='e'"), 1)
        self.assertEqual(self.pdf_path.read_bytes(), self.pdf)
        self.assert_integrity()

    def test_idea_link_added_after_evidence_trash_blocks_purge(self):
        self.assertEqual(self.request('DELETE', '/api/evidence/e').status_code, 204)
        self.write(
            ("INSERT INTO ideas(id,project_id,title) VALUES('i','a','idea')", ()),
            ("INSERT INTO idea_evidence(idea_id,evidence_id) VALUES('i','e')", ()),
        )
        body = self.preview('evidence', 'e').json()
        self.assertEqual(body['blocked_by'], [{'reason': 'idea_linked_evidence', 'ids': ['e']}])
        self.assertEqual(self.purge('evidence', 'e', body['confirm_token']).status_code, 409)
        self.assertEqual(self.scalar("SELECT count(*) FROM evidence WHERE id='e'"), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM evidence_trash WHERE evidence_id='e'"), 1)
        self.assert_integrity()

    def test_stale_token_after_related_change_is_rejected(self):
        self.assertEqual(self.request('DELETE', '/api/papers/p').status_code, 204)
        stale = self.preview('papers', 'p').json()['confirm_token']
        # Another window attaches a note to project b between preview and purge.
        self.write(("INSERT INTO project_paper_notes(project_id,paper_id,note) VALUES('b','p','changed')", ()))
        response = self.purge('papers', 'p', stale, delete_files=True)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.scalar("SELECT count(*) FROM papers WHERE id='p'"), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM project_paper_notes WHERE paper_id='p'"), 1)
        self.assertEqual(self.pdf_path.read_bytes(), self.pdf)

        fresh = self.preview('papers', 'p').json()
        self.assertNotEqual(fresh['confirm_token'], stale)
        response = self.purge('papers', 'p', fresh['confirm_token'])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['deleted']['project_paper_notes'], 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM project_paper_notes WHERE paper_id='p'"), 0)
        self.assert_integrity()

    def test_restore_after_preview_makes_purge_404(self):
        self.assertEqual(self.request('DELETE', '/api/papers/p').status_code, 204)
        token = self.preview('papers', 'p').json()['confirm_token']
        self.assertEqual(self.request('POST', '/api/trash/papers/p/restore').status_code, 200)
        self.assertEqual(self.purge('papers', 'p', token).status_code, 404)
        self.assertEqual(self.scalar("SELECT count(*) FROM papers WHERE id='p' AND deleted_at IS NULL"), 1)

    def test_purge_rejects_wrong_token_without_changes(self):
        self.assertEqual(self.request('DELETE', '/api/evidence/e').status_code, 204)
        response = self.purge('evidence', 'e', 'f' * 64)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.scalar("SELECT count(*) FROM evidence WHERE id='e'"), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM evidence_trash WHERE evidence_id='e'"), 1)


if __name__ == '__main__':
    unittest.main()

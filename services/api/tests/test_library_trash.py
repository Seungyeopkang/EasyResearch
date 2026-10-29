"""Recoverable project scope and v1 migration; isolated DB and synthetic PDF only."""
import hashlib
import os
import sqlite3
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path
from unittest.mock import patch
from contextlib import closing
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import storage
from app.main import app

class LibraryTrashTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'EASYRESEARCH_DATA_DIR':self.temp.name})
        self.env.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.h = {'X-EasyResearch':'1'}
        self.pdf = b'%PDF-1.4\nsynthetic fixture\n%%EOF'
        digest=hashlib.sha256(self.pdf).hexdigest()
        key='files/'+digest[:2]+'/'+digest+'.pdf'
        path=Path(self.temp.name)/key
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(self.pdf)
        self.pdf_path=path
        with storage.transaction() as con:
            con.executemany('INSERT INTO projects(id,name) VALUES(?,?)',[('a','A'),('b','B')])
            con.execute('INSERT INTO files(id,sha256,size,storage_key) VALUES(?,?,?,?)',('f',digest,len(self.pdf),key))
            con.execute("INSERT INTO papers(id,file_id,title,page_count) VALUES('p','f','Paper',1)")
            con.executemany('INSERT INTO project_papers(project_id,paper_id,reading_status,last_page) VALUES(?,?,?,?)',[('a','p','reading',2),('b','p','done',0)])
            con.execute("INSERT INTO evidence(id,paper_id,page_index,quote,note) VALUES('e','p',0,'same','shared')")
            con.execute("INSERT INTO evidence_revisions(evidence_id,page_index,quote,note,prefix,suffix,status) VALUES('e',0,'old','note','','','unverified')")
    def tearDown(self):
        self.client.__exit__(None,None,None)
        self.env.stop()
        self.temp.cleanup()
    def request(self,method,path,**kwargs):
        return self.client.request(method,path,headers=self.h,**kwargs)
    def save_note(self, project, note):
        path=f'/api/projects/{project}/papers/p/note'
        revision=self.client.get(path).json()['revision']
        return self.request('PUT',path,json={'note':note,'expected_revision':revision})
    def test_project_notes_detach_trash_restore_and_file(self):
        for project,note in [('a','A private'),('b','B private')]:
            self.assertEqual(self.save_note(project,note).status_code,200)
        self.assertEqual(self.request('DELETE','/api/projects/a/papers/p').status_code,204)
        self.assertEqual(self.client.get('/api/papers?project_id=a').json(),[])
        self.assertEqual(len(self.client.get('/api/papers?project_id=b').json()),1)
        self.assertEqual(self.client.get('/api/projects/b/papers/p/note').json()['note'],'B private')
        self.assertEqual(self.client.get('/api/papers/p/evidence').json()[0]['note'],'shared')
        link=self.client.get('/api/trash').json()['links'][0]
        self.assertEqual(self.request('POST',f"/api/trash/links/{link['id']}/restore").status_code,200)
        self.assertEqual(self.client.get('/api/projects/a/papers/p/note').json()['note'],'A private')
        paper=self.client.get('/api/papers?project_id=a').json()[0]
        self.assertEqual((paper['reading_status'],paper['last_page']),('reading',2))
        self.assertEqual(self.pdf_path.read_bytes(),self.pdf)
        exported=self.client.get('/api/projects/a/export?format=json').json()
        self.assertEqual(exported['papers'][0]['project_note'],'A private')
        self.assertNotIn('B private',str(exported))
    def test_note_conflict_keeps_the_first_save_and_requires_review(self):
        path='/api/projects/a/papers/p/note'
        first=self.client.get(path).json()
        second=self.client.get(path).json()
        self.assertEqual(first['revision'],second['revision'])
        saved=self.request('PUT',path,json={'note':'창 1 메모','expected_revision':first['revision']})
        self.assertEqual(saved.status_code,200,saved.text)
        conflict=self.request('PUT',path,json={'note':'창 2 메모','expected_revision':second['revision']})
        self.assertEqual(conflict.status_code,409)
        current=self.client.get(path).json()
        self.assertEqual(current['note'],'창 1 메모')
        self.assertNotEqual(current['revision'],first['revision'])
        self.assertEqual(current['revision'],saved.json()['revision'])
        self.assertEqual(self.request('PUT',path,json={'note':'구버전 요청'}).status_code,422)
        confirmed=self.request('PUT',path,json={'note':'창 2 메모','expected_revision':current['revision']})
        self.assertEqual(confirmed.status_code,200)
        self.assertEqual(self.client.get(path).json()['note'],'창 2 메모')

    def test_selected_quote_context_survives_and_disambiguates(self):
        with storage.transaction() as con:
            con.execute("INSERT INTO pages(paper_id,page_index,text,status) VALUES('p',0,'first repeated alpha; second repeated omega','extracted')")
        response=self.request('POST','/api/papers/p/evidence',json={'page_index':0,'quote':'repeated',
            'prefix':'second','suffix':'omega','capture_method':'pdf_selection','verified_with_original':False})
        self.assertEqual(response.status_code,201,response.text)
        item=response.json()
        self.assertEqual(item['prefix'],'second')
        self.assertEqual(item['suffix'],'omega')
        loaded=next(x for x in self.client.get('/api/papers/p/evidence').json() if x['id']==item['id'])
        self.assertEqual(loaded['status'],'candidate')
        self.assertEqual(loaded['match']['candidates'][0]['start'],29)
        self.assertFalse(loaded['match']['verified'])

    def test_missing_note_and_explicit_empty_note_have_distinct_revisions(self):
        path='/api/projects/a/papers/p/note'
        missing=self.client.get(path).json()['revision']
        written=self.request('PUT',path,json={'note':'','expected_revision':missing})
        self.assertEqual(written.status_code,200)
        self.assertNotEqual(written.json()['revision'],missing)
        self.assertEqual(self.request('PUT',path,json={'note':'stale','expected_revision':missing}).status_code,409)

    def test_simultaneous_note_saves_only_one_can_succeed(self):
        path='/api/projects/a/papers/p/note'
        revision=self.client.get(path).json()['revision']
        barrier=Barrier(2)
        def write(value):
            barrier.wait(timeout=5)
            return self.request('PUT',path,json={'note':value,'expected_revision':revision}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(write,['first','second']))
        self.assertEqual(sorted(statuses),[200,409])
        self.assertIn(self.client.get(path).json()['note'],['first','second'])
    def test_project_paper_evidence_trash_recovery_preserves_history_and_files(self):
        self.assertEqual(self.request('DELETE','/api/evidence/e').status_code,204)
        self.assertEqual(self.client.get('/api/papers/p/evidence').json(),[])
        self.assertEqual(len(self.client.get('/api/evidence/e/revisions').json()),1)
        self.assertEqual(self.request('DELETE','/api/papers/p').status_code,204)
        self.assertEqual(self.request('POST','/api/trash/evidence/e/restore').status_code,409)
        self.assertEqual(self.request('POST','/api/trash/papers/p/restore').status_code,200)
        self.assertEqual(self.request('POST','/api/trash/evidence/e/restore').status_code,200)
        self.assertEqual(self.client.get('/api/papers/p/evidence').json()[0]['note'],'shared')
        self.assertEqual(self.request('DELETE','/api/projects/a').status_code,204)
        self.assertEqual([p['id'] for p in self.client.get('/api/projects').json()],['b'])
        self.assertEqual(self.request('POST','/api/trash/projects/a/restore').status_code,200)
        self.assertEqual(len(self.client.get('/api/papers?project_id=a').json()),1)
        self.assertEqual(self.pdf_path.read_bytes(),self.pdf)
    def test_pdf_versions_preserve_original_and_are_backed_up(self):
        other=b'%PDF-1.7\nother synthetic version\n%%EOF'
        response=self.request('POST','/api/papers/p/versions',data={'label':'Second version'},files={'file':('other.pdf',other,'application/pdf')})
        self.assertEqual(response.status_code,201,response.text)
        version=response.json()
        self.assertFalse(version['duplicate'])
        self.assertEqual(self.client.get(version['url']).content,other)
        self.assertEqual(self.client.get('/api/papers/p/file').content,self.pdf)
        self.assertEqual(self.client.get('/api/papers/p/evidence').json()[0]['note'],'shared')
        self.assertEqual(len(self.client.get('/api/papers/p/versions').json()['versions']),1)
        again=self.request('POST','/api/papers/p/versions',files={'file':('other.pdf',other,'application/pdf')})
        self.assertTrue(again.json()['duplicate'])
        same=self.request('POST','/api/papers/p/versions',files={'file':('same.pdf',self.pdf,'application/pdf')})
        self.assertTrue(same.json()['primary'])
        backup=self.request('POST','/api/backups').json()
        self.assertEqual(backup['file_count'],2)
        archive=self.client.get(backup['download_url']).content
        restored=self.request('POST','/api/backups/restore',files={'file':('backup.zip',archive,'application/zip')})
        self.assertEqual(restored.status_code,201,restored.text)
        self.assertEqual(restored.json()['file_count'],2)

    def test_evidence_origins_checks_and_revision_history(self):
        with storage.transaction() as con:
            con.execute("INSERT INTO pages(paper_id,page_index,text,status) VALUES('p',0,'the repeated quote and repeated quote','extracted')")
        response=self.request('POST','/api/papers/p/evidence',json={'page_index':0,'quote':'repeated quote','capture_method':'pdf_selection','verified_with_original':True})
        self.assertEqual(response.status_code,201,response.text)
        item=response.json()
        self.assertEqual((item['capture_method'],item['original_checked'],item['status']),('pdf_selection',True,'ambiguous'))
        self.assertEqual(item['file_sha256'],hashlib.sha256(self.pdf).hexdigest())
        response=self.request('PUT','/api/evidence/'+item['id'],json={'page_index':0,'quote':'missing','capture_method':'manual'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual((response.json()['status'],response.json()['original_checked']),('not_found',None))
        history=self.client.get('/api/evidence/'+item['id']+'/revisions').json()[0]
        self.assertEqual((history['capture_method'],history['original_checked']),('pdf_selection',1))
        response=self.request('POST','/api/papers/p/evidence',json={'page_index':0,'quote':'missing','capture_method':'ocr','verified_with_original':True})
        self.assertEqual(response.status_code,422)
        # Merely checking the original does not turn a manual entry into OCR.
        item=self.request('POST','/api/papers/p/evidence',json={'page_index':0,'quote':'repeated quote','verified_with_original':True}).json()
        self.assertEqual((item['capture_method'],item['source'],item['original_checked']),('manual','manual',True))

    def test_metadata_edit_and_scoped_local_search(self):
        updated=self.request('PATCH','/api/papers/p',json={'authors':['First Author','두 번째'], 'year':2024, 'doi':'https://doi.org/10.1234/ABC'})
        self.assertEqual(updated.status_code,200,updated.text)
        self.assertEqual(updated.json()['doi'],'10.1234/abc')
        self.assertEqual(updated.json()['authors'],['First Author','두 번째'])
        self.assertEqual(self.request('PATCH','/api/papers/p',json={'doi':'invalid'}).status_code,422)
        self.assertEqual(self.save_note('a','alpha project only').status_code,200)
        with storage.transaction() as con:
            con.execute("INSERT INTO pages(paper_id,page_index,text,status) VALUES('p',0,'alpha page content','extracted')")
        a=self.client.get('/api/projects/a/library-search',params={'q':'alpha'}).json()
        self.assertEqual({r['kind'] for r in a['results']},{'project_note','page'})
        self.assertEqual(a['incomplete_pages'],0)
        b=self.client.get('/api/projects/b/library-search',params={'q':'alpha'}).json()
        self.assertEqual([r['kind'] for r in b['results']],['page'])
        self.assertEqual(b['results'][0]['page_index'],0)
        self.assertEqual(self.request('PATCH','/api/papers/p',json={'year':None,'doi':None}).json()['year'],None)

    def test_restore_link_requires_project_and_paper(self):
        self.request('DELETE','/api/projects/a/papers/p')
        link=self.client.get('/api/trash').json()['links'][0]['id']
        self.request('DELETE','/api/projects/a')
        self.assertEqual(self.request('POST',f'/api/trash/links/{link}/restore').status_code,409)
        self.request('POST','/api/trash/projects/a/restore')
        self.request('DELETE','/api/papers/p')
        self.assertEqual(self.request('POST',f'/api/trash/links/{link}/restore').status_code,409)
        self.request('POST','/api/trash/papers/p/restore')
        self.assertEqual(self.request('POST',f'/api/trash/links/{link}/restore').status_code,200)

class MigrationV3Tests(unittest.TestCase):
    def test_v2_source_migrates_with_project_notes_and_provenance_intact(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'EASYRESEARCH_DATA_DIR':temp}):
            path=Path(temp)/'library.sqlite3'
            with closing(sqlite3.connect(str(path))) as con:
                con.executescript(storage.SCHEMA_V2)
                con.execute('PRAGMA user_version=2')
                con.execute("INSERT INTO projects(id,name) VALUES('p','project')")
                con.execute("INSERT INTO papers(id,title) VALUES('paper','title')")
                con.execute("INSERT INTO evidence(id,paper_id,page_index,quote) VALUES('e','paper',0,'quote')")
                con.execute("INSERT INTO evidence_provenance VALUES('e','pdf_selection',1,'hash')")
                con.execute("INSERT INTO project_paper_notes(project_id,paper_id,note) VALUES('p','paper','private')")
                con.commit()
            storage.init_db()
            with closing(sqlite3.connect(str(path))) as con:
                self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0],storage.SCHEMA_VERSION)
                self.assertEqual(con.execute('SELECT capture_method,original_checked,file_sha256 FROM evidence_provenance').fetchone(),('pdf_selection',1,'hash'))
                self.assertEqual(con.execute('SELECT note FROM project_paper_notes').fetchone()[0],'private')
                self.assertEqual(con.execute('SELECT count(*) FROM paper_versions').fetchone()[0],0)
            snapshot=list((Path(temp)/'migration-backups').glob('*.sqlite3'))
            self.assertEqual(len(snapshot),1)
            with closing(sqlite3.connect(str(snapshot[0]))) as con:
                self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0],2)

class MigrationV2Tests(unittest.TestCase):
    def test_v1_is_upgraded_with_snapshot_and_old_evidence_unchanged(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'EASYRESEARCH_DATA_DIR':temp}):
            path=Path(temp)/'library.sqlite3'
            with closing(sqlite3.connect(str(path))) as con:
                con.executescript(storage.SCHEMA_V1)
                con.execute('PRAGMA user_version=1')
                con.execute("INSERT INTO projects(id,name) VALUES('p','기존')")
                con.execute("INSERT INTO papers(id,title) VALUES('paper','기존 논문')")
                con.execute("INSERT INTO evidence(id,paper_id,page_index,quote,note) VALUES('e','paper',0,'구절','메모')")
                con.commit()
            storage.init_db()
            with closing(sqlite3.connect(str(path))) as con:
                self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0],storage.SCHEMA_VERSION)
                self.assertEqual(con.execute('SELECT quote,note FROM evidence').fetchone(),('구절','메모'))
                self.assertEqual(con.execute('SELECT count(*) FROM project_paper_notes').fetchone()[0],0)
            snapshot=list((Path(temp)/'migration-backups').glob('*.sqlite3'))
            self.assertEqual(len(snapshot),1)
            with closing(sqlite3.connect(str(snapshot[0]))) as con:
                self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0],1)
                self.assertEqual(con.execute('SELECT note FROM evidence').fetchone()[0],'메모')

if __name__=='__main__': unittest.main()

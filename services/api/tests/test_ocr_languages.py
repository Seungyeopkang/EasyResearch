"""Language isolation and deduplication for disposable local OCR jobs."""
import hashlib
import json
import os
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import jobs, main, storage
from app.pdf_processing import PDFProcessingError


@unittest.skipUnless(os.name == 'nt', 'Windows OCR endpoint is Windows-only')
class OCRLanguageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'EASYRESEARCH_DATA_DIR': self.temp.name})
        self.env.start()
        storage.init_db()
        raw = b'%PDF-1.4\nsynthetic\n%%EOF'
        sha = hashlib.sha256(raw).hexdigest()
        key = f'files/{sha[:2]}/{sha}.pdf'
        path = Path(self.temp.name) / key
        path.parent.mkdir(parents=True)
        path.write_bytes(raw)
        with storage.transaction() as con:
            con.execute("INSERT INTO files(id,sha256,size,storage_key) VALUES('f',?,?,?)", (sha,len(raw),key))
            con.execute("INSERT INTO papers(id,file_id,title,page_count) VALUES('p','f','Paper',1)")

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def request(self, language):
        return main.request_ocr('p', 0, main.OCRRequest(language=language))

    def execute(self, job_id, result=None, exception=None):
        with storage.transaction() as con:
            con.execute("UPDATE jobs SET status='running',lease_token='lease' WHERE id=?", (job_id,))
        with patch.object(jobs, 'ocr_page_windows', return_value=result, side_effect=exception):
            jobs.execute_ocr(job_id, 'lease')

    def test_concurrent_same_language_reuses_one_job_different_languages_do_not(self):
        barrier = threading.Barrier(12)
        def submit(i):
            barrier.wait()
            return self.request(['en-US', 'EN-us', 'ko'][i % 3])
        with patch.object(main.shutil, 'which', return_value='available'):
            with ThreadPoolExecutor(max_workers=12) as pool:
                results = list(pool.map(submit, range(12)))
        by_language = {language: {item['job_id'] for item in results if item['language'] == language}
                       for language in ('en-us', 'ko')}
        self.assertEqual([len(by_language[k]) for k in ('en-us', 'ko')], [1, 1])
        self.assertNotEqual(by_language['en-us'], by_language['ko'])
        self.assertEqual(sum(not item['reused'] for item in results), 2)
        with storage.transaction() as con:
            self.assertEqual(con.execute("SELECT count(*) FROM jobs WHERE kind='ocr_page'").fetchone()[0], 2)

    def test_languages_keep_separate_results_and_requested_metadata(self):
        with patch.object(main.shutil, 'which', return_value='available'):
            ko, en = self.request('ko'), self.request('en')
        for job, text, language in [(ko, '한국어 결과', 'ko-KR'), (en, 'english result', 'en-US')]:
            self.execute(job['job_id'], {'page_index': 0, 'text': text, 'language': language,
                                        'text_source': 'ocr_windows', 'status': 'ocr_unverified'})
            details = json.loads(main.get_job(job['job_id'])['detail'])
            self.assertEqual((details['page_index'], details['language']), (0, job['language']))
        listed = main.list_page_ocr_results('p', 0)
        self.assertEqual({r['language'] for r in listed['results']}, {'ko-KR', 'en-US'})
        self.assertFalse(listed['truncated'])
        self.assertEqual(main.get_ocr_result(ko['job_id'])['text'], '한국어 결과')
        self.assertEqual(main.get_ocr_result(en['job_id'])['text'], 'english result')
        self.assertEqual(main.get_page('p', 0)['ocr']['job_id'], en['job_id'])
        with patch.object(main.shutil, 'which', return_value='available'):
            retry = self.request('en')
        self.assertNotEqual(retry['job_id'], en['job_id'])
        self.assertFalse(retry['reused'])

    def test_error_does_not_masquerade_as_result_or_replace_old_language(self):
        with patch.object(main.shutil, 'which', return_value='available'):
            ko, en = self.request('ko'), self.request('en')
        self.execute(ko['job_id'], {'page_index': 0, 'text': '한국어 결과', 'language': 'ko-KR',
                                    'text_source': 'ocr_windows', 'status': 'ocr_unverified'})
        self.execute(en['job_id'], exception=PDFProcessingError('language_unavailable', 'not installed'))
        self.assertEqual(main.get_job(en['job_id'])['error'], 'language_unavailable')
        self.assertEqual(main.get_job(en['job_id'])['status'], 'failed')
        self.assertEqual(main.get_page('p', 0)['ocr']['job_id'], ko['job_id'])
        self.assertEqual(len(main.list_page_ocr_results('p', 0)['results']), 1)
        with patch.object(main.shutil, 'which', return_value='available'):
            wrong = self.request('en-US')
        self.execute(wrong['job_id'], {'page_index': 0, 'text': 'wrong', 'language': 'ko-KR',
                                      'text_source': 'ocr_windows', 'status': 'ocr_unverified'})
        self.assertEqual(main.get_job(wrong['job_id'])['error'], 'language_mismatch')
        self.assertEqual(len(main.list_page_ocr_results('p', 0)['results']), 1)


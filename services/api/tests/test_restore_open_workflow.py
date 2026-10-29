"""Back up, restore and actually open a disposable library in a fresh server."""
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
import zipfile
from contextlib import closing
from unittest.mock import patch

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))
from app.main import app
from app import storage
import open_restored


def pdf_bytes():
    stream = io.BytesIO()
    page = canvas.Canvas(stream)
    page.drawString(80, 700, "evidence survives restoration")
    page.save()
    return stream.getvalue()


class RestoreOpenWorkflowTests(unittest.TestCase):
    def test_v3_restore_and_fresh_server_preserve_pdf_and_notes(self):
        headers = {'X-EasyResearch': '1'}
        with tempfile.TemporaryDirectory(prefix='easyresearch-v3-open-') as folder:
            root = Path(folder)
            raw = pdf_bytes()
            with patch.dict(os.environ, {'EASYRESEARCH_DATA_DIR': str(root)}):
                with TestClient(app) as client:
                    project = client.post('/api/projects', headers=headers, json={'name': 'v3 project'}).json()['id']
                    response = client.post('/api/papers/import', headers=headers, data={'project_id': project},
                                           files={'file': ('v3.pdf', raw, 'application/pdf')})
                    self.assertEqual(response.status_code, 201, response.text)
                    paper = response.json()['id']
                    path = f'/api/projects/{project}/papers/{paper}/note'
                    revision = client.get(path).json()['revision']
                    note = client.put(path, headers=headers, json={'note': 'project note from v3', 'expected_revision': revision})
                    self.assertEqual(note.status_code, 200, note.text)
                    evidence = client.post(f'/api/papers/{paper}/evidence', headers=headers,
                                           json={'page_index': 0, 'note': 'evidence note from v3'})
                    self.assertEqual(evidence.status_code, 201, evidence.text)
                    backup = client.post('/api/backups', headers=headers).json()
                    archive = client.get(backup['download_url']).content
                    with zipfile.ZipFile(io.BytesIO(archive)) as source:
                        entries = {name: source.read(name) for name in source.namelist()}
                    legacy_db = root / 'synthetic-v3.sqlite3'
                    legacy_db.write_bytes(entries['library.sqlite3'])
                    with closing(sqlite3.connect(str(legacy_db))) as con:
                        con.execute('DROP TABLE paper_version_trash')
                        con.execute('DROP TABLE paper_version_state')
                        con.execute('DROP TABLE revision_ocr_source')
                        con.execute('DROP TABLE evidence_ocr_source')
                        con.execute('PRAGMA user_version=3')
                        con.commit()
                    entries['library.sqlite3'] = legacy_db.read_bytes()
                    manifest = json.loads(entries['manifest.json'])
                    manifest['database_sha256'] = hashlib.sha256(entries['library.sqlite3']).hexdigest()
                    entries['manifest.json'] = json.dumps(manifest).encode()
                    data = io.BytesIO()
                    with zipfile.ZipFile(data, 'w') as z:
                        for name, content in entries.items():
                            z.writestr(name, content)
                    legacy_archive = data.getvalue()
                    archive_hash = hashlib.sha256(legacy_archive).digest()
                    inspected = client.post('/api/backups/inspect', headers=headers,
                                            files={'file': ('v3.zip', legacy_archive, 'application/zip')})
                    self.assertEqual(inspected.status_code, 200, inspected.text)
                    self.assertEqual(inspected.json()['database_version'], 3)
                    restored = client.post('/api/backups/restore', headers=headers,
                                           files={'file': ('v3.zip', legacy_archive, 'application/zip')})
                    self.assertEqual(restored.status_code, 201, restored.text)
                    restored_path = Path(restored.json()['restore_path'])
                    with closing(sqlite3.connect(str(restored_path / 'library.sqlite3'))) as con:
                        self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0], storage.SCHEMA_VERSION)
                        self.assertEqual(con.execute('SELECT note FROM project_paper_notes').fetchone()[0], 'project note from v3')
                    self.assertEqual(hashlib.sha256(legacy_archive).digest(), archive_hash)
                    self.assertEqual(client.get(path).json()['note'], 'project note from v3')

                # Exercise startup migration itself: a previously restored v3 folder
                # contains only files from our own synthetic fixture.
                older_restore = root / 'restores' / str(uuid.uuid4())
                older_restore.mkdir(parents=True)
                for name, content in entries.items():
                    if name == 'manifest.json':
                        continue
                    target = older_restore / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
                self.assertEqual(open_restored.validate_library(older_restore, root)['files'], 1)
                with socket.socket() as probe:
                    probe.bind(('127.0.0.1', 0))
                    port = probe.getsockname()[1]
                env = os.environ.copy()
                env['EASYRESEARCH_DATA_DIR'] = str(older_restore)
                process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1',
                                            '--port', str(port)], cwd=str(ROOT / 'services' / 'api'), env=env,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                def get(path):
                    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
                    try:
                        connection.request('GET', path)
                        response = connection.getresponse()
                        content = response.read()
                        self.assertEqual(response.status, 200, content[:300])
                        return content
                    finally:
                        connection.close()
                try:
                    deadline = time.monotonic() + 20
                    while True:
                        self.assertIsNone(process.poll(), 'restored v3 server exited during startup')
                        try:
                            get('/api/health')
                            break
                        except OSError:
                            if time.monotonic() > deadline:
                                self.fail('restored v3 server did not start')
                            time.sleep(0.1)
                    self.assertEqual(json.loads(get(path))['note'], 'project note from v3')
                    self.assertEqual(json.loads(get(f'/api/papers/{paper}/evidence'))[0]['note'], 'evidence note from v3')
                    self.assertEqual(get(f'/api/papers/{paper}/file'), raw)
                    with closing(sqlite3.connect(str(older_restore / 'library.sqlite3'))) as con:
                        self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0], storage.SCHEMA_VERSION)
                    snapshots = list((older_restore / 'migration-backups').glob('*.sqlite3'))
                    self.assertEqual(len(snapshots), 1)
                    with closing(sqlite3.connect(str(snapshots[0]))) as con:
                        self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0], 3)
                        self.assertEqual(con.execute('SELECT note FROM project_paper_notes').fetchone()[0], 'project note from v3')
                    self.assertEqual(legacy_db.read_bytes(), entries['library.sqlite3'])
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()

    def test_restore_is_opened_by_a_fresh_server_without_changing_original(self):
        headers = {"X-EasyResearch": "1"}
        with tempfile.TemporaryDirectory(prefix="easyresearch-restore-open-") as folder:
            root = Path(folder)
            with patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": str(root)}):
                with TestClient(app) as client:
                    project = client.post("/api/projects", json={"name": "원본 프로젝트"}, headers=headers).json()["id"]
                    raw = pdf_bytes()
                    result = client.post("/api/papers/import", data={"project_id": project},
                                         files={"file": ("test.pdf", raw, "application/pdf")}, headers=headers)
                    self.assertEqual(result.status_code, 201, result.text)
                    paper = result.json()["id"]
                    evidence = client.post(f"/api/papers/{paper}/evidence", headers=headers,
                                           json={"page_index": 0, "note": "복원할 개인 메모"})
                    self.assertEqual(evidence.status_code, 201, evidence.text)
                    backup = client.post("/api/backups", headers=headers)
                    self.assertEqual(backup.status_code, 201, backup.text)
                    archive = client.get(backup.json()["download_url"]).content
                    preview = client.post("/api/backups/inspect", headers=headers,
                                          files={"file": ("backup.zip", archive, "application/zip")})
                    self.assertEqual(preview.status_code, 200, preview.text)
                    self.assertEqual(preview.json()["evidence_count"], 1)
                    restore = client.post("/api/backups/restore", headers=headers,
                                          files={"file": ("backup.zip", archive, "application/zip")})
                    self.assertEqual(restore.status_code, 201, restore.text)
                    restored = Path(restore.json()["restore_path"])
                    self.assertNotEqual(restored, root)
                    self.assertEqual(open_restored.validate_library(restored, root)["files"], 1)
                    original_papers = client.get("/api/papers", params={"project_id": project}).json()
                    self.assertEqual(len(original_papers), 1)

                # A new process uses only the restored data directory and its own
                # OS lock. It never opens or modifies the original library.
                with socket.socket() as probe:
                    probe.bind(("127.0.0.1", 0))
                    port = probe.getsockname()[1]
                env = os.environ.copy()
                env["EASYRESEARCH_DATA_DIR"] = str(restored)
                process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
                                            "--host", "127.0.0.1", "--port", str(port)],
                                           cwd=str(ROOT / "services" / "api"), env=env,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    deadline = time.monotonic() + 20
                    while True:
                        if process.poll() is not None:
                            self.fail("restored server exited during startup")
                        try:
                            con = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
                            con.request("GET", "/api/health")
                            response = con.getresponse()
                            response.read()
                            con.close()
                            if response.status == 200:
                                break
                        except OSError:
                            pass
                        if time.monotonic() > deadline:
                            self.fail("restored server did not start")
                        time.sleep(0.1)

                    def get(path):
                        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                        try:
                            connection.request("GET", path)
                            response = connection.getresponse()
                            content = response.read()
                            self.assertEqual(response.status, 200, content[:300])
                            return content
                        finally:
                            connection.close()

                    self.assertEqual(json.loads(get("/api/projects"))[0]["name"], "원본 프로젝트")
                    self.assertEqual(json.loads(get(f"/api/papers/{paper}/evidence"))[0]["note"], "복원할 개인 메모")
                    self.assertEqual(hashlib.sha256(get(f"/api/papers/{paper}/file")).digest(),
                                     hashlib.sha256(raw).digest())
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()


if __name__ == "__main__":
    unittest.main()

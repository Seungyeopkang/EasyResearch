"""Database version guard tests use isolated, disposable SQLite files."""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import storage


class SchemaVersionGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        env = patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": self.temporary.name})
        env.start()
        self.addCleanup(env.stop)
        self.database = Path(self.temporary.name) / "library.sqlite3"

    def test_new_database_is_initialized_as_current_version(self):
        storage.init_db()
        with sqlite3.connect(str(self.database)) as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], storage.SCHEMA_VERSION)
            self.assertIsNotNone(con.execute("SELECT name FROM sqlite_master WHERE name='projects'").fetchone())

    def test_existing_v1_and_its_data_survive_reinitialization(self):
        storage.init_db()
        with sqlite3.connect(str(self.database)) as con:
            con.execute("INSERT INTO projects(id, name) VALUES (?, ?)", ("project", "Existing"))
        storage.init_db()
        with sqlite3.connect(str(self.database)) as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], storage.SCHEMA_VERSION)
            self.assertEqual(con.execute("SELECT name FROM projects WHERE id='project'").fetchone()[0], "Existing")

    def test_unversioned_compatible_database_keeps_its_existing_data(self):
        with sqlite3.connect(str(self.database)) as con:
            con.executescript(storage.SCHEMA)
            con.execute("INSERT INTO projects(id, name) VALUES (?, ?)", ("old", "Unversioned"))
            con.execute("CREATE TABLE extra_data (content TEXT)")
            con.execute("INSERT INTO extra_data VALUES ('keep')")
        storage.init_db()
        with sqlite3.connect(str(self.database)) as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], storage.SCHEMA_VERSION)
            self.assertEqual(con.execute("SELECT name FROM projects WHERE id='old'").fetchone()[0], "Unversioned")
            self.assertEqual(con.execute("SELECT content FROM extra_data").fetchone()[0], "keep")

    def make_unversioned_v1(self):
        with sqlite3.connect(str(self.database)) as con:
            con.executescript(storage.SCHEMA_V1)
            con.execute("INSERT INTO projects(id, name) VALUES ('p', '기록 보존')")

    def test_unknown_unversioned_database_is_rejected_without_changes(self):
        with sqlite3.connect(str(self.database)) as con:
            con.execute("CREATE TABLE unrelated(value TEXT)")
            con.execute("INSERT INTO unrelated VALUES ('keep')")
        original = self.database.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "구조"):
            storage.init_db()
        self.assertEqual(self.database.read_bytes(), original)

    def test_migration_snapshot_and_user_data_preserved(self):
        self.make_unversioned_v1()
        storage.init_db()
        backups = list((Path(self.temporary.name) / "migration-backups").glob("*.sqlite3"))
        self.assertEqual(len(backups), 1)
        with sqlite3.connect(str(backups[0])) as snapshot:
            self.assertEqual(snapshot.execute("PRAGMA user_version").fetchone()[0], 0)
            self.assertEqual(snapshot.execute("SELECT name FROM projects").fetchone()[0], "기록 보존")
        with sqlite3.connect(str(self.database)) as live:
            self.assertEqual(live.execute("PRAGMA user_version").fetchone()[0], storage.SCHEMA_VERSION)
            self.assertEqual(live.execute("SELECT name FROM projects").fetchone()[0], "기록 보존")

    def test_failure_rolls_back_mutations_and_keeps_snapshot(self):
        self.make_unversioned_v1()
        def fail(con):
            con.execute("UPDATE projects SET name='변경되어서는 안 됨'")
            raise RuntimeError("test migration failure")
        with patch.dict(storage.MIGRATIONS, {0: fail}):
            with self.assertRaisesRegex(RuntimeError, "test migration failure"):
                storage.init_db()
        with sqlite3.connect(str(self.database)) as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 0)
            self.assertEqual(con.execute("SELECT name FROM projects").fetchone()[0], "기록 보존")
        self.assertEqual(len(list((Path(self.temporary.name) / "migration-backups").glob("*.sqlite3"))), 1)

    def test_copy_migration_preserves_source_and_refuses_existing_destination(self):
        self.make_unversioned_v1()
        original = self.database.read_bytes()
        dest = Path(self.temporary.name) / "staging" / "migrated.sqlite3"
        result = storage.migrate_database_copy(self.database, dest)
        self.assertEqual(result, {"source_version": 0, "target_version": storage.SCHEMA_VERSION, "requires_migration": True})
        self.assertEqual(self.database.read_bytes(), original)
        with sqlite3.connect(str(dest)) as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], storage.SCHEMA_VERSION)
            self.assertEqual(con.execute("SELECT name FROM projects").fetchone()[0], "기록 보존")
        dest_bytes = dest.read_bytes()
        with self.assertRaises(FileExistsError):
            storage.migrate_database_copy(self.database, dest)
        self.assertEqual(dest.read_bytes(), dest_bytes)
        self.assertEqual(self.database.read_bytes(), original)

    def test_copy_migration_failure_removes_only_new_destination(self):
        self.make_unversioned_v1()
        original = self.database.read_bytes()
        dest = Path(self.temporary.name) / "staging" / "migrated.sqlite3"
        def fail(con):
            con.execute("UPDATE projects SET name='bad'")
            raise RuntimeError("migration failed")
        with patch.dict(storage.MIGRATIONS, {0: fail}):
            with self.assertRaisesRegex(RuntimeError, "migration failed"):
                storage.migrate_database_copy(self.database, dest)
        self.assertFalse(dest.exists())
        self.assertEqual(self.database.read_bytes(), original)

    def test_v1_to_future_step_is_atomic_and_version_checked(self):
        storage.init_db()
        with sqlite3.connect(str(self.database)) as con:
            con.execute("INSERT INTO projects(id, name) VALUES ('p', '기록 보존')")
        schema2 = storage.SCHEMA + "\nCREATE TABLE added (id TEXT PRIMARY KEY);\n"
        def upgrade(con):
            con.execute("CREATE TABLE added (id TEXT PRIMARY KEY)")
        next_version = storage.SCHEMA_VERSION + 1
        with patch.object(storage, "SCHEMA_VERSION", next_version), patch.dict(storage.SCHEMAS, {next_version: schema2}), patch.dict(storage.MIGRATIONS, {next_version - 1: upgrade}):
            storage.init_db()
        with sqlite3.connect(str(self.database)) as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], next_version)
            self.assertEqual(con.execute("SELECT name FROM projects").fetchone()[0], "기록 보존")
            self.assertIsNotNone(con.execute("SELECT name FROM sqlite_master WHERE name='added'").fetchone())
        backups = list((Path(self.temporary.name) / "migration-backups").glob("*.sqlite3"))
        self.assertEqual(len(backups), 1)
        with sqlite3.connect(str(backups[0])) as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], storage.SCHEMA_VERSION)

    def test_snapshot_failure_leaves_original_untouched(self):
        self.make_unversioned_v1()
        original = self.database.read_bytes()
        with patch.object(storage, "_copy_database", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                storage.init_db()
        self.assertEqual(self.database.read_bytes(), original)

    def test_invalid_new_schema_rolls_back_all_version_steps(self):
        storage.init_db()
        with sqlite3.connect(str(self.database)) as con:
            con.execute("INSERT INTO projects(id, name) VALUES ('p', '기록 보존')")
        schema2 = storage.SCHEMA + "\nCREATE TABLE expected(id TEXT PRIMARY KEY);\n"
        def bad_upgrade(con):
            con.execute("UPDATE projects SET name='bad'")
            con.execute("CREATE TABLE unexpected(id TEXT PRIMARY KEY)")
        next_version = storage.SCHEMA_VERSION + 1
        with patch.object(storage, "SCHEMA_VERSION", next_version), patch.dict(storage.SCHEMAS, {next_version: schema2}), patch.dict(storage.MIGRATIONS, {next_version - 1: bad_upgrade}):
            with self.assertRaisesRegex(RuntimeError, "구조"):
                storage.init_db()
        with sqlite3.connect(str(self.database)) as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], storage.SCHEMA_VERSION)
            self.assertEqual(con.execute("SELECT name FROM projects").fetchone()[0], "기록 보존")
            self.assertIsNone(con.execute("SELECT name FROM sqlite_master WHERE name='unexpected'").fetchone())

    def test_future_version_copy_does_not_create_destination(self):
        with sqlite3.connect(str(self.database)) as con:
            con.execute("CREATE TABLE records(value TEXT)")
            con.execute("PRAGMA user_version=9")
        original = self.database.read_bytes()
        dest = Path(self.temporary.name) / "copy.sqlite3"
        with self.assertRaisesRegex(RuntimeError, "데이터 버전"):
            storage.migrate_database_copy(self.database, dest)
        self.assertFalse(dest.exists())
        self.assertEqual(self.database.read_bytes(), original)

    def test_invalid_foreign_key_blocks_migration(self):
        self.make_unversioned_v1()
        with sqlite3.connect(str(self.database)) as con:
            con.execute("INSERT INTO project_papers(project_id,paper_id) VALUES ('missing','missing')")
        original = self.database.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "연결 관계"):
            storage.init_db()
        self.assertEqual(self.database.read_bytes(), original)

    def test_future_database_is_rejected_without_modification(self):
        future_version = storage.SCHEMA_VERSION + 1
        with sqlite3.connect(str(self.database)) as con:
            con.execute("CREATE TABLE future_records (content TEXT NOT NULL)")
            con.execute("INSERT INTO future_records VALUES ('preserve me')")
            con.execute(f"PRAGMA user_version={future_version}")
        original = self.database.read_bytes()
        with self.assertRaisesRegex(RuntimeError, rf"데이터 버전\({future_version}\)"):
            storage.init_db()
        self.assertEqual(self.database.read_bytes(), original)
        with sqlite3.connect(str(self.database)) as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], future_version)
            self.assertEqual(con.execute("SELECT content FROM future_records").fetchone()[0], "preserve me")
            self.assertEqual(con.execute("PRAGMA journal_mode").fetchone()[0], "delete")
            self.assertIsNone(con.execute("SELECT name FROM sqlite_master WHERE name='projects'").fetchone())

    def test_future_version_in_uncheckpointed_wal_is_rejected(self):
        # Keep a writer open so its committed version remains in the WAL.
        con = sqlite3.connect(str(self.database))
        self.addCleanup(con.close)
        self.assertEqual(con.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
        con.execute("PRAGMA wal_autocheckpoint=0")
        con.execute("CREATE TABLE future_records (content TEXT)")
        con.execute("INSERT INTO future_records VALUES ('in wal')")
        con.execute("PRAGMA user_version=9")
        con.commit()
        wal = Path(str(self.database) + "-wal")
        original_db, original_wal = self.database.read_bytes(), wal.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "데이터 버전\\(9\\)"):
            storage.init_db()
        self.assertEqual(self.database.read_bytes(), original_db)
        self.assertEqual(wal.read_bytes(), original_wal)
        self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 9)
        self.assertEqual(con.execute("SELECT content FROM future_records").fetchone()[0], "in wal")


if __name__ == "__main__":
    unittest.main()

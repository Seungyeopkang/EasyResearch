"""Database version guard tests use isolated, disposable SQLite files."""
import json
import os
import sqlite3
from contextlib import closing
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
        with closing(sqlite3.connect(str(self.database))) as con, con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], storage.SCHEMA_VERSION)
            self.assertIsNotNone(con.execute("SELECT name FROM sqlite_master WHERE name='projects'").fetchone())

    def test_existing_v1_and_its_data_survive_reinitialization(self):
        storage.init_db()
        with closing(sqlite3.connect(str(self.database))) as con, con:
            con.execute("INSERT INTO projects(id, name) VALUES (?, ?)", ("project", "Existing"))
        storage.init_db()
        with closing(sqlite3.connect(str(self.database))) as con, con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], storage.SCHEMA_VERSION)
            self.assertEqual(con.execute("SELECT name FROM projects WHERE id='project'").fetchone()[0], "Existing")

    def test_unversioned_compatible_database_keeps_its_existing_data(self):
        with closing(sqlite3.connect(str(self.database))) as con, con:
            con.executescript(storage.SCHEMA)
            con.execute("INSERT INTO projects(id, name) VALUES (?, ?)", ("old", "Unversioned"))
            con.execute("CREATE TABLE extra_data (content TEXT)")
            con.execute("INSERT INTO extra_data VALUES ('keep')")
        storage.init_db()
        with closing(sqlite3.connect(str(self.database))) as con, con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], storage.SCHEMA_VERSION)
            self.assertEqual(con.execute("SELECT name FROM projects WHERE id='old'").fetchone()[0], "Unversioned")
            self.assertEqual(con.execute("SELECT content FROM extra_data").fetchone()[0], "keep")

    def make_unversioned_v1(self):
        with closing(sqlite3.connect(str(self.database))) as con, con:
            con.executescript(storage.SCHEMA_V1)
            con.execute("INSERT INTO projects(id, name) VALUES ('p', '기록 보존')")

    def test_unknown_unversioned_database_is_rejected_without_changes(self):
        with closing(sqlite3.connect(str(self.database))) as con, con:
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
        with closing(sqlite3.connect(str(backups[0]))) as snapshot, snapshot:
            self.assertEqual(snapshot.execute("PRAGMA user_version").fetchone()[0], 0)
            self.assertEqual(snapshot.execute("SELECT name FROM projects").fetchone()[0], "기록 보존")
        with closing(sqlite3.connect(str(self.database))) as live, live:
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
        with closing(sqlite3.connect(str(self.database))) as con, con:
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
        with closing(sqlite3.connect(str(dest))) as con, con:
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
        with closing(sqlite3.connect(str(self.database))) as con, con:
            con.execute("INSERT INTO projects(id, name) VALUES ('p', '기록 보존')")
        schema2 = storage.SCHEMA + "\nCREATE TABLE added (id TEXT PRIMARY KEY);\n"
        def upgrade(con):
            con.execute("CREATE TABLE added (id TEXT PRIMARY KEY)")
        next_version = storage.SCHEMA_VERSION + 1
        with patch.object(storage, "SCHEMA_VERSION", next_version), patch.dict(storage.SCHEMAS, {next_version: schema2}), patch.dict(storage.MIGRATIONS, {next_version - 1: upgrade}):
            storage.init_db()
        with closing(sqlite3.connect(str(self.database))) as con, con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], next_version)
            self.assertEqual(con.execute("SELECT name FROM projects").fetchone()[0], "기록 보존")
            self.assertIsNotNone(con.execute("SELECT name FROM sqlite_master WHERE name='added'").fetchone())
        backups = list((Path(self.temporary.name) / "migration-backups").glob("*.sqlite3"))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(str(backups[0]))) as con, con:
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
        with closing(sqlite3.connect(str(self.database))) as con, con:
            con.execute("INSERT INTO projects(id, name) VALUES ('p', '기록 보존')")
        schema2 = storage.SCHEMA + "\nCREATE TABLE expected(id TEXT PRIMARY KEY);\n"
        def bad_upgrade(con):
            con.execute("UPDATE projects SET name='bad'")
            con.execute("CREATE TABLE unexpected(id TEXT PRIMARY KEY)")
        next_version = storage.SCHEMA_VERSION + 1
        with patch.object(storage, "SCHEMA_VERSION", next_version), patch.dict(storage.SCHEMAS, {next_version: schema2}), patch.dict(storage.MIGRATIONS, {next_version - 1: bad_upgrade}):
            with self.assertRaisesRegex(RuntimeError, "구조"):
                storage.init_db()
        with closing(sqlite3.connect(str(self.database))) as con, con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], storage.SCHEMA_VERSION)
            self.assertEqual(con.execute("SELECT name FROM projects").fetchone()[0], "기록 보존")
            self.assertIsNone(con.execute("SELECT name FROM sqlite_master WHERE name='unexpected'").fetchone())

    def test_future_version_copy_does_not_create_destination(self):
        with closing(sqlite3.connect(str(self.database))) as con, con:
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
        with closing(sqlite3.connect(str(self.database))) as con, con:
            con.execute("INSERT INTO project_papers(project_id,paper_id) VALUES ('missing','missing')")
        original = self.database.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "연결 관계"):
            storage.init_db()
        self.assertEqual(self.database.read_bytes(), original)

    def test_future_database_is_rejected_without_modification(self):
        future_version = storage.SCHEMA_VERSION + 1
        with closing(sqlite3.connect(str(self.database))) as con, con:
            con.execute("CREATE TABLE future_records (content TEXT NOT NULL)")
            con.execute("INSERT INTO future_records VALUES ('preserve me')")
            con.execute(f"PRAGMA user_version={future_version}")
        original = self.database.read_bytes()
        with self.assertRaisesRegex(RuntimeError, rf"데이터 버전\({future_version}\)"):
            storage.init_db()
        self.assertEqual(self.database.read_bytes(), original)
        with closing(sqlite3.connect(str(self.database))) as con, con:
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


class V6MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        env = patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": self.temporary.name})
        env.start()
        self.addCleanup(env.stop)
        self.database = Path(self.temporary.name) / "library.sqlite3"

    def make_v5(self):
        with closing(sqlite3.connect(str(self.database))) as con, con:
            con.executescript(storage.SCHEMA_V5)
            con.execute("PRAGMA user_version=5")
            con.executemany("INSERT INTO projects(id,name) VALUES(?,?)", [("a", "Project A"), ("b", "Project B")])
            con.executemany("INSERT INTO papers(id,title) VALUES(?,?)", [(f"p{i}", f"Paper {i}") for i in range(1, 5)] + [("p5", "Unlinked")])
            con.executemany("INSERT INTO project_papers(project_id,paper_id,reading_status,last_page) VALUES(?,?,?,?)", [
                ("a", "p1", "read", 3), ("b", "p1", "to_read", 9),
                ("a", "p2", "on_hold", 1), ("b", "p2", "reading", 4),
                ("a", "p3", "to_read", 0), ("b", "p3", "on_hold", 0),
                ("a", "p4", "to_read", 2),
            ])

    def test_v5_to_v6_aggregates_status_and_seeds_categories_without_touching_links(self):
        self.make_v5()
        with closing(sqlite3.connect(str(self.database))) as con, con:
            links_before = con.execute("SELECT project_id,paper_id,reading_status,last_page FROM project_papers ORDER BY 1,2").fetchall()
        storage.init_db()
        with closing(sqlite3.connect(str(self.database))) as con, con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], storage.SCHEMA_VERSION)
            states = {row[0]: (row[1], row[2]) for row in con.execute("SELECT paper_id,reading_status,last_page FROM paper_reading_state")}
            self.assertEqual(states, {"p1": ("read", 9), "p2": ("reading", 4), "p3": ("on_hold", 0),
                                      "p4": ("to_read", 2), "p5": ("to_read", 0)})
            self.assertEqual(con.execute("SELECT project_id,paper_id,reading_status,last_page FROM project_papers ORDER BY 1,2").fetchall(), links_before)
            categories = {row[0]: row[1] for row in con.execute("SELECT name,keywords_json FROM categories")}
            self.assertEqual(sorted(categories), sorted(["최적화", "경량화", "컴퓨터 비전", "자연어 처리", "생성 모델", "강화학습"]))
            self.assertIn("adam", json.loads(categories["최적화"]))
            self.assertIn("pruning", json.loads(categories["경량화"]))
            self.assertEqual(con.execute("SELECT count(*) FROM paper_categories").fetchone()[0], 0)
            self.assertEqual(con.execute("SELECT count(*) FROM paper_topics").fetchone()[0], 0)
            self.assertEqual(len({row[0] for row in con.execute("SELECT id FROM categories")}), 6)
        snapshots = list((Path(self.temporary.name) / "migration-backups").glob("*.sqlite3"))
        self.assertEqual(len(snapshots), 1)
        with closing(sqlite3.connect(str(snapshots[0]))) as con, con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 5)
            self.assertIsNone(con.execute("SELECT name FROM sqlite_master WHERE name='paper_reading_state'").fetchone())
        # A later launch does not migrate again and does not duplicate the defaults.
        storage.init_db()
        with closing(sqlite3.connect(str(self.database))) as con, con:
            self.assertEqual(con.execute("SELECT count(*) FROM categories").fetchone()[0], 6)
            self.assertEqual(con.execute("SELECT count(*) FROM paper_reading_state").fetchone()[0], 5)

    def test_fresh_database_gets_only_default_categories(self):
        storage.init_db()
        with closing(sqlite3.connect(str(self.database))) as con, con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], storage.SCHEMA_VERSION)
            self.assertEqual(con.execute("SELECT count(*) FROM categories").fetchone()[0], 6)
            self.assertEqual(con.execute("SELECT count(*) FROM paper_reading_state").fetchone()[0], 0)
            self.assertEqual(con.execute("SELECT count(*) FROM paper_categories").fetchone()[0], 0)
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_v6_migration_failure_leaves_v5_library_untouched(self):
        self.make_v5()
        def fail(con):
            storage._execute_schema(con, storage.SCHEMA_V6_ADDITIONS)
            con.execute("INSERT INTO paper_reading_state(paper_id,reading_status,last_page) SELECT id,'read',9 FROM papers")
            raise RuntimeError("v6 failure")
        with patch.dict(storage.MIGRATIONS, {5: fail}):
            with self.assertRaisesRegex(RuntimeError, "v6 failure"):
                storage.init_db()
        with closing(sqlite3.connect(str(self.database))) as con, con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 5)
            self.assertIsNone(con.execute("SELECT name FROM sqlite_master WHERE name='categories'").fetchone())


if __name__ == "__main__":
    unittest.main()

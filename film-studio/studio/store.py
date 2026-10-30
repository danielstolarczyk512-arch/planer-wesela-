"""Small transactional SQLite store. No ORM or external dependencies."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock


class Store:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self.lock = RLock()
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, body TEXT NOT NULL, updated TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, shot_id TEXT NOT NULL, body TEXT NOT NULL, updated TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS personas (id TEXT PRIMARY KEY, body TEXT NOT NULL, updated TEXT NOT NULL)')
    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()
    def save_project(self, body):
        with self.lock, self.connect() as db:
            db.execute('INSERT OR REPLACE INTO projects VALUES (?,?,datetime("now"))', (body['id'], json.dumps(body, ensure_ascii=False),))
    def get_project(self, id):
        with self.connect() as db:
            r = db.execute('SELECT body FROM projects WHERE id=?', (id,)).fetchone()
        return json.loads(r['body']) if r else None
    def list_projects(self):
        with self.connect() as db:
            rows = db.execute('SELECT body FROM projects ORDER BY updated DESC').fetchall()
        return [json.loads(r['body']) for r in rows]
    def save_job(self, body):
        with self.lock, self.connect() as db:
            db.execute('INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,datetime("now"))', (body['id'], body['project_id'],body['shot_id'], json.dumps(body, ensure_ascii=False)))
    def get_job(self, id):
        with self.connect() as db:
            r=db.execute('SELECT body FROM jobs WHERE id=?',(id,)).fetchone()
        return json.loads(r['body']) if r else None
    def jobs(self, project_id):
        with self.connect() as db:
            rows=db.execute('SELECT body FROM jobs WHERE project_id=? ORDER BY updated DESC',(project_id,)).fetchall()
        return [json.loads(r['body']) for r in rows]

    def save_persona(self, body):
        with self.lock, self.connect() as db:
            db.execute('INSERT OR REPLACE INTO personas VALUES (?,?,datetime("now"))',
                       (body['id'], json.dumps(body, ensure_ascii=False)))
    def get_persona(self, id):
        with self.connect() as db:
            row=db.execute('SELECT body FROM personas WHERE id=?',(id,)).fetchone()
        return json.loads(row['body']) if row else None
    def list_personas(self):
        with self.connect() as db:
            rows=db.execute('SELECT body FROM personas ORDER BY updated DESC').fetchall()
        return [json.loads(row['body']) for row in rows]

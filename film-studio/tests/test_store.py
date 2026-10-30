import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from studio import engine
from studio.exporter import package
from studio.store import Store


class StoreTests(unittest.TestCase):
    def test_roundtrip_and_export(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'db.sqlite3')
            p=engine.new_project({'title':'Test'})
            engine.develop_demo(p)
            store.save_project(p)
            self.assertEqual(store.get_project(p['id'])['title'],'Test')
            self.assertEqual(len(store.list_projects()),1)
            job={'id':'j123','project_id':p['id'],'shot_id':'S01','status':'queued'}
            store.save_job(job)
            self.assertEqual(store.jobs(p['id'])[0]['id'],'j123')
            pack=package(p,store.jobs(p['id']))
            with ZipFile(BytesIO(pack)) as z:
                names=z.namelist()
                self.assertTrue(any(x.endswith('projekt.json') for x in names))
                self.assertTrue(any(x.endswith('scenariusz.txt') for x in names))
                self.assertTrue(any(x.endswith('edl.json') for x in names))

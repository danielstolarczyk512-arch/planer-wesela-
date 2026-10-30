"""Offline restore tool. Does not overwrite projects or preexisting files by default.
Example: python tools/restore_portable_v83.py my_backup.zip --target D:/film-studio/V8.3/Nasz_Dzien_Film_Studio_V8_3
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from studio.portable_v83 import validate_archive
from studio.store import Store


def restore(source,target,dry_run=False):
    source=Path(source);target=Path(target).resolve()
    data=source.read_bytes();details=validate_archive(data)
    db=Store(target/'data'/'v6.sqlite3')
    if db.get_project(details['project_id']):
        raise ValueError('Projekt już istnieje. Przywracanie nie nadpisuje danych.')
    if dry_run:return details
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in (entry['path'] for entry in json.loads(z.read('MANIFEST_SHA256.json'))['files']):
            rel=name[len('assets/'):];dst=(target/rel).resolve()
            if not dst.is_relative_to(target) or dst.exists():raise ValueError('Plik istnieje lub jest poza projektem: '+rel)
        for name in (entry['path'] for entry in json.loads(z.read('MANIFEST_SHA256.json'))['files']):
            rel=name[len('assets/'):];dst=target/rel;dst.parent.mkdir(parents=True,exist_ok=True)
            dst.write_bytes(z.read(name))
        state=json.loads(z.read('projekt.json'))
        p=state['project']
        for shot in p.get('shots',[]):
            for key in ('v7_audio_file',):
                val=shot.get(key)
                if isinstance(val,str) and val.startswith('data/'):
                    shot[key]=str((target/val).resolve())
            for v in shot.get('v8_voice_variants') or []:
                if isinstance(v,dict) and isinstance(v.get('file'),str) and v['file'].startswith('data/'):
                    v['file']=str((target/v['file']).resolve())
        # Never silently accept stale visual approvals on another machine.
        p['v82_visual_lock']=False
        for shot in p.get('shots',[]):
            shot.pop('v83_reference_binding',None);shot.pop('v82_frame_approval',None)
            shot.pop('v82_clip_approval',None);shot['qc_approved']=False
        db.save_project(p)
        for job in state.get('jobs',[]):
            if isinstance(job,dict) and job.get('project_id')==p['id'] and job.get('id'):
                job['status']='restored_requires_reconciliation'
                db.save_job(job)
    return details

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('zip');parser.add_argument('--target',default=str(ROOT));parser.add_argument('--dry-run',action='store_true')
    a=parser.parse_args();print(json.dumps(restore(a.zip,a.target,a.dry_run),indent=2))

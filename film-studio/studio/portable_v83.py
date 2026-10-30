"""Portable production bundle: project JSON, approved source assets, clips, audio.
No API keys and no expiring Sogni URLs. Paths are strictly inside project root.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import re
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

MAX_FILE=150*1024*1024
MAX_TOTAL=640*1024*1024
PROHIBITED=('SOGNI_API_KEY','STUDIO_ACCESS_TOKEN','Authorization','uploadUrl','downloadUrl')
PRIVATE_FIELDS={'v83_reference_binding','reference_image_urls','remote_reference_url','image_url','media_url','quote','image_quote'}

def digest(data):return hashlib.sha256(data).hexdigest()

def scrub(o):
    if isinstance(o,dict):return {k:scrub(v) for k,v in o.items() if k not in PRIVATE_FIELDS and k not in ('token','api_key','secret')}
    if isinstance(o,list):return [scrub(x) for x in o]
    if isinstance(o,str) and ('https://' in o and ('X-Amz-' in o or 'Signature=' in o)):
        return '[EXPIRED_URL_REQUIRES_REUPLOAD]'
    return o

def project_for_export(root,project):
    """Rewrite bundled local audio paths; discard unportable absolute user paths."""
    root=Path(root).resolve()
    copy=scrub(project)
    for shot in copy.get('shots',[]):
        for field in ('v7_audio_file',):
            value=shot.get(field)
            if not isinstance(value,str):continue
            try:
                local=Path(value).resolve()
                shot[field]=local.relative_to(root).as_posix() if local.is_relative_to(root) else None
            except (ValueError,OSError):shot[field]=None
        for item in shot.get('v8_voice_variants') or []:
            if not isinstance(item,dict):continue
            value=item.get('file')
            if isinstance(value,str):
                try:
                    local=Path(value).resolve()
                    item['file']=local.relative_to(root).as_posix() if local.is_relative_to(root) else None
                except (ValueError,OSError):item['file']=None
    return copy


def asset_paths(root,project,include_clips=True):
    root=Path(root).resolve();pid=project['id']
    wanted=[root/'data'/'keyframes'/pid,root/'data'/'v7_audio'/pid,
            root/'data'/'v8_voice'/pid,root/'data'/'v85_audio'/pid,root/'data'/'v7_render'/pid,root/'data'/'v7_renders'/pid,
            root/'data'/'exports'/pid,root/'data'/'master_assets_v82']
    if include_clips:wanted.append(root/'data'/'clips'/pid)
    # Keep master assets which are referenced by pinned snapshots and all
    # approved project-local stills, but no arbitrary user home folder.
    for item in (project.get('v82_visual_snapshot') or {}).values():
        if isinstance(item,dict) and isinstance(item.get('path'),str):
            p=(root/item['path']).resolve()
            if p.is_relative_to(root) and p.is_file():wanted.append(p)
    found={}
    for base in wanted:
        base=base.resolve()
        if not base.is_relative_to(root) or not base.exists():continue
        candidates=[base] if base.is_file() else base.rglob('*')
        for p in candidates:
            if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(root):continue
            if p.suffix.lower() not in ('.png','.jpg','.jpeg','.wav','.mp3','.mp4','.json','.srt') :continue
            found[p.relative_to(root).as_posix()]=p
    return found

def package(root,project,jobs,include_clips=True):
    manifest=[];total=0;out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as archive:
        for rel,p in sorted(asset_paths(root,project,include_clips).items()):
            size=p.stat().st_size
            if size>MAX_FILE:raise ValueError('Zbyt duży plik do archiwum: '+rel)
            total+=size
            if total>MAX_TOTAL:raise ValueError('Limit archiwum 640 MB: wybierz kopię bez klipów')
            data=p.read_bytes()
            if rel.endswith('.json') and any(s.encode() in data for s in PROHIBITED):
                continue # never export suspected secrets in arbitrary JSON
            archive.writestr('assets/'+rel,data)
            manifest.append({'path':'assets/'+rel,'size':len(data),'sha256':digest(data)})
        archive.writestr('projekt.json',json.dumps({'project':project_for_export(root,project),'jobs':scrub(jobs)},ensure_ascii=False,indent=2))
        archive.writestr('MANIFEST_SHA256.json',json.dumps({'version':'8.5.0','files':manifest,'contains_external_urls':False},ensure_ascii=False,indent=2))
        archive.writestr('README_IMPORT.txt','Paczka offline. Nie zawiera kluczy ani czasowych adresów Sogni. Przy przywracaniu zweryfikuj SHA256; ponownie zatwierdz wzorce i zaladuj referencje do Sogni.\n')
    return out.getvalue()


def validate_archive(data):
    """Validates portable bundle without writing ANY files."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if len(z.infolist())>3000:raise ValueError('Za dużo plików')
        info=json.loads(z.read('MANIFEST_SHA256.json'))
        if info.get('version') not in ('8.3.0','8.4.0','8.5.0'):raise ValueError('Niewłaściwa wersja')
        seen=set();size=0
        for entry in info['files']:
            name=entry['path'];parts=Path(name).parts
            if name in seen or not name.startswith('assets/') or '..' in parts or name.startswith('/') or '\\' in name:
                raise ValueError('Niedozwolona ścieżka w archiwum')
            seen.add(name);obj=z.getinfo(name)
            if obj.file_size>MAX_FILE:raise ValueError('Zbyt duży plik')
            size+=obj.file_size
            if size>MAX_TOTAL:raise ValueError('Zbyt duże archiwum')
            if obj.file_size!=entry['size'] or digest(z.read(name))!=entry['sha256']:
                raise ValueError('Uszkodzony plik '+name)
        # Reject unmanifested assets and duplicate ZIP entries, even if not extracted.
        listed=set(x['path'] for x in info['files'])
        names=[x.filename for x in z.infolist() if not x.is_dir()]
        if len(names)!=len(set(names)):raise ValueError('Duplikaty ścieżek ZIP')
        if any(n.startswith('assets/') and n not in listed for n in names):
            raise ValueError('Nieoczekiwany zasób w archiwum')
        project=json.loads(z.read('projekt.json'))['project']
        if not re.fullmatch('[0-9a-f-]{36}',project['id']):raise ValueError('Nieprawidłowy identyfikator projektu')
        return {'project_id':project['id'],'files':len(seen),'bytes':size}


PROJECT_DIRECTORIES={'keyframes','v7_audio','v8_voice','v7_render','v7_renders','v85_audio','v86_films','exports','clips'}

def restore_archive(root,db,data):
    """Offline restore AS NEW project, never resumes submitted workflows.

    Validated manifest is the only authority for extracted paths. Existing projects,
    global master images and user keys are never overwritten.
    """
    root=Path(root).resolve()
    validate_archive(data)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        obj=json.loads(z.read('projekt.json'))
        old=obj['project']['id']
        new=str(uuid.uuid4())
        while db.get_project(new):new=str(uuid.uuid4())
        project=copy.deepcopy(obj['project'])
        project['id']=new
        project['title']=str(project.get('title','Projekt'))[:160]+' [przywrócony]'
        project['restored_from_id']=old
        project['restored_offline']=True
        project['v82_visual_lock']=False
        project['v83_reference_mode']=False
        project.pop('v82_visual_snapshot',None)
        project.pop('v83_character_snapshot',None)
        project['storyboard_stale']=False
        project['shot_generation']=str(uuid.uuid4())
        # All remote links and approvals are invalid until human verification.
        for shot in project.get('shots',[]):
            for key in ('image_url','media_url','workflow_id','quote','image_quote',
                        'v82_frame_approval','v82_clip_approval','v82_synced_sha256',
                        'v83_reference_binding','v7_voice','v7_lips_approved'):
                shot.pop(key,None)
            shot['qc_approved']=False
            shot['edit_version']=str(uuid.uuid4())
            if isinstance(shot.get('v85_audio'),dict):
                # The bytes are backed up, but a restored dialogue is NOT considered
                # reviewed for the new project/version until played again.
                info=shot['v85_audio'];info['approved']=False
                info['edit_version']=shot['edit_version']
                info['path']='data/v85_audio/'+new+'/'+str(shot.get('id'))+'.wav'

            for field in ('v7_audio_file',):
                val=shot.get(field)
                if val:
                    rel=Path(val)
                    if rel.is_absolute() or '..' in rel.parts or len(rel.parts)<3 or rel.parts[0]!='data' or rel.parts[1] not in PROJECT_DIRECTORIES or rel.parts[2]!=old:
                        shot[field]=None
                    else:shot[field]='data/'+rel.parts[1]+'/'+new+'/'+'/'.join(rel.parts[3:])
            for item in shot.get('v8_voice_variants') or []:
                if not isinstance(item,dict):continue
                val=item.get('file')
                if not isinstance(val,str):continue
                rel=Path(val)
                if rel.is_absolute() or '..' in rel.parts or len(rel.parts)<4 or rel.parts[:3]!=('data','v8_voice',old):
                    item['file']=None
                else:item['file']='data/v8_voice/'+new+'/'+'/'.join(rel.parts[3:])
        assets=[];ignored=[]
        manifest=json.loads(z.read('MANIFEST_SHA256.json'))
        for row in manifest['files']:
            rel=Path(row['path'])
            parts=rel.parts
            # An allowlist prevents ZIP-slip and any master-key replacement.
            if len(parts)<5 or parts[0]!='assets' or parts[1]!='data' or parts[2] not in PROJECT_DIRECTORIES or parts[3]!=old:
                ignored.append(row['path']);continue
            dst=root/'data'/parts[2]/new/Path(*parts[4:])
            if not dst.resolve().is_relative_to(root):raise ValueError('Nieprawidłowa ścieżka')
            assets.append((row['path'],dst))
        # Create assets in a private temp staging tree; only then install.
        stage=Path(tempfile.mkdtemp(prefix='restore_v84_',dir=root))
        installed=[]
        try:
            for name,dst in assets:
                partial=stage/dst.relative_to(root)
                partial.parent.mkdir(parents=True,exist_ok=True)
                partial.write_bytes(z.read(name))
            for _,dst in assets:
                partial=stage/dst.relative_to(root)
                dst.parent.mkdir(parents=True,exist_ok=True)
                if dst.exists():raise ValueError('Docelowy plik już istnieje')
                partial.replace(dst);installed.append(dst)
            # Historical provider jobs are NOT imported as executable queue entries.
            project['imported_job_history']=[{'shot_id':j.get('shot_id'),'kind':j.get('kind'),
              'status':j.get('status'),'note':'Historyczne zadanie; nie ponawiaj automatycznie'}
              for j in obj.get('jobs',[]) if isinstance(j,dict)][:500]
            db.save_project(project)
        except Exception:
            for path in installed:path.unlink(missing_ok=True)
            raise
        finally:
            shutil.rmtree(stage,ignore_errors=True)
    return {'project_id':new,'restored_asset_count':len(assets),
            'ignored_shared_assets':ignored,
            'remote_jobs_resumed':False,'requires_visual_reapproval':True,
            'message':'Projekt przywrócony jako nowa kopia; zatwierdź wzorce, klatki i dialogi.'}

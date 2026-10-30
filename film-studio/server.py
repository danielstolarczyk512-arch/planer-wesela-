#!/usr/bin/env python3
"""Nasz Dzień Film Studio v4: local-first production with QC gates."""
import argparse
import json
import mimetypes
import os
import re
import secrets
import shutil
import sys
import traceback
import uuid
import zipfile
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from director.story import apply_director_v4
from product.screen_capture import provenance
from qc.continuity_v85 import contact_sheet
from qc.lips_v7 import inspect_mouth
from qc.motion_v8 import inspect_motion
from qc.story import audit as story_audit
from qc.video import inspect_shot
from studio import (
    ai,
    camera360,
    camera360_cli,
    character_bible_v83,
    cinematic_v7,
    dialogue_v7,
    engine,
    exporter,
    jobs_v84,
    pace_v8,
    personas,
    portable_v83,
    product_demo_v8,
    quality_v85,
    reference_v6,
    reference_v83,
    rendered_inspector_v86,
    sogni,
    story_director_v84,
    style_guide,
    timeline_v85,
    visual_lock_v82,
    voice_cli_v7,
    voice_v8,
)
from studio.store import Store

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/'web'
ID=r'([0-9a-f]{8}-[0-9a-f-]{27,36})'
SID=r'(S\d{2})'

class ApiError(Exception):
    def __init__(self,msg,status=400):super().__init__(msg);self.status=status

class Handler(BaseHTTPRequestHandler):
    server_version='NaszDzienFilmStudio/8.6'
    def log_message(self,format,*args):
        # Do not log request bodies, API keys, or authorization headers.
        sys.stderr.write('[studio] '+format%args+'\n')
    @property
    def db(self):return self.server.db
    def send_json(self,obj,code=200):
        data=json.dumps(obj,ensure_ascii=False,default=str).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers();self.wfile.write(data)
    def send_bytes(self,data,content_type='application/octet-stream',filename=None):
        self.send_response(200);self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        if filename:self.send_header('Content-Disposition','attachment; filename="'+filename+'"')
        self.end_headers();self.wfile.write(data)
    def read_json(self):
        try:size=int(self.headers.get('Content-Length','0'))
        except ValueError:raise ApiError('Nieprawidłowy nagłówek Content-Length')
        if size<0 or size>150000:raise ApiError('Maksymalny rozmiar żądania: 150 kB',413)
        try:parsed=json.loads(self.rfile.read(size) or b'{}')
        except (ValueError,UnicodeDecodeError):raise ApiError('Żądanie musi zawierać prawidłowy JSON')
        if not isinstance(parsed,dict):raise ApiError('Oczekiwano obiektu JSON')
        return parsed
    def require_auth(self):
        token=self.server.access_token
        if token and not secrets.compare_digest(self.headers.get('X-Studio-Token',''),token):raise ApiError('Wymagane hasło dostępu do studia',401)
    def get_project(self,id):
        p=self.db.get_project(id)
        if not p:raise ApiError('Nie znaleziono projektu',404)
        return p
    def clip_current(self,project,shot):
        folder=ROOT/'data'/'clips'/project['id']
        clip=folder/(shot['id']+'.mp4')
        meta=folder/(shot['id']+'.meta.json')
        if not clip.is_file() or not meta.is_file():return False
        try:
            info=json.loads(meta.read_text(encoding='utf8'))
            return (info.get('shot_generation')==project.get('shot_generation') and
                    info.get('edit_version')==shot.get('edit_version'))
        except (ValueError,OSError):return False
    def route(self,method):
        path=urlparse(self.path).path
        if not path.startswith('/api/'):
            if method!='GET':raise ApiError('Metoda nie jest obsługiwana',405)
            return self.serve_static(path)
        if path=='/api/health' and method=='GET':return self.send_json({'ok':True,'version':'8.6.0','mode':'local','billing_mode':'subscription_only','extra_api_cost_allowed':False,'sogni_key_configured':bool(sogni.key()),'protected':bool(self.server.access_token),'live_sogni_connection_tested':False,'camera360':'coverage_and_single_angle' ,'dialogue_v7':'audio_first_lipsync_with_review_gate','character_v6':'curated_checkpoint','voice_v8':'local_optional_chatterbox','pace_v8':'offline_editorial_review','visual_lock_v82':'manual_master_and_keyframe_gate','v83':'longform_reference_image_edit_portable_backup','v86':'uncle_original_references_and_rendered_film_inspector'})
        self.require_auth()
        # V8.6 local-only character extension and analysis of *actual* rendered MP4.
        if path=='/api/v86' and method=='GET':
            rows=[r for r in reference_v6.entries() if r['category']=='WUJEK']
            person=self.db.get_persona(personas.BOGUS_ID)
            return self.send_json({'version':'8.6.0',
              'uncle':{'persona_id':personas.BOGUS_ID,'name':person.get('name') if person else 'Boguś',
                'reference_count':len(rows),'approved_count':sum(x['review']=='approved' for x in rows),
                'requires_review':True, 'portrait_id':'WUJEK__PORTRAIT',
                'example_shot_roles':['ONA','ON','WUJEK']},
              'film_inspector':'ffmpeg_offline_actual_mp4','no_sogni_requests':True,
              'quality_limits':'no visual identity recognition or phoneme sync verification'})
        film_match=re.fullmatch('/api/v86/projects/'+ID+'/film',path)
        if film_match:
            pid=film_match.group(1);project=self.get_project(pid)
            dst=rendered_inspector_v86.movie_file(ROOT,pid)
            if method=='GET':
                if not dst.is_file():return self.send_json({'uploaded':False,'project_id':pid})
                try:
                    import hashlib
                    h=hashlib.sha256(dst.read_bytes()).hexdigest()
                    report=rendered_inspector_v86.inspect(dst, sum(float(sh.get('duration') or 0) for sh in project.get('shots',[])))
                except ValueError as exc:raise ApiError(str(exc),409) from None
                return self.send_json({'uploaded':True,'sha256':h,'project_id':pid,'report':report})
            if method=='PUT':
                if self.headers.get('Content-Type','').split(';')[0] not in ('video/mp4','application/mp4'):
                    raise ApiError('Prześlij prawdziwy plik MP4',415)
                try:n=int(self.headers.get('Content-Length','0'))
                except ValueError:raise ApiError('Nieprawidłowy rozmiar MP4',400)
                if n<1024 or n>rendered_inspector_v86.MAX_SIZE:
                    raise ApiError('Rozmiar MP4: maksymalnie 200 MB',413)
                if self.headers.get('X-Film-Review-Consent')!='true':
                    raise ApiError('Potwierdź lokalny import MP4 do audytu',403)
                import hashlib
                import tempfile
                dst.parent.mkdir(parents=True,exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=dst.parent,suffix='.mp4',delete=False) as f:
                    temp=Path(f.name); left=n;hasher=hashlib.sha256()
                    while left>0:
                        block=self.rfile.read(min(left,1024*1024))
                        if not block:break
                        f.write(block);hasher.update(block);left-=len(block)
                try:
                    if left:raise ValueError('Plik przesłany niekompletnie')
                    report=rendered_inspector_v86.inspect(temp,sum(float(sh.get('duration') or 0) for sh in project.get('shots',[])))
                    os.replace(temp,dst)
                except (ValueError,OSError) as exc:
                    temp.unlink(missing_ok=True);raise ApiError(str(exc),409) from None
                return self.send_json({'uploaded':True,'project_id':pid,'sha256':hasher.hexdigest(),
                    'report':report,'note':'Lokalny audyt techniczny; nie potwierdza wyglądu i mowy'},201)
        # V8.5: local-only editorial QA, user-approved speech, and master continuity review.
        if path=='/api/v85' and method=='GET':
            return self.send_json({'version':'8.5.0','master_style':visual_lock_v82.summary(ROOT)['slots']['style'],
                'new_master_image':'assets/style/MASTER_GOLDEN_STORYBOOK_V85.png',
                'audio_mix':'opt_in_human_approved_wav','subtitle_format':'srt_from_audio_timing',
                'visual_similarity_auto_verified':False,'sogni_operations_triggered':False})
        v85=re.fullmatch('/api/v85/projects/'+ID+'(?:/(review|config|subtitles)|/shots/'+SID+'/(audio|audio-approve|contact-sheet))?',path)
        if v85:
            pid,action,sid,shot_action=v85.groups();project=self.get_project(pid)
            if action=='review' and method=='GET':
                return self.send_json(quality_v85.review(ROOT,project))
            if action=='subtitles' and method=='GET':
                try:
                    cue_list=timeline_v85.cues(ROOT,project,require_approved=True)
                    content=timeline_v85.srt_from_cues(cue_list,timeline_v85.project_duration(project))
                except ValueError as exc:raise ApiError(str(exc),409) from None
                return self.send_bytes(content.encode('utf8'),'text/plain; charset=utf-8','nasz_dzien_subtitles_v85.srt')
            if action=='config' and method=='POST':
                b=self.read_json()
                if b.get('approve') is not True:raise ApiError('Potwierdź zmianę sposobu montażu',403)
                if not isinstance(b.get('enabled'),bool) or not isinstance(b.get('replace_clip_audio'),bool):
                    raise ApiError('Podaj enabled i replace_clip_audio jako true/false',400)
                project['v85_audio_mix']={'enabled':b['enabled'],
                      'replace_clip_audio':b['replace_clip_audio'], 'subtitles':bool(b.get('subtitles',True))}
                self.db.save_project(project)
                return self.send_json({'config':project['v85_audio_mix'],'review':quality_v85.review(ROOT,project)})
            if sid and shot_action:
                shot=next((x for x in project.get('shots',[]) if x.get('id')==sid),None)
                if not shot:raise ApiError('Ujęcie nie istnieje',404)
                if shot_action=='contact-sheet' and method=='GET':
                    clip=ROOT/'data'/'clips'/pid/(sid+'.mp4')
                    if not clip.is_file():raise ApiError('Najpierw wgraj klip MP4',404)
                    try:im=contact_sheet(visual_lock_v82.safe_file(ROOT,visual_lock_v82.summary(ROOT)['slots']['style']['path']),clip)
                    except (ValueError,RuntimeError,OSError) as e:raise ApiError(str(e),409) from None
                    return self.send_bytes(im,'image/png')
                if shot_action=='audio' and method=='GET':
                    file=timeline_v85.safe_audio(ROOT,pid,sid)
                    if not file.is_file():raise ApiError('Brak nagrania',404)
                    return self.send_bytes(file.read_bytes(),'audio/wav')
                if shot_action=='audio' and method=='PUT':
                    if self.headers.get('Content-Type','').split(';')[0] not in ('audio/wav','audio/x-wav','audio/wave'):
                        raise ApiError('Wymagany plik WAV PCM',415)
                    try:size=int(self.headers.get('Content-Length','0'))
                    except ValueError:raise ApiError('Brak Content-Length',400)
                    if not 1024<=size<=25*1024*1024:raise ApiError('WAV 1 KB–25 MB',413)
                    data=self.rfile.read(size)
                    if len(data)!=size:raise ApiError('Niekompletne nagranie',400)
                    offset=parse_qs(urlparse(self.path).query).get('offset',['0'])[0]
                    try:info=timeline_v85.add_audio(ROOT,project,shot,data,float(offset))
                    except (ValueError,RuntimeError,OSError) as e:raise ApiError(str(e),409) from None
                    self.db.save_project(project)
                    return self.send_json({'audio':info,'message':'Nagranie dodane. Odsłuchaj przed zatwierdzeniem.'},201)
                if shot_action=='audio-approve' and method=='POST':
                    b=self.read_json()
                    try:info=timeline_v85.approve_audio(ROOT,project,shot,str(b.get('sha256','')),b.get('heard') is True)
                    except ValueError as e:raise ApiError(str(e),409) from None
                    # Share the SAME approved WAV with the pre-existing V7
                    # audio-driven lip-sync workflow. No external generation here.
                    file=timeline_v85.safe_audio(ROOT,pid,sid)
                    if shot.get('mode')=='t2v':
                        speaker=shot.get('speaker')
                        if speaker in ('ONA','ON','WUJEK') and speaker not in (shot.get('characters') or []):
                            shot['characters']=list(dict.fromkeys((shot.get('characters') or [])+[speaker]))
                        shot['v7_audio_file']=str(file)
                        shot['v7_audio_meta']=dialogue_v7.audio_probe(file)
                    self.db.save_project(project)
                    return self.send_json({'audio':info,'approved':True,
                        'next':'W Reżyserze V7 zaplanuj voice-plan na tym samym WAV, następnie wygeneruj i ręcznie sprawdź lip-sync.'})
        # V8.4: offline story / continuity / render planning and safe restore.
        if path=='/api/v84' and method=='GET':
            return self.send_json({'version':'8.4.0','story_dialogues':True,'restore_as_new_project':True,
              'offline_render_budget':True,'remote_generation_auto_resume':False,
              'lip_sync_auto_verified':False,'cost_unknown_until_sogni_account_test':True})
        if path=='/api/v84/restore' and method=='POST':
            if self.headers.get('X-Restore-Approved')!='true':
                raise ApiError('Wymagana jawna zgoda na lokalny import ZIP',403)
            if self.headers.get('Content-Type','').split(';')[0]!='application/zip':
                raise ApiError('Wymagany plik ZIP',415)
            try:size=int(self.headers.get('Content-Length','0'))
            except ValueError:raise ApiError('Nieprawidłowa długość pliku',400)
            if not 100<size<=portable_v83.MAX_TOTAL+8*1024*1024:
                raise ApiError('Rozmiar ZIP przekracza limit',413)
            data=self.rfile.read(size)
            if len(data)!=size:raise ApiError('Niekompletne archiwum',400)
            try:result=portable_v83.restore_archive(ROOT,self.db,data)
            except (ValueError,KeyError,zipfile.BadZipFile) as e:
                raise ApiError('Odmowa przywrócenia: '+str(e),409) from None
            return self.send_json(result,201)
        v84=re.fullmatch('/api/v84/projects/'+ID+'/(story-review|render-plan|continuity)',path)
        if v84 and method=='GET':
            pid,action=v84.groups();project=self.get_project(pid)
            if action=='story-review':return self.send_json(story_director_v84.review_story(project))
            if action=='render-plan':return self.send_json(story_director_v84.render_plan(project,self.db.jobs(pid)))
            if action=='continuity':return self.send_json(story_director_v84.continuity_report(project))
        # V8.3: new projects can explicitly enable reference-guided keyframes.
        # The GET endpoints are local-only and never call Sogni.
        if path=='/api/v83' and method=='GET':
            return self.send_json({'version':'8.3.0','max_duration_seconds':180,
                'image_edit_model':'krea-identity-edit','cost_estimate':'offline_only_no_live_quote',
                'live_image_edit_eligibility':'unverified_until_account_test',
                'generations_on_request_only':True})
        v83=re.fullmatch('/api/v83/projects/'+ID+'(?:/(mode|bible|jobs|backup)|/shots/'+SID+'/(references|upload-references))?',path)
        if v83:
            pid,action,sid,shot_action=v83.groups();p=self.get_project(pid)
            if action=='bible' and method=='GET':
                return self.send_json(character_bible_v83.binding(p))
            if action=='jobs' and method=='GET':
                return self.send_json({'jobs':[{'id':j['id'],'status':j.get('status'),
                    'kind':j.get('kind'),'shot_id':j.get('shot_id'),
                    'workflow_id':j.get('workflow_id')} for j in self.db.jobs(pid)],
                    'note':'Po przerwaniu połącz się z workflow_id; nie uruchamiaj nowej generacji.'})
            if action=='backup' and method=='GET':
                query=parse_qs(urlparse(self.path).query)
                clips=query.get('clips',['1'])[0]!='0'
                try:output=portable_v83.package(ROOT,p,self.db.jobs(pid),clips)
                except ValueError as e:raise ApiError(str(e),409) from None
                return self.send_bytes(output,'application/zip','film_v83_'+pid[:8]+'.zip')
            if action=='mode' and method=='POST':
                b=self.read_json()
                if b.get('approve') is not True:raise ApiError('Potwierdź zmianę trybu',403)
                if b.get('enabled') is True:
                    try:visual_lock_v82.snapshot(ROOT)
                    except ValueError as e:raise ApiError(str(e),409) from None
                    if not p.get('v82_visual_lock'):raise ApiError('Najpierw przypnij V8.2 Master Visual Lock',409)
                    if visual_lock_v82.check_masters(p,ROOT):raise ApiError('Zmienione referencje wymagają ponownego przypięcia',409)
                    p['v83_reference_mode']=True
                    p['v83_character_snapshot']=character_bible_v83.binding(p)['roles']
                elif b.get('enabled') is False:p['v83_reference_mode']=False
                else:raise ApiError('Wymagane enabled true/false',400)
                for shot in p.get('shots',[]):
                    shot.pop('image_quote',None);shot.pop('v83_reference_binding',None)
                self.db.save_project(p)
                return self.send_json({'enabled':p['v83_reference_mode'],'project':p})
            if sid and shot_action:
                shot=next((x for x in p.get('shots',[]) if x.get('id')==sid),None)
                if not shot:raise ApiError('Brak ujęcia',404)
                if shot_action=='references' and method=='GET':
                    return self.send_json(reference_v83.public_status(p,shot,ROOT))
                if shot_action=='upload-references' and method=='POST':
                    b=self.read_json()
                    if b.get('approve') is not True:raise ApiError('Wymagana zgoda na wysłanie referencji do Sogni',403)
                    if not p.get('v83_reference_mode'):raise ApiError('Włącz tryb V8.3',409)
                    try:plan=reference_v83.plan(p,shot,ROOT)
                    except ValueError as e:raise ApiError(str(e),409) from None
                    uploads=[]
                    for row in plan['files']:
                        f=visual_lock_v82.safe_file(ROOT,row['path'])
                        if visual_lock_v82.sha256(f)!=row['sha256']:
                            raise ApiError('Referencja zmieniona podczas przesyłania',409)
                        mime='image/png' if f.suffix.lower()=='.png' else 'image/jpeg'
                        result=sogni.upload_reference_image(f,mime)
                        uploads.append({'slot':row['slot'],'url':result['url']})
                    reference_v83.mark_uploaded(p,shot,ROOT,uploads)
                    self.db.save_project(p)
                    return self.send_json({'uploaded':True,'slots':plan['slots'],'expires_hint_hours':40,
                                           'notice':'Następny krok: image-quote, a następnie ręcznie zatwierdzone image-render'})
        # V8.2 Master Visual Lock: local-only control plane; no billable operations.
        if path=='/api/v82/masters' and method=='GET':
            return self.send_json(visual_lock_v82.summary(ROOT))
        v82_master=re.fullmatch(r'/api/v82/masters/(style|woman|man|couple)(?:/(image|approve))?',path)
        if v82_master:
            slot,action=v82_master.groups()
            if action=='image' and method=='GET':
                row=visual_lock_v82.summary(ROOT)['slots'][slot]
                try:file=visual_lock_v82.safe_file(ROOT,row['path'])
                except ValueError as e:raise ApiError(str(e),404) from None
                kind='image/png' if file.suffix.lower()=='.png' else 'image/jpeg'
                return self.send_bytes(file.read_bytes(),kind)
            if action=='image' and method=='PUT':
                try:n=int(self.headers.get('Content-Length','0'))
                except ValueError:raise ApiError('Nieprawidłowy rozmiar') from None
                if not 128<=n<=12*1024*1024:raise ApiError('Obraz 128 B–12 MB',413)
                content=self.rfile.read(n)
                if len(content)!=n:raise ApiError('Niekompletny plik',400)
                try:row=visual_lock_v82.replace(ROOT,slot,content,self.headers.get('Content-Type','').split(';')[0])
                except ValueError as e:raise ApiError(str(e),400) from None
                return self.send_json({'master':row,'action':'review_required'})
            if action=='approve' and method=='POST':
                b=self.read_json()
                try:row=visual_lock_v82.approve(ROOT,slot,str(b.get('sha256','')),b.get('viewed') is True,str(b.get('note','')))
                except ValueError as e:raise ApiError(str(e),409) from None
                return self.send_json({'master':row})
        v82_project=re.fullmatch('/api/v82/projects/'+ID+'(?:/(lock|report)|/shots/'+SID+'/(approve-keyframe|keyframe-preview|frame-info))?',path)
        if v82_project:
            pid,operation,sid,shot_action=v82_project.groups()
            project=self.get_project(pid)
            if operation=='report' and method=='GET':return self.send_json(visual_lock_v82.project_report(project,ROOT))
            if operation=='lock' and method=='POST':
                b=self.read_json()
                if b.get('approve') is not True:raise ApiError('Wymagana świadoma zgoda na zmianę blokady',403)
                if b.get('enabled') is True:
                    try:visual_lock_v82.pin_project(project,ROOT)
                    except ValueError as e:raise ApiError(str(e),409) from None
                elif b.get('enabled') is False:visual_lock_v82.unpin_project(project)
                else:raise ApiError('Podaj enabled true lub false')
                self.db.save_project(project)
                return self.send_json({'project':project,'report':visual_lock_v82.project_report(project,ROOT)})
            if sid and shot_action:
                shot=next((x for x in project.get('shots',[]) if x.get('id')==sid),None)
                if not shot or shot.get('mode')!='t2v':raise ApiError('Nieznane ujęcie wideo',404)
                if shot_action=='frame-info' and method=='GET':
                    try:file=visual_lock_v82.frame_path(ROOT,project,shot)
                    except ValueError as e:raise ApiError(str(e),404) from None
                    return self.send_json({'sha256':visual_lock_v82.sha256(file),'edit_version':shot.get('edit_version')})
                if shot_action=='keyframe-preview' and method=='GET':
                    try:file=visual_lock_v82.frame_path(ROOT,project,shot)
                    except ValueError as e:raise ApiError(str(e),404) from None
                    return self.send_bytes(file.read_bytes(),'image/png' if file.suffix=='.png' else 'image/jpeg')
                if shot_action=='approve-keyframe' and method=='POST':
                    b=self.read_json()
                    try:approval=visual_lock_v82.approve_frame(project,shot,ROOT,
                        b.get('viewed') is True,b.get('style_ok') is True,b.get('identity_ok') is True,str(b.get('notes','')),str(b.get('observed_sha','')))
                    except ValueError as e:raise ApiError(str(e),409) from None
                    self.db.save_project(project)
                    return self.send_json({'project':project,'approval':approval})
        if path=='/api/v8' and method=='GET':
            return self.send_json({'version':'8.0.0','local_voice_engine':'optional_chatterbox_multilingual',
              'emotions':voice_v8.EMOTIONS,'voice_requires_consent':True,
              'preview_needs_listening':True,'lip_sync_manual_gate':True,
              'paid_api_fallback':False,'product_demo':'verified_real_recording_only',
              'pace_audit':'rule_based_not_perceptual'})
        v8pace=re.fullmatch('/api/v8/projects/'+ID+'/(pace|cut-proposals)',path)
        if v8pace and method=='GET':
            project=self.get_project(v8pace.group(1))
            return self.send_json(pace_v8.audit(project) if v8pace.group(2)=='pace'
                                  else pace_v8.suggest_cuts(project))
        v8motion=re.fullmatch('/api/v8/projects/'+ID+'/shots/'+SID+'/motion-check',path)
        if v8motion and method=='GET':
            pid,sid=v8motion.groups();project=self.get_project(pid)
            shot=next((x for x in project.get('shots',[]) if x['id']==sid),None)
            if not shot or not self.clip_current(project,shot):
                raise ApiError('Najpierw wgraj aktualny klip MP4 do tego ujęcia',409)
            try:report=inspect_motion(ROOT/'data'/'clips'/pid/(sid+'.mp4'))
            except ValueError as e:raise ApiError(str(e),409) from None
            return self.send_json({'shot_id':sid,'motion':report})
        v8ref=re.fullmatch('/api/v8/projects/'+ID+'/shots/'+SID+'/product-frame',path)
        if v8ref and method=='POST':
            pid,sid=v8ref.groups();project=self.get_project(pid)
            shot=next((a for a in project.get('shots',[]) if a['id']==sid),None)
            if not shot:raise ApiError('Nie znaleziono ujęcia',404)
            body=self.read_json()
            try:plan=product_demo_v8.plan(shot,float(body.get('zoom',1)),float(body.get('focus_x',0.5)),
                  float(body.get('focus_y',0.5)),body.get('confirmed') is True)
            except (ValueError,TypeError) as e:raise ApiError(str(e),409) from None
            shot['v8_product_frame']=plan;shot['qc_approved']=False
            project['v8_enabled']=True;self.db.save_project(project)
            return self.send_json({'plan':plan,'project':project})
        v8voices=re.fullmatch('/api/v8/projects/'+ID+'/shots/'+SID+
            '/(voice-prepare|voice-generate|voice-list|voice-approve|voice-audio/([A-Za-z0-9_-]+))',path)
        if v8voices:
            pid,sid,action,audio_id=v8voices.groups();project=self.get_project(pid)
            shot=next((a for a in project.get('shots',[]) if a['id']==sid),None)
            if not shot:raise ApiError('Nie znaleziono ujęcia',404)
            if shot.get('mode')!='t2v':raise ApiError('Głos dotyczy ujęcia postaci, nie UI',409)
            if action=='voice-list' and method=='GET':
                return self.send_json(voice_v8.manifest(shot))
            if action=='voice-prepare' and method=='POST':
                body=self.read_json()
                if body.get('voice_consent') is not True:
                    raise ApiError('Potwierdź zgodę i licencję nagrania referencyjnego',403)
                if body.get('speaker') not in ('ONA','ON','WUJEK'):
                    raise ApiError('Wybierz zatwierdzoną postać z obsady',409)
                # Explicitly selecting a speaker adds that character to older storyboard scenes.
                if body['speaker'] not in (shot.get('characters') or []):
                    shot['characters']=list(dict.fromkeys((shot.get('characters') or [])+[body['speaker']]))
                # Imported recording is an optional voice reference. Consent must be explicit.
                reference=shot.get('v7_audio_file') if body.get('use_recording_as_reference') is True else None
                if reference and not Path(reference).is_file():raise ApiError('Brak pliku próbki głosu',409)
                try:req=voice_v8.build_variants_request(str(body.get('text','')),
                    str(body.get('emotion','neutral')),str(body.get('speaker','')),reference)
                except ValueError as e:raise ApiError(str(e),409) from None
                if body.get('voice_consent') is not True:
                    raise ApiError('Potwierdź zgodę i licencję nagrania referencyjnego',403)
                shot['edit_version']=str(uuid.uuid4())
                req['shot_edit_version']=shot['edit_version']
                shot['v8_voice_request']=req;shot['v8_voice_variants']=[];shot.pop('v8_voice_approved_id',None)
                shot.pop('v7_voice',None);shot['v7_lips_approved']=False;shot['qc_approved']=False
                project['v8_enabled']=True;project['v7_enabled']=True
                self.db.save_project(project)
                return self.send_json({'prepared':req,'project':project})
            if action=='voice-generate' and method=='POST':
                body=self.read_json()
                if body.get('approve') is not True:raise ApiError('Wymagana wyraźna zgoda na lokalną generację',403)
                req=shot.get('v8_voice_request')
                if not req:raise ApiError('Najpierw przygotuj kwestie w V8',409)
                if req.get('shot_edit_version')!=shot.get('edit_version'):raise ApiError('Ujęcie zostało zmienione od przygotowania mowy',409)
                directory=voice_v8.isolated_dir(ROOT,pid,sid)
                try:variants=voice_v8.run_chatterbox(req,directory)
                except ValueError as e:raise ApiError(str(e),409) from None
                shot['v8_voice_variants']=variants;shot.pop('v8_voice_approved_id',None)
                self.db.save_project(project)
                return self.send_json(voice_v8.manifest(shot))
            if action.startswith('voice-audio/') and method=='GET':
                row=next((v for v in shot.get('v8_voice_variants',[]) if v['id']==audio_id),None)
                if not row:raise ApiError('Nie ma takiego wariantu',404)
                f=Path(row['file']).resolve()
                if not f.is_relative_to((ROOT/'data'/'v8_voice'/pid/sid).resolve()) or not f.is_file():
                    raise ApiError('Nieprawidłowa ścieżka audio',403)
                return self.send_bytes(f.read_bytes(),'audio/wav')
            if action=='voice-approve' and method=='POST':
                body=self.read_json()
                if any(body.get(k) is not True for k in ('listened','polish_ok','voice_consent')):
                    raise ApiError('Wymagane potwierdzenie odsłuchu, wymowy i zgody',403)
                if shot.get('v8_voice_request',{}).get('shot_edit_version')!=shot.get('edit_version'):
                    raise ApiError('Zmieniłeś ujęcie po przygotowaniu głosu — wygeneruj warianty ponownie',409)
                try:chosen=voice_v8.approve(shot,str(body.get('variant_id','')),True)
                except ValueError as e:raise ApiError(str(e),409) from None
                dest=ROOT/'data'/'v7_audio'/pid;dest.mkdir(parents=True,exist_ok=True)
                target=dest/(sid+'_v8_approved.wav')
                shutil.copyfile(chosen['file'],target)
                shot['v7_audio_file']=str(target)
                shot['v7_audio_meta']=dialogue_v7.audio_probe(target)
                shot.pop('v7_voice',None);shot['v7_lips_approved']=False;shot['qc_approved']=False
                shot['edit_version']=str(uuid.uuid4());self.db.save_project(project)
                return self.send_json({'approved':chosen['id'],
                  'next':'Ustaw voice-plan w Reżyser V7, animuj usta i obejrzyj wynik',
                  'project':project})
        if path=='/api/v7' and method=='GET':
            return self.send_json({'version':'7.0.0','camera_presets':cinematic_v7.PRESETS,
               'audio_first':True,'default_video_model':voice_cli_v7.MODEL,
               'external_render_requires_approval':True,'provider_payment_mode':'subscription',
               'automated_lip_sync_detection':'not_guaranteed; manual approval mandatory',
               'polish_voice_recommendation':'Zaimportuj własne nagranie naturalnego polskiego głosu. Brak płatnego TTS.'})
        v7_match=re.fullmatch('/api/v7/projects/'+ID+'/shots/'+SID+'/(camera|coverage|voice-file|voice-plan|voice-recipe|voice-generate|render-preview|render-adopt|lip-diagnostics|lips-approve)',path)
        if v7_match:
            pid,sid,action=v7_match.groups()
            p=self.get_project(pid)
            shot=next((x for x in p.get('shots',[]) if x.get('id')==sid),None)
            if not shot:raise ApiError('Nie znaleziono ujęcia',404)
            if shot.get('mode')!='t2v':raise ApiError('Ujęcia UI wymagają rzeczywistych nagrań produktu',409)
            if action=='camera' and method=='POST':
                form=self.read_json()
                speaker=form.get('speaker') or None
                if speaker in ('ONA','ON','WUJEK') and speaker not in (shot.get('characters') or []):
                    # Explicit UI selection casts a speaking role into legacy storyboard scenes.
                    shot['characters']=list(dict.fromkeys((shot.get('characters') or [])+[speaker]))
                try:guide=cinematic_v7.plan(shot,str(form.get('preset','speaker_closeup')),speaker)
                except ValueError as e:raise ApiError(str(e)) from None
                shot['v7_camera']=guide;p['v7_enabled']=True
                shot['edit_version']=str(uuid.uuid4());shot['qc_approved']=False
                shot['v7_lips_approved']=False
                for k in ('quote','image_quote','media_url','workflow_id'):shot.pop(k,None)
                self.db.save_project(p)
                return self.send_json({'camera':guide,'project':p})
            if action=='coverage' and method=='GET':
                params=parse_qs(urlparse(self.path).query)
                try:plan=cinematic_v7.coverage(shot,(params.get('speaker') or ['ONA'])[0])
                except ValueError as e:raise ApiError(str(e)) from None
                return self.send_json({'plan':plan})
            if action=='voice-file' and method=='PUT':
                kind=self.headers.get('Content-Type','').split(';')[0]
                ext=dialogue_v7.AUDIO_CONTENT_TYPES.get(kind)
                if not ext:raise ApiError('Dozwolone WAV, MP3 i M4A',415)
                try:size=int(self.headers.get('Content-Length','0'))
                except ValueError:raise ApiError('Niepoprawna długość pliku') from None
                if size<100 or size>dialogue_v7.MAX_BYTES:raise ApiError('Maks. 25 MB nagrania audio',413)
                directory=ROOT/'data'/'v7_audio'/pid
                directory.mkdir(parents=True,exist_ok=True)
                f=directory/(sid+ext);temp=directory/(sid+'.upload')
                with temp.open('wb') as o:
                    remaining=size
                    while remaining:
                        data=self.rfile.read(min(1048576,remaining))
                        if not data:break
                        o.write(data);remaining-=len(data)
                if remaining:temp.unlink(missing_ok=True);raise ApiError('Niekompletny upload',400)
                try:meta=dialogue_v7.audio_probe(temp)
                except ValueError as e:temp.unlink(missing_ok=True);raise ApiError(str(e)) from None
                temp.replace(f)
                shot['v7_audio_file']=str(f);shot['v7_audio_meta']=meta
                shot.pop('v7_voice',None);shot['v7_lips_approved']=False
                shot['qc_approved']=False;shot['edit_version']=str(uuid.uuid4())
                p['v7_enabled']=True;self.db.save_project(p)
                return self.send_json({'uploaded':True,'audio':meta,'project':p})
            if action=='voice-plan' and method=='POST':
                data=self.read_json()
                file=shot.get('v7_audio_file')
                if not file:raise ApiError('Najpierw prześlij zatwierdzone polskie nagranie audio',409)
                try:info=dialogue_v7.prepare_talking_shot(shot,str(data.get('speaker','')),
                    str(data.get('transcript','')),file,str(data.get('camera','speaker_closeup')))
                except ValueError as e:raise ApiError(str(e)) from None
                shot['v7_voice']=info;shot['v7_lips_approved']=False;shot['qc_approved']=False
                shot['edit_version']=str(uuid.uuid4())
                v85=shot.get('v85_audio') or {}
                if (v85.get('approved') and v85.get('sha256')==info['audio']['sha256']
                    and str(shot.get('dialogue') or '').strip()==info['transcript']):
                    # The voice PLAN modified the scene version, not its audio;
                    # preserve the explicit listening decision for that exact WAV.
                    v85['edit_version']=shot['edit_version']
                p['v7_enabled']=True;self.db.save_project(p)
                return self.send_json({'voice':info,'project':p})
            if action in ('voice-recipe','voice-generate'):
                info=shot.get('v7_voice')
                if not info:raise ApiError('Najpierw ustaw audio-first: voice-plan',409)
                data=self.read_json() if method=='POST' else {}
                rid=str(data.get('reference_id') or (parse_qs(urlparse(self.path).query).get('reference_id') or [''])[0])
                try:
                    if p.get('v82_visual_lock'):
                        issues=visual_lock_v82.check_frame(p,shot,ROOT)
                        if issues:raise ValueError('V8.2: '+'; '.join(issues))
                        source=visual_lock_v82.frame_path(ROOT,p,shot)
                    else:
                        if not rid:raise ValueError('Wybierz zatwierdzoną referencję postaci')
                        ref=reference_v6.find(rid)
                        if ref['review']!='approved':raise ValueError('Referencja wymaga zatwierdzenia w bibliotece V6')
                        role=reference_v6.ROLES.get(info['speaker'])
                        if ref['category'] not in (role,'PARA'):raise ValueError('Referencja nie pasuje do mówiącego')
                        source=reference_v6.file_for(rid)
                    if action=='voice-recipe' and method=='GET':
                        return self.send_json({'recipe':voice_cli_v7.recipe(shot,info,source),'submitted':False})
                    if action=='voice-generate' and method=='POST':
                        if data.get('approve') is not True:raise ApiError('Wymagana osobna zgoda na pojedynczy render',403)
                        result=voice_cli_v7.generate_once(shot,info,source,True)
                        shot['v7_render']=result;shot['v7_lips_approved']=False;shot['qc_approved']=False
                        self.db.save_project(p)
                        return self.send_json({'render':result,'preview':'/api/v7/projects/'+pid+'/shots/'+sid+'/render-preview'})
                except ValueError as e:raise ApiError(str(e),409) from None
            if action=='render-preview' and method=='GET':
                row=shot.get('v7_render') or {};f=Path(row.get('file','/missing-file'))
                if not f.is_file() or not f.resolve().is_relative_to(voice_cli_v7.OUTPUTS.resolve()):raise ApiError('Brak renderu',404)
                self.send_response(200);self.send_header('Content-Type','video/mp4');self.send_header('Content-Length',str(f.stat().st_size));self.send_header('Cache-Control','no-store');self.end_headers()
                with f.open('rb') as fo:shutil.copyfileobj(fo,self.wfile,length=1048576)
                return
            if action=='render-adopt' and method=='POST':
                data=self.read_json()
                if data.get('watched') is not True:raise ApiError('Przed importem obejrzyj prawdziwy klip',403)
                row=shot.get('v7_render') or {};f=Path(row.get('file','/missing-file'))
                if not f.is_file() or not f.resolve().is_relative_to(voice_cli_v7.OUTPUTS.resolve()):raise ApiError('Nie znaleziono renderu',404)
                folder=ROOT/'data'/'clips'/pid;folder.mkdir(parents=True,exist_ok=True)
                shutil.copy2(f,folder/(sid+'.mp4'))
                (folder/(sid+'.meta.json')).write_text(json.dumps({'shot_generation':p.get('shot_generation'), 'edit_version':shot.get('edit_version')}),encoding='utf8')
                shot['qc_approved']=False;shot.pop('v82_clip_approval',None);shot['v7_lips_approved']=False
                self.db.save_project(p)
                return self.send_json({'imported':True,'requires_lipsync_review':True,'project':p})
            if action=='lip-diagnostics' and method=='GET':
                if not self.clip_current(p,shot):raise ApiError('Brak aktualnego ujęcia MP4',409)
                parts=(parse_qs(urlparse(self.path).query).get('roi') or ['0.35,0.38,0.30,0.20'])[0].split(',')
                if len(parts)!=4:raise ApiError('ROI musi zawierać X,Y,W,H jako liczby od 0 do 1')
                try:result=inspect_mouth(ROOT/'data'/'clips'/pid/(sid+'.mp4'),tuple(float(v) for v in parts))
                except ValueError as e:raise ApiError(str(e)) from None
                return self.send_json({'diagnostics':result})
            if action=='lips-approve' and method=='POST':
                data=self.read_json()
                if not self.clip_current(p,shot):raise ApiError('Brak aktualnego klipu do kontroli',409)
                if not shot.get('v7_voice'):raise ApiError('Brak zatwierdzonego dialogu',409)
                if any(data.get(k) is not True for k in ('watched','listened','polish_ok','lips_match','identity_ok')):
                    raise ApiError('Potwierdź obejrzenie, odsłuch, polski język, ruch ust i spójność twarzy',403)
                shot['v7_lips_approved']=True
                shot['v7_lips_review']={'reviewed_at':engine.now(),'reviewer':'local_manual','notes':str(data.get('notes',''))[:400],
                    'audio_sha256':shot['v7_voice']['audio']['sha256'],'edit_version':shot.get('edit_version')}
                self.db.save_project(p)
                return self.send_json({'approved':True,'project':p})
            raise ApiError('Niedozwolona metoda',405)
        if path=='/api/projects':
            if method=='GET':return self.send_json({'projects':self.db.list_projects()})
            if method=='POST':
                p=engine.new_project(self.read_json())
                auto_cast={role:pid for role,pid in {
                    'ONA':'11111111-1111-4111-8111-111111111111',
                    'ON':'22222222-2222-4222-8222-222222222222'}.items() if self.db.get_persona(pid)}
                if auto_cast:personas.bind_cast(p,self.db,auto_cast)
                self.db.save_project(p)
                return self.send_json({'project':p},201)
        if path=='/api/style-guide' and method=='GET':return self.send_json(style_guide.state(ROOT))
        if path=='/api/style-guide/image' and method=='GET':
            file=style_guide.default_image(ROOT)
            if not file.is_file():raise ApiError('Brak graficznego wzorca stylu',404)
            return self.send_bytes(file.read_bytes(),'image/png')
        if path=='/api/style-guide/sync' and method=='POST':
            data=self.read_json()
            if data.get('approve') is not True:raise ApiError('Wymagana zgoda na przesłanie wzorca stylu do Sogni.',403)
            result=sogni.upload_reference_image(style_guide.default_image(ROOT),'image/png')
            style_guide.write_remote(ROOT,result['url'])
            return self.send_json({'uploaded':True,'style':style_guide.state(ROOT)})
        if path=='/api/personas':
            if method=='GET':return self.send_json({'personas':self.db.list_personas(),
                'visual_style':{'id':personas.STYLE_ID,'name':personas.STYLE_NAME,
                                'visual_prompt':personas.STYLE_VISUAL,'motion_prompt':personas.STYLE_MOTION,
                                'avoid':personas.STYLE_AVOID}})
            if method=='POST':
                try:person=personas.new_persona(self.read_json())
                except ValueError as e:raise ApiError(str(e)) from None
                self.db.save_persona(person);return self.send_json({'persona':person},201)
        m_persona=re.fullmatch('/api/personas/'+ID+'(?:/assets/([a-z0-9_]+)|/(sync-reference))?',path)
        if m_persona:
            persona_id,asset,action=m_persona.groups()
            person=self.db.get_persona(persona_id)
            if not person:raise ApiError('Nie znaleziono postaci.',404)
            if method=='GET' and not (asset or action):return self.send_json({'persona':person})
            if method=='PUT' and not (asset or action):
                form=self.read_json()
                for k,lim in {'name':100,'look':3000,'personality':1000,'avoid':2000}.items():
                    if k in form:
                        if not isinstance(form[k],str):raise ApiError('Wartość pola musi być tekstem.')
                        person[k]=form[k][:lim].strip()
                if not person['name']:raise ApiError('Postać musi mieć nazwę')
                person['updated']=personas.now();self.db.save_persona(person)
                return self.send_json({'persona':person})
            if asset:
                try:personas.check_asset_name(asset)
                except ValueError as e:raise ApiError(str(e),404) from None
                filename=person.get('assets',{}).get(asset)
                if method=='GET':
                    if not filename:raise ApiError('Brak obrazu w tej perspektywie',404)
                    file=ROOT/'data'/'personas'/persona_id/filename
                    if not file.is_file():raise ApiError('Nie znaleziono pliku referencji.',404)
                    return self.send_bytes(file.read_bytes(),'image/png' if file.suffix=='.png' else 'image/jpeg')
                if method=='PUT':
                    try:size=int(self.headers.get('Content-Length','0'))
                    except ValueError:raise ApiError('Nieprawidłowy rozmiar',400)
                    if not 20<=size<=12*1024*1024:raise ApiError('Wybierz PNG lub JPEG, maks. 12 MB.',413)
                    kind=self.headers.get('Content-Type','').split(';')[0]
                    if kind not in ('image/png','image/jpeg'):raise ApiError('Dozwolony PNG lub JPEG.',415)
                    data=self.rfile.read(size)
                    if len(data)!=size:raise ApiError('Przesyłanie pliku jest niekompletne.',400)
                    valid=data.startswith(b'\x89PNG\r\n\x1a\n') if kind=='image/png' else data.startswith(b'\xff\xd8\xff')
                    if not valid:raise ApiError('Nieprawidłowy nagłówek obrazu.',400)
                    ext='.png' if kind=='image/png' else '.jpg'
                    directory=ROOT/'data'/'personas'/persona_id;directory.mkdir(parents=True,exist_ok=True)
                    (directory/(asset+ext)).write_bytes(data)
                    person.setdefault('assets',{})[asset]=asset+ext
                    person['remote_reference_url']='';person['reference_status']='local_only'
                    person['updated']=personas.now();self.db.save_persona(person)
                    return self.send_json({'persona':person,'uploaded':True})
            if action=='sync-reference' and method=='POST':
                body=self.read_json()
                if body.get('approve') is not True:raise ApiError('Wymagana świadoma zgoda na przesłanie obrazu do Sogni',403)
                asset=body.get('asset','portrait')
                if asset not in ('portrait','sheet','front','threequarter','profile','back'):
                    raise ApiError('Nieznany obraz referencyjny',400)
                filename=person.get('assets',{}).get(asset)
                if not filename:raise ApiError('Najpierw dodaj lokalny obraz postaci.',409)
                file=ROOT/'data'/'personas'/persona_id/filename
                mime='image/png' if file.suffix=='.png' else 'image/jpeg'
                result=sogni.upload_reference_image(file,mime)
                person.update(remote_reference_url=result['url'],remote_reference_kind=asset,
                    remote_synced_at=result['synced_at'],reference_status='uploaded_to_sogni',updated=personas.now())
                self.db.save_persona(person)
                return self.send_json({'persona':person,'uploaded':True,'expires_hint_hours':48})
            raise ApiError('Niedozwolona metoda',405)
        # V6: checkpoint library stays local until explicit per-image approval.
        if path=='/api/v6/references' and method=='GET':return self.send_json(reference_v6.summary())
        if path=='/api/v6/camera360' and method=='GET':return self.send_json(camera360.public_presets())
        if path=='/api/v6/camera360/generate' and method=='POST':
            body=self.read_json()
            try:
                row=camera360_cli.generate_one(str(body.get('reference_id','')),
                    str(body.get('azimuth','front-right')),
                    str(body.get('elevation','eye-level')),
                    str(body.get('distance','medium')),body.get('approve') is True)
            except (ValueError,RuntimeError) as e:raise ApiError(str(e),409) from None
            return self.send_json({'result':row,'preview':'/api/v6/camera360/render/'+row['render_id']},201)
        render_match=re.fullmatch('/api/v6/camera360/render/([0-9a-f-]{36})',path)
        if render_match and method=='GET':
            try:file=camera360_cli.fetch_image(render_match.group(1))
            except ValueError as e:raise ApiError(str(e),404) from None
            return self.send_bytes(file.read_bytes(),'image/png')

        image_match=re.fullmatch(r'/api/v6/references/([A-Za-z0-9_\-/]+)/image',path)
        if image_match and method=='GET':
            try:file=reference_v6.file_for(image_match.group(1))
            except ValueError as e:raise ApiError(str(e),404) from None
            return self.send_bytes(file.read_bytes(),'image/png')
        review_match=re.fullmatch(r'/api/v6/references/([A-Za-z0-9_\-/]+)/(review|remote|sync)',path)
        if review_match and method=='POST':
            key,action=review_match.groups();body=self.read_json()
            try:
                if action=='review':
                    return self.send_json({'reference':reference_v6.review(key,body.get('decision'),str(body.get('note','')))})
                if action=='remote':
                    if body.get('approve') is not True:raise ApiError('Wymagana zgoda na przypisanie linku z Sogni',403)
                    return self.send_json({'reference':reference_v6.set_remote(key,str(body.get('url','')))})
                if body.get('approve') is not True:raise ApiError('Wyraźna zgoda na wysłanie obrazu do Sogni jest wymagana',403)
                entry=reference_v6.find(key)
                if entry['review']!='approved':raise ApiError('Najpierw zatwierdź tę referencję',409)
                sogni.assert_active_subscription()
                response=sogni.upload_reference_image(reference_v6.file_for(key),'image/png')
                return self.send_json({'reference':reference_v6.set_remote(key,response['url']), 'uploaded':True})
            except ValueError as e:raise ApiError(str(e)) from None
        if path=='/api/sogni/test'  and method=='GET':return self.send_json(sogni.account_check())
        if path=='/api/sogni/models' and method=='GET':
            _,j=sogni.request('GET','/v1/models',timeout=15)
            return self.send_json({'models':[x.get('id') for x in j.get('data',[])][:60]})
        m=re.fullmatch('/api/projects/'+ID+'(/.*)?',path)
        if not m:raise ApiError('Nieznany adres API',404)
        id=m.group(1);suffix=m.group(2) or ''
        if suffix=='/v6/references' and method=='GET':
            p=self.get_project(id)
            return self.send_json({'locked':bool(p.get('v6_reference_lock')),
                'shots':[{'id':s['id'], 'characters':s.get('characters',[]),
                    'suggested':[x['id'] for x in reference_v6.suggest_for_shot(s)],
                    'selected':s.get('v6_reference_ids',[])} for s in p.get('shots',[])],
                'summary':reference_v6.summary()['statuses']})
        if suffix=='/v6/references/lock' and method=='PUT':
            p=self.get_project(id);body=self.read_json()
            if not isinstance(body.get('enabled'),bool):raise ApiError('Podaj enabled: true/false')
            p['v6_reference_lock']=body['enabled'];p['updated']=engine.now();self.db.save_project(p)
            return self.send_json({'project':p})
        shot_ref=re.fullmatch('/v6/references/shots/'+SID,suffix)
        if shot_ref and method=='PUT':
            p=self.get_project(id);shot=next((s for s in p.get('shots',[]) if s['id']==shot_ref.group(1)),None)
            if not shot:raise ApiError('Nie znaleziono ujęcia',404)
            body=self.read_json();ids=body.get('ids')
            if not isinstance(ids,list) or len(ids)>3 or any(not isinstance(x,str) for x in ids):
                raise ApiError('Wymagana lista maksymalnie 3 ID')
            previous=shot.get('v6_reference_ids',[])
            shot['v6_reference_ids']=ids
            try:reference_v6.resolve_for_shot(shot)
            except ValueError as e:
                shot['v6_reference_ids']=previous;raise ApiError(str(e)) from None
            shot['edit_version']=str(uuid.uuid4());shot['qc_approved']=False
            for k in ('quote','image_quote','media_url','workflow_id'):shot.pop(k,None)
            self.db.save_project(p)
            return self.send_json({'project':p})
        if suffix=='/360' and method=='GET':
            p=self.get_project(id)
            return self.send_json({'plans':[{'id':s['id'],'mode':s['mode'],'camera360':s.get('camera360'),
                        'characters':s.get('characters',[])} for s in p.get('shots',[])],
                        'presets':camera360.public_presets()})
        adopt_match=re.fullmatch('/shots/'+SID+'/360/adopt',suffix)
        if adopt_match and method=='POST':
            body=self.read_json()
            if body.get('approve') is not True:raise ApiError('Zatwierdź klatkę po obejrzeniu obrazu',403)
            p=self.get_project(id)
            shot=next((s for s in p.get('shots',[]) if s['id']==adopt_match.group(1)),None)
            if not shot or shot.get('mode')!='t2v':raise ApiError('Nieprawidłowe ujęcie',404)
            try:file=camera360_cli.fetch_image(body.get('render_id'))
            except ValueError as e:raise ApiError(str(e),404) from None
            target=ROOT/'data'/'keyframes'/id;target.mkdir(parents=True,exist_ok=True)
            shutil.copy2(file,target/(shot['id']+'.png'))
            shot['firstframe_local']=shot['id']+'.png'
            shot.pop('v82_frame_approval',None);shot.pop('v82_synced_sha256',None);shot.pop('v82_synced_at',None)
            shot['camera360_render_id']=body['render_id']
            shot['edit_version']=str(uuid.uuid4());shot['qc_approved']=False
            for k in ('quote','image_quote','image_url','workflow_id','media_url'):shot.pop(k,None)
            self.db.save_project(p)
            return self.send_json({'project':p,'adopted':True,
                'next_step':'Wyślij zaakceptowaną klatkę do Sogni w zakładce Storyboard → Synchronizuj klatkę.'})
        angles_match=re.fullmatch('/shots/'+SID+'/360(?:/(recipe))?',suffix)
        if angles_match:
            shot_id,recipe=angles_match.groups();p=self.get_project(id)
            shot=next((s for s in p.get('shots',[]) if s['id']==shot_id),None)
            if not shot:raise ApiError('Nieznane ujęcie',404)
            if shot.get('mode')!='t2v':raise ApiError('360 tylko dla ujęcia animowanego (nie dla prawdziwego UI)',409)
            if recipe and method=='POST':
                body=self.read_json()
                plan=shot.get('camera360')
                if not plan:raise ApiError('Najpierw zaplanuj kąty',409)
                return self.send_json({'recipe':camera360.make_cli_recipe(plan,body.get('source_image',''))})
            if method=='POST' and not recipe:
                body=self.read_json()
                plan=camera360.build(str(body.get('preset_id','dialogue_reveal')),shot,body.get('points'))
                shot['camera360']=plan
                shot['edit_version']=str(uuid.uuid4());shot['qc_approved']=False
                for k in ('quote','image_quote','media_url','workflow_id'):shot.pop(k,None)
                p['updated']=engine.now();self.db.save_project(p)
                return self.send_json({'plan':plan,'project':p})
            if method=='GET' and not recipe:return self.send_json({'plan':shot.get('camera360')})
        if suffix=='' and method=='GET':return self.send_json({'project':self.get_project(id),'jobs':self.db.jobs(id)})
        if suffix=='/director-v4' and method=='POST':
            p=self.get_project(id)
            casting=p.get('casting',{}).copy()
            try:apply_director_v4(p)
            except ValueError as e:raise ApiError(str(e),409) from None
            if casting:personas.bind_cast(p,self.db,casting)
            self.db.save_project(p)
            return self.send_json({'project':p,'audit':story_audit(p)})
        if suffix=='/casting' and method=='PUT':
            p=self.get_project(id);data=self.read_json()
            try:personas.bind_cast(p,self.db,data.get('casting',{}))
            except ValueError as e:raise ApiError(str(e),400) from None
            self.db.save_project(p);return self.send_json({'project':p})
        if suffix=='/visual-preview' and method=='GET':
            p=self.get_project(id)
            return self.send_json({'style_id':personas.STYLE_ID,'style_name':personas.STYLE_NAME,
                'shots':[{'id':s['id'],'mode':s.get('mode'),'characters':s.get('characters',[]),
                          'selected_personas':{c['id']:c.get('persona_id') for c in personas.cast_for_shot(p,s)},
                          'prompt':personas.render_prompt(p,s) if s.get('mode')=='t2v' else s.get('prompt',''),
                          'reference_count':len(personas.shot_provider_refs(p,s,style_guide.state(ROOT)['remote_reference_url'])),
                          'requires_cloud_sync':any(not c.get('reference_url') for c in personas.cast_for_shot(p,s))}
                   for s in p.get('shots',[])]})
        if suffix=='/v4/story-audit' and method=='GET':
            p=self.get_project(id)
            return self.send_json({'audit':story_audit(p),'quality_mode':bool(p.get('v4_quality_mode'))})
        clip_action=re.fullmatch('/clips/'+SID+'/(inspect|approve|preview)',suffix)
        if clip_action:
            shot_id,action=clip_action.groups();p=self.get_project(id)
            shot=next((x for x in p.get('shots',[]) if x['id']==shot_id),None)
            if not shot:raise ApiError('Nieznane ujęcie',404)
            if not self.clip_current(p,shot):raise ApiError('Najpierw wgraj aktualny klip MP4',409)
            path_clip=ROOT/'data'/'clips'/id/(shot_id+'.mp4')
            if action=='preview' and method=='GET':
                self.send_response(200);self.send_header('Content-Type','video/mp4')
                self.send_header('Content-Length',str(path_clip.stat().st_size))
                self.send_header('Cache-Control','no-store');self.end_headers()
                with path_clip.open('rb') as f:shutil.copyfileobj(f,self.wfile,length=1024*1024)
                return
            try:report=inspect_shot(path_clip,shot)
            except (FileNotFoundError,RuntimeError,ValueError) as e:raise ApiError(str(e),409) from None
            if action=='inspect' and method=='GET':return self.send_json({'report':report,'approved':bool(shot.get('qc_approved'))})
            if action=='approve' and method=='POST':
                data=self.read_json()
                if data.get('viewed') is not True:raise ApiError('Najpierw obejrzyj materiał i potwierdź kontrolę wizualną',403)
                if report['issues']:raise ApiError('Nie można zatwierdzić: '+'; '.join(report['issues']),409)
                if shot.get('mode')=='ui':
                    try:shot['ui_provenance']=provenance(str(data.get('source_url','')),
                         data.get('authentic') is True,str(data.get('description','')))
                    except ValueError as e:raise ApiError(str(e),400) from None
                if p.get('v82_visual_lock') and shot.get('mode')=='t2v':
                    if data.get('style_ok') is not True or data.get('identity_ok') is not True:
                        raise ApiError('V8.2: obejrzyj i potwierdź wygląd postaci oraz styl całego klipu',403)
                    errs=visual_lock_v82.check_frame(p,shot,ROOT)
                    if errs:raise ApiError('; '.join(errs),409)
                    shot['v82_clip_approval']={'edit_version':shot.get('edit_version'),
                        'master_snapshot':p['v82_visual_snapshot'],'reviewed_at':engine.now()}
                shot['qc_approved']=True
                shot['approval_date']=engine.now()
                shot['qc_report']=report
                p['updated']=engine.now();self.db.save_project(p)
                return self.send_json({'project':p,'report':report})
            raise ApiError('Niedozwolona metoda',405)
        if suffix=='/readiness' and method=='GET':
            p=self.get_project(id);folder=ROOT/'data'/'clips'/id
            issues=engine.validate_story(p)
            if p.get('v4_quality_mode'):
                issues+=story_audit(p)['blocking']
                for shot in p.get('shots',[]):
                    if not shot.get('qc_approved'):issues.append('Brak akceptacji ujęcia: '+shot['id'])
                    if shot['mode']=='ui' and not shot.get('ui_provenance',{}).get('user_confirmed_real_ui'):
                        issues.append('Brak potwierdzenia autentyczności ekranu '+shot['id'])
            if p.get('v82_visual_lock'):
                issues+=visual_lock_v82.check_masters(p,ROOT)
                for shot in p.get('shots',[]):
                    if shot.get('mode')=='t2v':
                        issues+=visual_lock_v82.check_frame(p,shot,ROOT)
                        if not shot.get('qc_approved') or (shot.get('v82_clip_approval') or {}).get('edit_version')!=shot.get('edit_version'):
                            issues.append('V8.2: brak akceptacji stylu gotowego klipu '+shot['id'])
            if p.get('v8_enabled'):
                for shot in p.get('shots',[]):
                    if shot.get('v8_voice_variants') and not shot.get('v8_voice_approved_id'):
                        issues.append('V8: odsłuchaj i zaakceptuj głos '+shot['id'])
                    if shot.get('v8_product_frame') and not shot.get('qc_approved'):
                        issues.append('V8: zatwierdź po kadrowaniu prawdziwy ekran '+shot['id'])
            if p.get('v7_enabled'):
                for shot in p.get('shots',[]):
                    if shot.get('mode')=='t2v' and (str(shot.get('dialogue') or '').strip() or shot.get('v7_voice')):
                        if not shot.get('v7_voice'):issues.append('V7: brak nagrania audio-first '+shot['id'])
                        if not shot.get('v7_lips_approved'):issues.append('V7: niezatwierdzony lip-sync '+shot['id'])
            return self.send_json({'issues':list(dict.fromkeys(issues)),
                'clips':[{ 'id':x['id'], 'available':self.clip_current(p,x),
                           'mode':x['mode'],'approved':bool(x.get('qc_approved'))} for x in p.get('shots',[])],
                'ffmpeg_available':bool(shutil.which('ffmpeg'))})
        if suffix=='/assemble' and method=='POST':
            p=self.get_project(id)
            issues=engine.validate_story(p)
            if p.get('v4_quality_mode'):
                issues+=story_audit(p)['blocking']
                for shot in p.get('shots',[]):
                    if not shot.get('qc_approved'):issues.append('Niezaakceptowany klip '+shot['id'])
                    if shot['mode']=='ui' and not shot.get('ui_provenance',{}).get('user_confirmed_real_ui'):
                        issues.append('Brak autentycznego UI '+shot['id'])
            if p.get('v82_visual_lock'):
                issues+=visual_lock_v82.check_masters(p,ROOT)
                for shot in p.get('shots',[]):
                    if shot.get('mode')=='t2v':
                        issues+=visual_lock_v82.check_frame(p,shot,ROOT)
                        if not shot.get('qc_approved') or (shot.get('v82_clip_approval') or {}).get('edit_version')!=shot.get('edit_version'):
                            issues.append('V8.2: brak akceptacji stylu gotowego klipu '+shot['id'])
            if p.get('v8_enabled'):
                for shot in p.get('shots',[]):
                    if shot.get('v8_voice_variants') and not shot.get('v8_voice_approved_id'):
                        issues.append('V8: odsłuchaj i zaakceptuj głos '+shot['id'])
                    if shot.get('v8_product_frame') and not shot.get('qc_approved'):
                        issues.append('V8: zatwierdź po kadrowaniu prawdziwy ekran '+shot['id'])
            if p.get('v7_enabled'):
                for shot in p.get('shots',[]):
                    if shot.get('mode')=='t2v' and (str(shot.get('dialogue') or '').strip() or shot.get('v7_voice')):
                        if not (shot.get('v7_voice') or (shot.get('v85_audio') or {}).get('approved')):issues.append('V7: brak nagrania '+shot['id'])
                        if not shot.get('v7_lips_approved'):issues.append('V7: brak akceptacji ruchu ust '+shot['id'])
            if (p.get('v85_audio_mix') or {}).get('enabled'):
                try:timeline_v85.cues(ROOT,p,require_approved=True)
                except ValueError as e:issues.append(str(e))
            if issues:raise ApiError('Montaż wstrzymany: '+'; '.join(issues),409)
            missing=[x['id'] for x in p.get('shots',[]) if not self.clip_current(p,x)]
            if missing:raise ApiError('Brak aktualnych klipów MP4: '+', '.join(missing)+'. Wgraj je po zmianach storyboardu.',409)
            from montaz import render
            dest=ROOT/'data'/'exports'/id/'reklama.mp4'
            try:result=render(p,ROOT/'data'/'clips'/id,dest,quality='final')
            except (FileNotFoundError,RuntimeError,ValueError) as e:raise ApiError(str(e)[:700],409) from None
            return self.send_json({'result':result,'download':'/api/projects/'+id+'/movie'})
        if suffix=='/movie' and method=='GET':
            file=ROOT/'data'/'exports'/id/'reklama.mp4'
            if not file.is_file():raise ApiError('Najpierw zmontuj film.',404)
            self.send_response(200);self.send_header('Content-Type','video/mp4')
            self.send_header('Content-Length',str(file.stat().st_size))
            self.send_header('Content-Disposition','attachment; filename=nasz_dzien_reklama.mp4')
            self.send_header('Cache-Control','no-store');self.end_headers()
            with file.open('rb') as f:shutil.copyfileobj(f,self.wfile,length=1024*1024)
            return
        clip_m=re.fullmatch('/clips/'+SID,suffix)
        if clip_m and method=='POST':
            p=self.get_project(id);shot_id=clip_m.group(1)
            if not any(x['id']==shot_id for x in p.get('shots',[])):raise ApiError('Ujęcie nie istnieje.',404)
            try:n=int(self.headers.get('Content-Length','0'))
            except ValueError:raise ApiError('Nieprawidłowy rozmiar pliku',400)
            if not 16<n<=120*1024*1024:raise ApiError('MP4 nie może przekraczać 120 MB.',413)
            if self.headers.get('Content-Type','').split(';')[0] not in ('video/mp4','application/octet-stream'):
                raise ApiError('Wymagany plik MP4.',415)
            folder=ROOT/'data'/'clips'/id;folder.mkdir(parents=True,exist_ok=True)
            file=folder/(shot_id+'.mp4');temp=folder/(shot_id+'.upload')
            with temp.open('wb') as f:
                remaining=n
                while remaining>0:
                    chunk=self.rfile.read(min(1024*1024,remaining))
                    if not chunk:break
                    f.write(chunk);remaining-=len(chunk)
            with temp.open('rb') as f:
                is_mp4=b'ftyp' in f.read(32)
            if remaining or not is_mp4:
                temp.unlink(missing_ok=True);raise ApiError('Przesłany plik nie jest poprawnym MP4.',400)
            temp.replace(file)
            shot=next(x for x in p['shots'] if x['id']==shot_id)
            shot['qc_approved']=False
            shot.pop('v82_clip_approval',None)
            shot['v7_lips_approved']=False
            shot.pop('ui_provenance',None);shot.pop('qc_report',None)
            self.db.save_project(p)
            metadata={'shot_generation':p.get('shot_generation'),'edit_version':shot.get('edit_version')}
            (folder/(shot_id+'.meta.json')).write_text(json.dumps(metadata),encoding='utf8')
            return self.send_json({'uploaded':True,'shot_id':shot_id,'bytes':n})
        if suffix=='/export' and method=='GET':
            p=self.get_project(id)
            return self.send_bytes(exporter.package(p,self.db.jobs(id)),'application/zip','nasz_dzien_film_'+id[:8]+'.zip')
        if suffix=='/develop' and method=='POST':
            data=self.read_json();p=self.get_project(id)
            if data.get('mode')=='ai':
                if data.get('allow_paid') is not True:raise ApiError('Wymagana zgoda na użycie abonamentu Unlimited.',403)
                if not sogni.key():raise ApiError('Nie skonfigurowano SOGNI_API_KEY',503)
                ai.develop_live(p,self.db.save_project)
            else:engine.develop_demo(p)
            if p.get('casting'):personas.bind_cast(p,self.db,p['casting'])
            self.db.save_project(p)
            return self.send_json({'project':p,'jobs':self.db.jobs(id)})
        if suffix=='/select' and method=='POST':
            data=self.read_json();p=self.get_project(id)
            chosen=data.get('concept_id','')
            if chosen not in [c['id'] for c in p['concepts']]:raise ApiError('Koncepcja nie istnieje')
            if data.get('mode')=='ai':
                if data.get('allow_paid') is not True:raise ApiError('Wymagana zgoda na generowanie w ramach abonamentu.',403)
                c=next(c for c in p['concepts'] if c['id']==chosen)
                script,shots,cast=ai.create_script(p,c)
                p.update(selected_concept_id=chosen,script=script,shots=shots,cast=cast, mode='sogni_ai',storyboard_stale=False,shot_generation=str(uuid.uuid4()))
            else:
                engine.select_demo(p,chosen)
                if p.get('mode')=='sogni_ai':p['mode']='mixed_template'
            if p.get('casting'):personas.bind_cast(p,self.db,p['casting'])
            p['updated']=engine.now();self.db.save_project(p)
            return self.send_json({'project':p})
        if suffix=='/doctor' and method=='POST':
            data=self.read_json();p=self.get_project(id)
            if data.get('allow_paid') is not True:raise ApiError('Wymagana zgoda na operacje AI w abonamencie.',403)
            if not sogni.key():raise ApiError('Nie skonfigurowano SOGNI_API_KEY',503)
            ai.script_doctor(p,self.db.save_project)
            return self.send_json({'project':p})
        if suffix=='/sync' and method=='POST':
            data=self.read_json();p=self.get_project(id)
            if data.get('approve') is not True:raise ApiError('Zatwierdź synchronizację przez Sogni Unlimited.',403)
            if not sogni.key():raise ApiError('Brak klucza Sogni',503)
            ai.sync_storyboard_from_script(p,self.db.save_project)
            if p.get('casting'):personas.bind_cast(p,self.db,p['casting']);self.db.save_project(p)
            return self.send_json({'project':p})
        if suffix=='/script' and method=='PUT':
            data=self.read_json();p=self.get_project(id)
            script=str(data.get('script',''))
            if not 1<=len(script)<=50000:raise ApiError('Scenariusz musi mieć 1–50000 znaków')
            p.setdefault('script_versions',[]).append({'script':p.get('script',''),'shots':p.get('shots',[]),'created':engine.now(),'reason':'manual_edit'})
            p.update(script=script,storyboard_stale=True,revisions=p.get('revisions',0)+1,updated=engine.now());self.db.save_project(p)
            return self.send_json({'project':p})
        if suffix=='/cast' and method=='PUT':
            data=self.read_json();p=self.get_project(id)
            cast=data.get('cast')
            if not isinstance(cast,list) or not 1<=len(cast)<=6:
                raise ApiError('Podaj 1–6 postaci.',400)
            cleaned=[]
            for c in cast:
                if not isinstance(c,dict) or not isinstance(c.get('name'),str) or not c['name'].strip():
                    raise ApiError('Każda postać musi mieć imię.',400)
                if c.get('reference_url') and (not isinstance(c['reference_url'],str) or not c['reference_url'].startswith('https://') or len(c['reference_url'])>2000):
                    raise ApiError('Referencja postaci musi być adresem HTTPS nie dłuższym niż 2000 znaków',400)
                cleaned.append({k:str(c.get(k,''))[:1500] for k in ('id','name','look','personality','avoid')}
                               | {'reference_url':str(c.get('reference_url',''))[:2000]})
            if p.get('v83_reference_mode'):raise ApiError('W V8.3 zmiana wyglądu wymaga najpierw wyłączenia i ponownej akceptacji Character Bible',409)
            p['cast']=cleaned
            for shot in p.get('shots',[]):
                if 'dialogue' in data or 'speaker' in data or 'acting_direction' in data:
                    shot.pop('v7_voice',None)
                    shot['v7_lips_approved']=False
                    shot.pop('v8_voice_approved_id',None)
                    shot['voice_status']='needs_recording' if str(shot.get('dialogue','')).strip() else 'not_applicable'
                shot.pop('quote',None);shot.pop('image_quote',None)
                shot.pop('media_url',None);shot.pop('image_url',None)
                shot['edit_version']=str(uuid.uuid4());shot['qc_approved']=False;shot.pop('ui_provenance',None)
            p['updated']=engine.now();self.db.save_project(p)
            return self.send_json({'project':p})
        if suffix=='/claims' and method=='PUT':
            data=self.read_json();p=self.get_project(id)
            p['claims_approved']=data.get('approved') is True
            p['updated']=engine.now();self.db.save_project(p)
            return self.send_json({'project':p,'issues':engine.validate_story(p)})
        if suffix=='/qa' and method=='GET':return self.send_json({'issues':engine.validate_story(self.get_project(id))})
        keyframe=re.fullmatch('/shots/'+SID+'/keyframe(?:/(sync))?',suffix)
        if keyframe:
            shot_id,action=keyframe.groups();p=self.get_project(id)
            shot=next((x for x in p.get('shots',[]) if x['id']==shot_id),None)
            if not shot or shot.get('mode')!='t2v':raise ApiError('Nieznane ujęcie wideo',404)
            folder=ROOT/'data'/'keyframes'/id;folder.mkdir(parents=True,exist_ok=True)
            if method=='PUT' and not action:
                try:size=int(self.headers.get('Content-Length','0'))
                except ValueError:raise ApiError('Nieprawidłowy rozmiar',400)
                if not 20<=size<=12*1024*1024:raise ApiError('Maksymalny rozmiar klatki: 12 MB',413)
                kind=self.headers.get('Content-Type','').split(';')[0]
                if kind not in ('image/png','image/jpeg'):raise ApiError('Wymagany PNG/JPG',415)
                content=self.rfile.read(size)
                if len(content)!=size or not (content.startswith(b'\x89PNG\r\n\x1a\n') if kind=='image/png' else content.startswith(b'\xff\xd8\xff')):
                    raise ApiError('Uszkodzony obraz',400)
                filename=shot_id+('.png' if kind=='image/png' else '.jpg')
                (folder/filename).write_bytes(content)
                try:visual_lock_v82.verify_image(folder/filename)
                except ValueError as e:
                    (folder/filename).unlink(missing_ok=True)
                    raise ApiError(str(e),400) from None
                shot['firstframe_local']=filename
                shot.pop('v82_frame_approval',None);shot.pop('v82_synced_sha256',None);shot.pop('v82_synced_at',None)
                shot.pop('image_url',None);shot.pop('quote',None);shot.pop('workflow_id',None)
                shot['qc_approved']=False;shot['edit_version']=str(uuid.uuid4())
                p['updated']=engine.now();self.db.save_project(p)
                return self.send_json({'project':p,'uploaded':True})
            if method=='POST' and action=='sync':
                request=self.read_json()
                if request.get('approve') is not True:raise ApiError('Wymagana zgoda na przesłanie klatki do Sogni',403)
                file=folder/shot.get('firstframe_local','')
                if not shot.get('firstframe_local') or not file.is_file():raise ApiError('Najpierw wybierz i wyślij klatkę lokalnie',409)
                if p.get('v82_visual_lock'):
                    problems=visual_lock_v82.check_frame(p,shot,ROOT)
                    if problems:raise ApiError('V8.2: '+'; '.join(problems),409)
                result=sogni.upload_reference_image(file,'image/png' if file.suffix=='.png' else 'image/jpeg')
                shot['image_url']=result['url'];shot['video_model']='minimax-h3-fasth3-i2v-turbo'
                if p.get('v82_visual_lock'):
                    shot['v82_synced_sha256']=(shot.get('v82_frame_approval') or {}).get('sha256')
                    shot['v82_synced_at']=datetime.now(UTC).isoformat(timespec='seconds')
                shot.pop('quote',None)
                if not p.get('v82_visual_lock'):shot['edit_version']=str(uuid.uuid4())
                p['updated']=engine.now();self.db.save_project(p)
                return self.send_json({'project':p,'uploaded':True,'expires_hint_hours':48})
            raise ApiError('Niedozwolona metoda',405)
        s=re.fullmatch('/shots/'+SID+'(?:/(quote|render|image-quote|image-render))?',suffix)
        if s:
            shot_id,action=s.groups();p=self.get_project(id)
            if p.get('storyboard_stale'):
                raise ApiError('Storyboard jest nieaktualny. Zsynchronizuj ze scenariuszem.',409)
            shot=next((x for x in p.get('shots',[]) if x['id']==shot_id),None)
            if not shot:raise ApiError('Ujęcie nie istnieje',404)
            if action is None and method=='PUT':
                data=self.read_json()
                allowed={'beat','dialogue','speaker','acting_direction','camera','prompt','generation_seconds','video_model','reference_image_urls','characters'}
                for k in allowed & data.keys():
                    v=data[k]
                    if k=='generation_seconds':
                        v=float(v)
                        if not 5.17<=v<=15.08:raise ApiError('Czas generacji H3: 5.17–15.08 s')
                    elif k=='speaker':
                        if v not in ('ONA','ON','WUJEK',''):raise ApiError('Mówca musi należeć do obsady',400)
                        if v and v not in data.get('characters',shot.get('characters') or []):raise ApiError('Postać mówiąca musi być w ujęciu',409)
                    elif k=='characters':
                        if not isinstance(v,list) or len(v)>4 or not all(isinstance(x,str) and x in [c.get('id') for c in p.get('cast',[])] for x in v):
                            raise ApiError('Podaj od 0 do 4 ID postaci istniejących w obsadzie',400)
                    elif k=='reference_image_urls':
                        if not isinstance(v,list) or len(v)>4 or any(not isinstance(u,str) or not u.startswith('https://') or len(u)>2000 for u in v):raise ApiError('Wymagana lista maks. 4 linków HTTPS')
                    elif not isinstance(v,str) or len(v)>7000:raise ApiError('Nieprawidłowy tekst')
                    shot[k]=v
                if 'dialogue' in data or 'speaker' in data or 'acting_direction' in data:
                    shot.pop('v7_voice',None)
                    shot['v7_lips_approved']=False
                    shot.pop('v8_voice_approved_id',None)
                    shot['voice_status']='needs_recording' if str(shot.get('dialogue','')).strip() else 'not_applicable'
                shot.pop('quote',None);shot.pop('image_quote',None)
                shot.pop('media_url',None);shot.pop('image_url',None);shot.pop('workflow_id',None)
                shot['edit_version']=str(uuid.uuid4());shot['qc_approved']=False;shot.pop('ui_provenance',None);p['updated']=engine.now();self.db.save_project(p)
                return self.send_json({'project':p})
            if p.get('v82_visual_lock'):
                errors=visual_lock_v82.check_masters(p,ROOT)
                if action in ('quote','render'):
                    errors+=visual_lock_v82.check_video(p,shot,ROOT)
                if errors:
                    raise ApiError('V8.2 Master Visual Lock: '+'; '.join(dict.fromkeys(errors)),409)
            # V5 has a single effective style and cast prompt for all Sogni operations.
            production_shot=personas.prepare_for_sogni(p,shot,'' if p.get('v82_visual_lock') else style_guide.state(ROOT)['remote_reference_url'])
            if p.get('v82_visual_lock') and action in ('quote','render'):
                production_shot['video_model']='minimax-h3-fasth3-i2v-turbo'
                production_shot['reference_image_urls']=[]
            if p.get('v6_reference_lock') and not p.get('v82_visual_lock'):
                try:
                    refs=reference_v6.resolve_for_shot(shot)
                except ValueError as e:raise ApiError(str(e),409) from None
                if shot.get('characters'):
                    security=reference_v6.review_safety(shot)
                    if not refs or not security['ready']:
                        raise ApiError('V6 Identity Lock: '+('; '.join(security['missing']) or 'brak zatwierdzonych referencji'),409)
                if refs and not shot.get('image_url'):
                    urls=reference_v6.upload_urls(shot)
                    if len(urls)!=len(refs):
                        raise ApiError('V6 Identity Lock: zatwierdzone zdjęcia muszą być najpierw przesłane do Sogni',409)
                    production_shot['reference_image_urls']=list(dict.fromkeys(urls+production_shot.get('reference_image_urls',[])))[:4]
                    if production_shot.get('video_model','').endswith('t2v-turbo'):
                        production_shot['video_model']='minimax-h3-fasth3-r2v-turbo'
                    production_shot['prompt']+=' '+reference_v6.prepare_prompt(p,shot)

            if p.get('v83_reference_mode') and action in ('image-quote','image-render'):
                try:production_shot=reference_v83.prepare_image_request(p,shot,ROOT,production_shot)
                except ValueError as e:raise ApiError('V8.3: '+str(e),409) from None
            if action=='image-quote' and method=='POST':
                quote=sogni.estimate_image(production_shot)
                quote.update(id=str(uuid.uuid4()),created=engine.now())
                shot['image_quote']=quote;p['updated']=engine.now();self.db.save_project(p)
                return self.send_json({'quote':quote})
            if action=='image-render' and method=='POST':
                data=self.read_json()
                if data.get('approve') is not True:raise ApiError('Wymagana zgoda na generowanie w abonamencie Unlimited.',403)
                quote=shot.get('image_quote') or {}
                if quote.get('id')!=data.get('quote_id'):raise ApiError('Wycena obrazu nieaktualna.',409)
                if (datetime.now(UTC)-datetime.fromisoformat(quote['created'])).total_seconds()>300:
                    raise ApiError('Wycena obrazu straciła ważność.',409)
                try:limit=float(data.get('max_capacity_units',0))
                except (ValueError,TypeError):raise ApiError('Nieprawidłowy limit kosztu')
                if not 0<limit<=100000:raise ApiError('Niedozwolony limit kosztu')
                job_id=quote['id']
                with self.db.lock:  # atomic check+claim within this server process
                    saved=self.db.get_job(job_id)
                    try:jobs_v84.require_safe_submission(self.db.jobs(id),shot_id,'image',job_id)
                    except ValueError as e:raise ApiError(str(e),409) from None
                    if saved and saved['cap']!=limit:raise ApiError('Nie można zmienić zatwierdzonego limitu.',409)
                    job=saved or {'id':job_id,'project_id':id,'shot_id':shot_id,'created':engine.now(),
                        'cap':limit,'status':'submitting','workflow_id':None,'kind':'image','shot_generation':p.get('shot_generation'),'edit_version':shot.get('edit_version')}
                    self.db.save_job(job)
                try:
                    result=sogni.start_image(production_shot,limit,job_id)
                    job.update(status=result.get('status','queued'),workflow_id=result['workflowId'],error=None)
                    self.db.save_project(p)
                except sogni.ProviderError as e:
                    job['status']='submission_uncertain' if e.status==503 else 'rejected'
                    job['error']=str(e);self.db.save_job(job);raise
                self.db.save_job(job)
                return self.send_json({'job':job})
            if action=='quote' and method=='POST':
                # Real Sogni estimate is a zero-spend preflight.
                quote=sogni.estimate(production_shot,p['format'])
                quote.update(id=str(uuid.uuid4()),created=engine.now())
                shot['quote']=quote;p['updated']=engine.now();self.db.save_project(p)
                return self.send_json({'quote':quote})
            if action=='render' and method=='POST':
                data=self.read_json()
                if data.get('approve') is not True:raise ApiError('Potwierdź generację w abonamencie Unlimited.',403)
                quote=shot.get('quote') or {}
                if quote.get('id')!=data.get('quote_id'):raise ApiError('Wycena wygasła lub nie dotyczy tego ujęcia.',409)
                age=(datetime.now(UTC)-datetime.fromisoformat(quote['created'])).total_seconds()
                if age>300:raise ApiError('Wycena starsza niż 5 minut. Pobierz aktualną.',409)
                try:limit=float(data.get('max_capacity_units',0))
                except (ValueError,TypeError):raise ApiError('Nieprawidłowy limit kosztu')
                if not 0<limit<=100000:raise ApiError('Limit musi mieścić się w zakresie 0–100000')
                job_id=quote['id']
                with self.db.lock:  # no two simultaneous local requests can submit the same shot
                    saved=self.db.get_job(job_id)
                    try:jobs_v84.require_safe_submission(self.db.jobs(id),shot_id,'video',job_id)
                    except ValueError as e:raise ApiError(str(e),409) from None
                    if saved and saved.get('cap')!=limit:raise ApiError('Dla tej zgody zatwierdzono inny limit.',409)
                    job=saved or {'id':job_id,'project_id':id,'shot_id':shot_id,'created':engine.now(),'cap':limit,'status':'submitting','workflow_id':None,'kind':'video','shot_generation':p.get('shot_generation'),'edit_version':shot.get('edit_version')}
                    self.db.save_job(job)
                # Same idem key across retries prevents double billing.
                try:
                    result=sogni.start_render(production_shot,limit,job_id,p['format'])
                    job.update(status=result.get('status','queued'),workflow_id=result['workflowId'],error=None)
                    shot['workflow_id']=result['workflowId']
                    self.db.save_project(p)
                except sogni.ProviderError as e:
                    job['status']='submission_uncertain' if e.status==503 else 'rejected'
                    job['error']=str(e)
                    self.db.save_job(job)
                    raise
                self.db.save_job(job)
                return self.send_json({'job':job})
        j=re.fullmatch('/jobs/([0-9a-f-]{36})(/cancel)?',suffix)
        if j:
            job=self.db.get_job(j.group(1))
            if not job or job['project_id']!=id:raise ApiError('Nie znaleziono zadania',404)
            if method=='GET' and not j.group(2):
                if job.get('workflow_id'):
                    wf=sogni.get_workflow(job['workflow_id'])
                    job['status']=wf.get('status',job['status'])
                    if job['status']=='completed':
                        for step in wf.get('steps',[]):
                            for a in step.get('artifacts',[]):
                                url=a.get('url')
                                if isinstance(url,str) and url.startswith('https://'):
                                    job['media_url']=url;break
                    self.db.save_job(job)
                    if job.get('media_url'):
                        p=self.get_project(id)
                        for shot in p.get('shots',[]):
                            if shot['id']==job['shot_id'] and p.get('shot_generation')==job.get('shot_generation') and shot.get('edit_version')==job.get('edit_version'):
                                if job.get('kind')=='image':shot['image_url']=job['media_url']
                                else:shot['media_url']=job['media_url']
                        self.db.save_project(p)
                return self.send_json({'job':job})
            if method=='POST' and j.group(2)=='/cancel':
                if not job.get('workflow_id'):raise ApiError('Nie można anulować przed nadaniem ID workflow',409)
                wf=sogni.cancel(job['workflow_id']);job['status']=wf.get('status','cancelled');self.db.save_job(job)
                return self.send_json({'job':job})
        raise ApiError('Nieznany adres lub metoda',404)
    def serve_static(self,path):
        allowed={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/style.css':'style.css','/manifest.json':'manifest.json','/favicon.svg':'favicon.svg','/sw.js':'sw.js'}
        if path not in allowed:raise ApiError('Nie znaleziono zasobu',404)
        file=STATIC/allowed[path]
        if not file.exists():raise ApiError('Brak pliku statycznego',404)
        typ=mimetypes.guess_type(str(file))[0] or 'application/octet-stream'
        return self.send_bytes(file.read_bytes(),typ)
    def process(self,method):
        try:
            if method in ('POST','PUT'):
                origin=self.headers.get('Origin')
                host=self.headers.get('Host','')
                if origin and urlparse(origin).netloc!=host:raise ApiError('Odrzucono żądanie cross-origin.',403)
            self.route(method)
        except ApiError as e:self.send_json({'error':str(e)},e.status)
        except sogni.ProviderError as e:self.send_json({'error':str(e),'provider_status':e.status,'details':e.details},400 if e.status in (400,409,422) else 502)
        except (ValueError,TypeError,OverflowError) as e:self.send_json({'error':str(e)[:450]},400)
        except Exception:
            traceback.print_exc()
            self.send_json({'error':'Błąd serwera; szczegóły w logu lokalnym.'},500)
    def do_GET(self):self.process('GET')
    def do_POST(self):self.process('POST')
    def do_PUT(self):self.process('PUT')


def main():
    ap=argparse.ArgumentParser(description='Nasz Dzien AI Film Studio 8.6')
    ap.add_argument('--host',default='127.0.0.1')
    ap.add_argument('--port',type=int,default=8765)
    ap.add_argument('--data',default=str(ROOT/'data'/'studio.sqlite3'))
    args=ap.parse_args()
    token=os.environ.get('STUDIO_ACCESS_TOKEN','').strip()
    if args.host not in ('127.0.0.1','localhost','::1') and len(token)<8:
        ap.error('Dostęp przez sieć wymaga STUDIO_ACCESS_TOKEN o długości co najmniej 8 znaków.')
    server=ThreadingHTTPServer((args.host,args.port),Handler)
    server.db=Store(args.data);server.access_token=token
    personas.seed_defaults(server.db,ROOT)
    personas.seed_wujek(server.db,ROOT)
    print('NASZ DZIEŃ — FILM DIRECTOR STUDIO 8.6')
    print(f'Otwórz: http://127.0.0.1:{args.port}  (na telefonie adres IP komputera)')
    print(f'Sogni API: {"skonfigurowane (niezweryfikowane)" if sogni.key() else "brak klucza; demo działa"}')
    print('Aby przerwać: Ctrl+C')
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()

"""V8 local, optional Polish voice workbench. No remote API calls.

Chatterbox is an OPTIONAL separate installation. Imported consented recordings
remain first-class, and no audio is silently approved for use in H3.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from studio.dialogue_v7 import audio_probe, dialogue_clean

EMOTIONS = {
    'neutral': {'label':'Spokojnie', 'exaggeration':0.45,'cfg_weight':0.5},
    'surprise': {'label':'Zaskoczenie', 'exaggeration':0.68,'cfg_weight':0.35},
    'warm': {'label':'Czułość', 'exaggeration':0.52,'cfg_weight':0.42},
    'comic': {'label':'Humor', 'exaggeration':0.65,'cfg_weight':0.32},
    'concern': {'label':'Zmartwienie', 'exaggeration':0.56,'cfg_weight':0.44},
}
ALLOWED_ENGINE = ('import','chatterbox')


def validate_request(text, emotion, engine='chatterbox', consent=False):
    if not dialogue_clean(text) or len(text)>280:
        raise ValueError('Jedna kwestia: 1–280 znaków bez znaczników HTML')
    if emotion not in EMOTIONS:raise ValueError('Nieznana emocja')
    if engine not in ALLOWED_ENGINE:raise ValueError('Nieznany silnik głosu')
    if engine=='chatterbox' and not consent:
        raise ValueError('Użycie głosu referencyjnego wymaga potwierdzenia uprawnienia i zgody osoby')
    return EMOTIONS[emotion]


def isolated_dir(root, project_id, shot_id):
    if not (project_id and shot_id and all(ch.isalnum() or ch=='-' for ch in project_id+shot_id)):
        raise ValueError('Nieprawidłowy identyfikator')
    root=Path(root)/'data'/'v8_voice'/project_id/shot_id
    root.mkdir(parents=True,exist_ok=True)
    return root


def voice_probe(path):
    info=audio_probe(path)
    return dict(info, file_size=Path(path).stat().st_size)


def build_variants_request(text,emotion,speaker,reference_path=None):
    preset=validate_request(text,emotion,consent=True)
    if speaker not in ('ONA','ON','WUJEK'):raise ValueError('Nieznana postać')
    return {'language_id':'pl','text':text.strip(),'speaker':speaker,'emotion':emotion,
            'variants':[
                {'exaggeration':preset['exaggeration'],'cfg_weight':preset['cfg_weight']},
                {'exaggeration':min(0.95,round(preset['exaggeration']+0.12,2)),
                 'cfg_weight':max(0.0,round(preset['cfg_weight']-0.1,2))}],
            'reference_path':str(reference_path) if reference_path else None,
            'generated':False,'needs_human_review':True}


def run_chatterbox(request,directory, max_seconds=180):
    """Only after explicit local user consent; launches dedicated local subprocess.
    Worker imports heavy dependencies; no auto-install, no paid fallback.
    """
    folder=Path(directory);folder.mkdir(parents=True,exist_ok=True)
    args={'language_id':'pl','text':request['text'],
          'reference_path':request.get('reference_path'),
          'variants':request['variants'],'output_dir':str(folder.resolve())}
    worker=Path(__file__).resolve().parent/'chatterbox_worker_v8.py'
    try:
        result=subprocess.run([os.environ.get('V8_TTS_PYTHON') or sys.executable,str(worker)],input=json.dumps(args),text=True,
            capture_output=True,timeout=max_seconds,
            env={k:v for k,v in os.environ.items() if k not in ('SOGNI_API_KEY','SOGNI_TOKEN')})
    except subprocess.TimeoutExpired:
        raise ValueError('Lokalny TTS przekroczył limit. Sprawdź GPU i log bez sekretów.') from None
    if result.returncode:
        raise ValueError('Lokalny Chatterbox nie uruchomił się. Sprawdź instalację chatterbox-tts, PyTorch i dostęp do GPU. '+result.stderr[-250:])
    try:response=json.loads(result.stdout.strip().splitlines()[-1])
    except Exception:raise ValueError('Chatterbox nie zwrócił poprawnego wyniku') from None
    out=[]
    for path in response['files']:
        f=Path(path).resolve()
        if not f.is_relative_to(folder.resolve()):raise ValueError('TTS zwrócił plik spoza katalogu projektu')
        out.append({'id':f.stem,'file':str(f), 'audio':voice_probe(f),
                    'approved':False,'origin':'local_chatterbox','language':'pl-PL'})
    if not out:raise ValueError('Chatterbox nie utworzył poprawnego audio')
    return out


def manifest(shot):
    return {'variants':[{k:v for k,v in x.items() if k!='file'} for x in shot.get('v8_voice_variants',[])],
            'approved_id':shot.get('v8_voice_approved_id'),
            'notes':'Każdy plik wymaga ręcznego odsłuchu, potwierdzenia wymowy i zgody na użycie głosu.'}


def approve(shot,variant_id,confirm):
    if confirm is not True:raise ValueError('Wymagany odsłuch i świadome zatwierdzenie')
    entry=next((v for v in shot.get('v8_voice_variants',[]) if v['id']==variant_id),None)
    if not entry:raise ValueError('Nie znaleziono wariantu')
    if voice_probe(entry['file'])['sha256'] != entry['audio']['sha256']:
        raise ValueError('Plik głosu zmienił się od ostatniej kontroli')
    for v in shot['v8_voice_variants']:v['approved']=v is entry
    shot['v8_voice_approved_id']=variant_id
    return entry

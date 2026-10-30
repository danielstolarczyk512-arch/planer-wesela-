"""Safe CLI bridge to Sogni FastH3 IA2V: own Polish voice drives lips.
Calls are deny-by-default and never fall back to premium models/tokens.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from studio import sogni
from studio.dialogue_v7 import audio_probe, prompt_for_speaker

ROOT=Path(__file__).resolve().parent.parent
OUTPUTS=ROOT/'data'/'v7_renders'
MODEL='minimax-h3-fasth3-ia2v-turbo'

def recipe(shot,voice_info,source,output=None):
    if voice_info.get('model')!=MODEL or voice_info.get('language')!='pl-PL':raise ValueError('Nieprawidłowy plan dialogu')
    sound=Path(voice_info['voice_path']).resolve()
    if not sound.is_file():raise ValueError('Nie znaleziono nagrania')
    duration=audio_probe(sound)['seconds']
    if duration>15.08:raise ValueError('Nagranie przekracza limit H3')
    if not source or str(source).startswith('http://'):
        raise ValueError('Wymagany zatwierdzony obraz źródłowy jako lokalny PNG/JPG lub HTTPS')
    # Local reference asset and HTTPS signed URLs are supported by the CLI.
    if str(source).startswith('https://'):
        if len(str(source))>2500:raise ValueError('Za długi link do obrazu')
        src=str(source)
    else:
        f=Path(source).resolve()
        if not f.is_file() or f.suffix.lower() not in ('.png','.jpg','.jpeg'):raise ValueError('Brak obrazu referencyjnego')
        src=str(f)
    target=Path(output or OUTPUTS/(str(uuid.uuid4())+'.mp4')).resolve()
    if not target.is_relative_to(OUTPUTS.resolve()):
        raise ValueError('Wynik musi znajdować się w folderze renderów V7')
    text=prompt_for_speaker(voice_info['speaker'],voice_info['transcript'],voice_info.get('camera_preset','speaker_closeup'))
    args=['sogni-agent','--json','--video','-m',MODEL,'--billing-mode','subscription',
          '--ref',src,'--ref-audio',str(sound),'--duration',str(round(max(5.17,duration),2)),
          '-o',str(target),text]
    return {'dry_run':True,'arguments':args,'output':str(target),'mode':'subscription',
            'audio_preparation': 'Dla nagrań krótszych niż 5,17s program uzupełnia WAV ciszą do 5,2s przed wysłaniem; oryginał pozostaje nienaruszony.',
            'note':'Wykonaj tylko po potwierdzeniu aktywnego Unlimited. Brak auto/premium fallback.',
            'source_audio_hash':voice_info.get('audio',{}).get('sha256')}

def generate_once(shot,voice_info,source,approve=False,timeout=1800):
    if approve is not True:raise ValueError('Wymagane świadome zatwierdzenie JEDNEJ generacji')
    plan=recipe(shot,voice_info,source)
    if not sogni.key():raise ValueError('Brak SOGNI_API_KEY')
    sogni.assert_active_subscription()
    if not shutil.which('sogni-agent'):raise ValueError('Zainstaluj oficjalny sogni-agent (Node >=22.11).')
    OUTPUTS.mkdir(parents=True,exist_ok=True)
    arguments=plan['arguments'].copy()
    duration=audio_probe(voice_info['voice_path'])['seconds']
    if duration<5.17:
        padded=OUTPUTS/(Path(plan['output']).stem+'-padded.wav')
        prep=subprocess.run(['ffmpeg','-v','error','-y','-i',voice_info['voice_path'],
             '-af','apad,atrim=duration=5.2','-ar','48000','-ac','1','-c:a','pcm_s16le',str(padded)],
             capture_output=True,text=True,timeout=40)
        if prep.returncode or not padded.is_file():raise ValueError('Nie udało się przygotować krótkiej wypowiedzi w FFmpeg')
        arguments[arguments.index('--ref-audio')+1]=str(padded)
    try:
        p=subprocess.run(arguments,capture_output=True,text=True,timeout=timeout,
                 env={**os.environ,'SOGNI_BILLING_MODE':'subscription'})
    except subprocess.TimeoutExpired:
        raise ValueError('Przekroczono limit oczekiwania. Przed ponowieniem sprawdź status zadania Sogni.') from None
    raw=(p.stdout or '')[-15000:]
    if p.returncode:
        raise ValueError('Niepowodzenie Sogni IA2V. Sprawdź lokalny status zadania; nie ponawiaj automatycznie.')
    # A successful CLI exit or ready MP4 doesn't prove no Spark; require reported payment model.
    if not re.search(r'"(?:paymentModel|payment_model|billingMode|billing_mode)"\s*:\s*"subscription"',raw):
        raise ValueError('Nie udało się potwierdzić rozliczenia subscription w odpowiedzi CLI. Przed dalszą pracą skontroluj konto.')
    f=Path(plan['output'])
    if not f.is_file() or f.stat().st_size<1024:raise ValueError('Brak prawidłowego MP4 w wyjściu Sogni')
    return {'file':str(f),'payment_model':'subscription','approved_for_montage':False,
            'lip_sync_verified':False,'technical_size':f.stat().st_size}

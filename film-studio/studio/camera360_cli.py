"""On-demand **single-angle only** Sogni 360 CLI integration.
This is the sole external call path for 360 in V6. Never starts bulk 360 jobs.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import uuid
from pathlib import Path

from studio import camera360, reference_v6, sogni

ROOT=Path(__file__).resolve().parent.parent
RENDERS=ROOT/'data'/'camera360'
_MUTEX=threading.Lock()


def _normalize_to_png(file):
    """CLI potrafi zapisać JPEG/WEBP pod nazwą .png — sprawdzamy sygnaturę i, jeśli trzeba, zapisujemy prawdziwy PNG."""
    head=file.read_bytes()[:12]
    if head[:8]==bytes([0x89])+b'PNG'+bytes([13,10,26,10]):return True
    if head[:3]==bytes([0xff,0xd8,0xff]) or (head[:4]==b'RIFF' and head[8:12]==b'WEBP'):
        try:
            from PIL import Image
            with Image.open(file) as im:im.convert('RGB').save(file,'PNG')
            return True
        except Exception:return False
    return False


def _output_size(path,long_edge=1152):
    """Rozmiar wyniku z proporcjami źródła (wielokrotności 32); CLI bez -w/-h renderuje kwadrat 512x512."""
    try:
        from PIL import Image
        with Image.open(path) as im:sw,sh=im.size
    except Exception:
        return 1024,1024
    k=long_edge/max(sw,sh)
    r32=lambda v:max(256,int(round(v*k/32))*32)
    return r32(sw),r32(sh)


def _safe_tail(result,limit=900):
    import re
    text=" ".join([(result.stderr or ""),(result.stdout or "")]).strip()
    key=sogni.key()
    if key:text=text.replace(key,"[KEY]")
    text=re.sub(r"https?://\S+","[URL]",text)
    text=re.sub(r"\s+"," ",text)
    hits=[m.group(0) for m in re.finditer(r"[^.{}\"]{0,80}(?:[Ee]rror|[Ff]ailed|[Ff]ilter|[Rr]equire|denied|not allowed)[^.{}\"]{0,160}",text)]
    return (" | ".join(dict.fromkeys(hits))[:400]+" || "+text[-(limit-400):]) if hits else text[-limit:]


def generate_one(reference_id,azimuth,elevation,distance,approve=False):
    if approve is not True:raise ValueError('Wymagana świadoma zgoda na jeden render w Unlimited')
    p=camera360.point(azimuth,elevation,distance)
    ref=reference_v6.find(reference_id)
    if ref['review']!='approved':raise ValueError('Zatwierdź referencję, zanim wykonasz generację')
    program=shutil.which('sogni-agent')
    if not program:raise ValueError('Brak sogni-agent. Zainstaluj oficjalny Creative Agent CLI (Node >= 22.11).')
    if not sogni.key():raise ValueError('Brak SOGNI_API_KEY na serwerze')
    if not _MUTEX.acquire(blocking=False):raise ValueError('Trwa już render 360. W V6 tylko jedno zadanie jednocześnie.')
    try:
        sogni.assert_active_subscription()
        asset=reference_v6.file_for(reference_id)
        RENDERS.mkdir(parents=True,exist_ok=True)
        task_id=str(uuid.uuid4())
        file=RENDERS/(task_id+'.png')
        w,h=_output_size(asset)
        cmd=[program,'--multi-angle','--billing-mode','subscription','--token-type','spark','-w',str(w),'-h',str(h),
             '--json','--no-update-check','--output-format','png','-c',str(asset),'--azimuth',p['azimuth'],
             '--elevation',p['elevation'],'--distance',p['distance'],'--angle-strength','0.9',
             '-o',str(file), 'single unchanged approved animation character, same Golden Storybook 3D design, no split screen']
        env=os.environ.copy()
        env['SOGNI_NO_UPDATE_CHECK']='1'
        try:
            result=subprocess.run(cmd,env=env,cwd=str(ROOT),capture_output=True,text=True,
                                  timeout=900,check=False)
        except subprocess.TimeoutExpired:
            raise RuntimeError('CLI nie odpowiedział w limicie czasu; sprawdź historię zadań Sogni przed ponowieniem') from None
        if result.returncode!=0:
            # Diagnostyka bez wycieku: usuwamy klucz API i podpisane adresy, zostawiamy ostatnie linie komunikatu CLI.
            raise RuntimeError('Sogni 360: zadanie nie powiodło się; kod CLI '+str(result.returncode)+'. '+_safe_tail(result)+' Sprawdź konto/limity/CLI.')
        if not file.exists():
            # CLI dopisuje nazwę kąta do pliku (np. <id>-front-right.png) — wskazany przez nas plik nie powstaje.
            found=sorted(RENDERS.glob(task_id+'*.png'),key=lambda f:f.stat().st_mtime,reverse=True)
            if found:found[0].replace(file)
        if not file.exists() or file.stat().st_size<512 or not _normalize_to_png(file):
            raise RuntimeError('Brak prawidłowego wyjściowego obrazu. Nie zatwierdzaj niekompletnej generacji.')
        payment='not_reported'
        try:
            data=json.loads(result.stdout.strip())
            if isinstance(data,dict):
                payment=data.get('paymentModel') or data.get('payment_model') or data.get('data',{}).get('paymentModel') or payment
        except (ValueError,TypeError,AttributeError):pass
        # --billing-mode subscription enforces server-side fail-closed, but
        # unreported paymentModel is not evidence of the actual final ledger.
        meta={'render_id':task_id,'reference_id':reference_id,'camera':p,
              'billing_mode_requested':'subscription','payment_model_reported':str(payment)[:64],
              'qc_approved':False,'source':'sogni-agent-multi-angle'}
        (RENDERS/(task_id+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')
        return meta
    finally:
        _MUTEX.release()


def fetch_image(render_id):
    try:uuid.UUID(render_id)
    except (TypeError,ValueError):raise ValueError('Nieznany identyfikator renderu') from None
    f=RENDERS/(render_id+'.png')
    if not f.is_file():raise ValueError('Nie znaleziono wygenerowanego obrazu')
    return f

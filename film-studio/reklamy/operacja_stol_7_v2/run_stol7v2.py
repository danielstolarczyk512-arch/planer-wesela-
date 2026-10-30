"""Uruchomienie etapów OPERACJA STÓŁ 7 V2: python run_stol7v2.py keyframes|sheet|clips"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from studio import film5
from studio import film_stol7v2 as F
from studio.film5 import Project

pr = Project(F.PROJECT)
cmd = sys.argv[1]
only = sys.argv[2].split(',') if len(sys.argv) > 2 else None
if cmd == 'keyframes':
    shots = [s for s in F.SHOTS if s['mode'] != 'reuse']
    film5.gen_keyframes(pr, shots, cands=tuple(sys.argv[3]) if len(sys.argv) > 3 else ('a', 'b'), only=only, workers=3)
elif cmd == 'sheet':
    from PIL import Image, ImageDraw
    ids = [s['id'] for s in F.SHOTS if s['mode'] != 'reuse']
    items = [(i, c) for i in ids for c in 'abc' if pr.p('keyframes', f'{i}_{c}.png').exists()]
    w, h = 300, 533
    sh = Image.new('RGB', (6 * w, ((len(items) + 5) // 6) * h), 'white')
    for k, (i, c) in enumerate(items):
        im = Image.open(pr.p('keyframes', f'{i}_{c}.png')).convert('RGB').resize((w, h)); d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 70, 16), fill='black'); d.text((3, 2), f'{i}_{c}', fill='white'); sh.paste(im, ((k % 6) * w, (k // 6) * h))
    out = pr.p('qc', 'keyframes_sheet.png'); sh.save(out); print(out)
elif cmd == 'approve':
    import hashlib
    import subprocess
    CH = {'v02': 'v02_a', 'v04': 'v04_c', 'v06': 'v06_b', 'v07': 'v07_c', 'v08': 'v08_a'}
    for sid, key in CH.items():
        pr.s['approved'][sid] = key
        pr.s.setdefault('approval_notes', {})[key] = {'sha256': hashlib.sha256(pr.p('keyframes', key + '.png').read_bytes()).hexdigest(),
            'by': 'przegląd wzrokowy operatora (Claude) wobec MASTER V8.5; wymaga potwierdzenia właściciela', 'master_sha256': 'de22112ef788c9a5e9ee71b8b540e99a9dc298c5996b0d3bcfe9911f14bf7331'}
    pr.save()
elif cmd == 'clips':
    import math
    import subprocess
    import uuid

    from studio import ia2v_rest as R
    from studio import sogni
    from studio.film5 import (
        art_url,
        assert_free,
        download,
        gate,
        ledger,
        poll,
        retry,
        step_cost,
        total_units,
        usage_snapshot,
    )
    TAKES = {'v02': 'M1_C', 'v04': 'K1_C', 'v07': 'M2_B'}
    SRC = r'D:\film-studio\OPERACJA_STOL_7_V2\POLISH_VOICES\takes'
    before = usage_snapshot()
    i2v = [s for s in F.SHOTS if s['mode'] == 'i2v' and (not only or s['id'] in only)]
    for s in i2v:
        s['say'] = None; s['seconds'] = 5.2   # H3 generuje min. 5,17 s; w montażu użyjemy krótkiego okna
    film5.gen_clips(pr, i2v)
    for s in [x for x in F.SHOTS if x['mode'] == 'ia2v' and (not only or x['id'] in only)]:
        sid = s['id']; dest = pr.p('clips', sid + '.mp4')
        if dest.exists() or pr.s['clips'].get(sid, {}).get('attempts', 0) >= 2:
            continue
        raw = os.path.join(SRC, TAKES[sid] + '.wav'); pad = pr.p('audio', sid + '_pad.wav')
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', raw, '-af', 'silenceremove=start_periods=1:start_threshold=-45dB,adelay=200|200,apad=whole_dur=5.2', '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', str(pad)], check=True)
        gate(pr)
        key = pr.s['approved'][sid]
        iu = retry(sogni.upload_reference, pr.p('keyframes', key + '.png').read_bytes(), 'image/png', 1); au = retry(R.upload_audio, pad)
        prompt = ('The character speaks Polish: lips, jaw and cheeks move naturally in sync with the voice in the audio, restrained expressive eyebrows, subtle head movement. '
                  f'{s["action"]} Keep the same face, eye proportions, hairstyle and outfit as in the first frame, same warm lighting, same camera framing; the mouth rests closed during the silent pauses; no text; the soundtrack is only the voice.')
        body = R.ia2v_body(sid, prompt, iu, au, 5.2); est = retry(R.quote, body); tot = total_units(est)
        body['confirm_cost'] = True; body['max_estimated_capacity_units'] = max(2.0, math.ceil(tot * 1.4))
        wf = retry(R.start, body, str(uuid.uuid4()))
        pr.s['clips'][sid] = {'wf': wf['workflowId'], 'status': 'running', 'attempts': pr.s['clips'].get(sid, {}).get('attempts', 0) + 1, 'from': key, 'mode': 'ia2v', 'take': TAKES[sid]}; pr.save()
        pr.log(f'start IA2V {sid} {wf["workflowId"]} wycena {tot:g}')
        r = poll(wf['workflowId']); u = art_url({x.get('id'): x for x in r.get('steps', [])}.get('clip'))
        ledger(pr, stage='ia2v', shot=sid, workflow=wf['workflowId'], estimate=tot, **step_cost(r))
        if u:
            download(u, dest); pr.s['clips'][sid]['status'] = 'done'; pr.log('gotowy IA2V ' + sid)
        else:
            pr.s['clips'][sid]['status'] = 'missing'; pr.log('BRAK IA2V ' + sid)
        pr.save()
    after = usage_snapshot(); assert_free(before, after, 'klipy V2'); ledger(pr, stage='clips-audit', before=before, after=after)
    print('limit dzienny %', after['fair_daily_pct'], 'sparkSpent', after['sparkSpent'], 'paidSparkSpent', after['paidSparkSpent'], 'spark', after['spark_net'])
print(json.dumps({k: v.get('status') for k, v in pr.s['keyframes'].items()}))

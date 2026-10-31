"""Kreator referencji: nowe postacie i lokalizacje -> zestaw zatwierdzonych obrazów (V8.7).

Dwa rodzaje (`kind`): "character" i "location". Dwa style: "realistic" (jak prawdziwa reklama aktorska) i "animated" (Golden Storybook).
Przebieg: create -> plan -> generate_anchor (kandydaci) -> approve_anchor -> generate_set (pozostałe widoki z kotwicą jako 1. referencją)
-> approve_view / manifest.json z SHA-256. Wszystko w planie Unlimited: billing_mode=subscription, wycena przed startem,
kontrola fair-use i salda Spark przed i po partii (HaltError). Klucz tylko ze zmiennej SOGNI_API_KEY.
"""
import hashlib
import json
import math
import re
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import sogni

ROOT = Path(__file__).resolve().parent.parent / 'data' / 'references_forge'
FLUX = 'flux-3-klein'
SIZES = {'character': {'portrait': (768, 1024), 'full': (768, 1360)}, 'location': {'wide': (1360, 768), 'tall': (768, 1360)}}
FAIR_USE_STOP_PCT = 92.0
TERMINAL = ('completed', 'failed', 'partial_failure', 'cancelled', 'canceled')
STYLES = {
    'realistic': ('Photorealistic live-action photograph, as in a premium commercial: real human skin texture, real fabric, cinema camera, '
                  'natural light. NOT animated, NOT a cartoon, NOT a 3D render, NOT an illustration.'),
    'animated': ('Stylized 3D animated-film look (warm golden storybook CGI): painted skin, soft contours, rich warm light; NOT photorealistic.'),
}
CHARACTER_VIEWS = [  # id, etykieta, opis ujęcia, rozmiar
    ('front', 'Przód, neutralnie', 'head and shoulders portrait facing the camera, calm neutral friendly expression, plain soft neutral background', 'portrait'),
    ('left34', 'Trzy czwarte w lewo', 'head and shoulders, face turned three-quarters to the left, plain soft background', 'portrait'),
    ('right34', 'Trzy czwarte w prawo', 'head and shoulders, face turned three-quarters to the right, plain soft background', 'portrait'),
    ('profile', 'Profil', 'head and shoulders in clean side profile, plain soft background', 'portrait'),
    ('smile', 'Uśmiech', 'head and shoulders facing the camera, a warm natural smile, plain soft background', 'portrait'),
    ('surprised', 'Zdziwienie', 'head and shoulders facing the camera, raised eyebrows, slightly surprised, plain soft background', 'portrait'),
    ('serious', 'Powaga', 'head and shoulders facing the camera, serious focused expression, plain soft background', 'portrait'),
    ('full_front', 'Cała sylwetka', 'full body standing, front view, relaxed pose, plain soft studio backdrop, whole body and shoes visible', 'full'),
]
LOCATION_VIEWS = [
    ('wide_evening', 'Plan ogólny, wieczór', 'wide establishing shot of the whole place in warm evening light', 'wide'),
    ('wide_day', 'Plan ogólny, dzień', 'the same place in bright natural daylight, wide shot', 'wide'),
    ('medium_left', 'Plan średni z lewej', 'medium shot from the left side of the same place', 'wide'),
    ('medium_right', 'Plan średni z prawej', 'medium shot from the right side of the same place', 'wide'),
    ('detail', 'Detal', 'close detail of the decor and table setting of the same place, shallow depth of field', 'wide'),
    ('high_angle', 'Z góry', 'high angle view over the whole place', 'wide'),
]
ANCHOR = {'character': 'front', 'location': 'wide_evening'}


class HaltError(RuntimeError):
    """Zatrzymanie ze względów kosztowych/limitów — stan jest zapisany, można wznowić."""


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _slug(text):
    s = re.sub(r'[^a-z0-9]+', '_', str(text).lower().translate(str.maketrans('ąćęłńóśźż', 'acelnoszz'))).strip('_')
    return (s or 'bez_nazwy')[:40]


def views_for(kind):
    return CHARACTER_VIEWS if kind == 'character' else LOCATION_VIEWS


def _dir(eid):
    if not re.fullmatch(r'[a-z0-9_]{1,50}', eid):
        raise ValueError('Nieprawidłowy identyfikator')
    return ROOT / eid


def _load(eid):
    f = _dir(eid) / 'meta.json'
    if not f.exists():
        raise KeyError('Nie ma takiego zestawu referencji')
    return json.loads(f.read_text(encoding='utf8'))


def _save(meta):
    d = _dir(meta['id']); d.mkdir(parents=True, exist_ok=True)
    tmp = d / 'meta.tmp'; tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf8'); tmp.replace(d / 'meta.json')


def create(kind, name, description, style='realistic', source_images=(), extra=''):
    """Tworzy zestaw. source_images: do 3 lokalnych plików (png/jpg/webp) jako źródło tożsamości/miejsca; bez nich generujemy z opisu."""
    if kind not in ('character', 'location'):
        raise ValueError('kind: character albo location')
    if style not in STYLES:
        raise ValueError('style: realistic albo animated')
    if len(description.strip()) < 15:
        raise ValueError('Opis jest za krótki (min. 15 znaków)')
    if len(source_images) > 3:
        raise ValueError('Maksymalnie 3 obrazy źródłowe')
    eid = _slug(name)
    if (_dir(eid) / 'meta.json').exists():
        eid = f'{eid}_{uuid.uuid4().hex[:6]}'
    d = _dir(eid); (d / 'source').mkdir(parents=True, exist_ok=True)
    srcs = []
    for i, p in enumerate(source_images):
        p = Path(p)
        if p.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp') or not p.is_file() or p.stat().st_size > 16_000_000:
            raise ValueError(f'Nieprawidłowy obraz źródłowy: {p.name}')
        dst = d / 'source' / f'src{i + 1}{p.suffix.lower()}'; dst.write_bytes(p.read_bytes())
        srcs.append({'file': dst.name, 'sha256': hashlib.sha256(dst.read_bytes()).hexdigest()})
    meta = {'id': eid, 'kind': kind, 'name': name.strip()[:80], 'description': description.strip()[:1500], 'extra': extra.strip()[:800], 'style': style, 'created': now(),
            'sources': srcs, 'images': {}, 'approved': {}, 'anchor': None, 'units': 0.0, 'ledger': [], 'log': []}
    _save(meta)
    return meta


def view_prompt(meta, view_id):
    v = {x[0]: x for x in views_for(meta['kind'])}[view_id]
    who = 'the character' if meta['kind'] == 'character' else 'the place'
    has_src = bool(meta['sources'])
    head = STYLES[meta['style']]
    if meta['kind'] == 'character':
        base = (f'{head} Reference sheet image of ONE fictional adult character: {meta["description"]} {meta["extra"]} '
                f'SHOT: {v[2]}. ONLY ONE PERSON in the frame, no other people, no text, letters, numbers or logos, no collage, no split screen.')
    else:
        base = (f'{head} Reference image of ONE location: {meta["description"]} {meta["extra"]} SHOT: {v[2]}. '
                'No people in the frame, no text, letters, numbers or logos, no collage, no split screen.')
    if view_id != ANCHOR[meta['kind']] and meta['anchor']:
        base += (f' The first reference image is the APPROVED anchor of {who}: keep exactly the same ' +
                 ('face, hairstyle, skin, age and outfit.' if meta['kind'] == 'character' else 'architecture, materials, colours, decor and layout.'))
    elif has_src:
        if meta['style'] == 'realistic':
            base += (f' The reference images may show {who} in a stylized animated or illustrated look: recreate exactly this ' + ('person' if meta['kind'] == 'character' else 'place') +
                     ' as a REAL photograph' + (' of a real human being with natural human eye proportions (do NOT enlarge the eyes), real skin and hair, keeping the same face structure, hairstyle and clothes.' if meta['kind'] == 'character' else ' of a real place, keeping the same architecture and decor.'))
        else:
            base += f' The reference images show {who}: reproduce exactly this ' + ('person.' if meta['kind'] == 'character' else 'place.')
    return base + ' Vertical or horizontal framing as specified, one continuous full-frame picture.'


# ---------------------------------------------------------------- konto i limity
def usage_snapshot():
    _, bal = sogni.request('GET', '/v4/account/balance', timeout=25)
    _, use = sogni.request('GET', '/v1/subscriptions/usage', timeout=25)
    _, hist = sogni.request('GET', '/v1/subscriptions/usage/history?days=7', timeout=25)
    t = hist['data']['totals']; u = use['data']
    return {'at': now(), 'spark_net': float(bal['data']['spark']['net']), 'sogni_net': float(bal['data']['sogni']['net']),
            'sparkSpent': t.get('sparkSpent', 0), 'paidSparkSpent': t.get('paidSparkSpent', 0),
            'fair_limited': bool(u['fairUse']['limited']), 'fair_daily_pct': u['fairUse']['daily']['usedPct']}


def assert_free(before, after, what):
    if (after['sparkSpent'] > before['sparkSpent'] or after['paidSparkSpent'] > before['paidSparkSpent']
            or after['spark_net'] < before['spark_net'] - 1e-9 or after['sogni_net'] < before['sogni_net'] - 1e-9):
        raise HaltError(f'WYKRYTO WZROST KOSZTU po „{what}” — zatrzymano: przed={before} po={after}')


def gate():
    s = usage_snapshot()
    if s['fair_limited'] or s['fair_daily_pct'] >= FAIR_USE_STOP_PCT:
        raise HaltError(f'fair-use: {s["fair_daily_pct"]}% dziennego limitu (limited={s["fair_limited"]}) — zatrzymano, limitów nie omijamy')
    return s


# ---------------------------------------------------------------- Sogni
def _upload(data, mime, slot):
    q = urllib.parse.urlencode({'type': f'contextImage{int(slot)}', 'jobId': str(uuid.uuid4()), 'contentType': mime})
    _, r = sogni.request('GET', '/v1/image/uploadUrl?' + q, timeout=20)
    up = (r.get('data') or {}).get('uploadUrl')
    if not isinstance(up, str) or not up.startswith('https://'):
        raise sogni.ProviderError('Sogni nie zwróciło adresu wysyłki.')
    req = urllib.request.Request(up, data=data, method='PUT', headers={'Content-Type': mime, 'User-Agent': 'NaszDzienFilmStudio/8.7'})
    with urllib.request.urlopen(req, timeout=90) as resp:   # adres jest podpisany: nie wysyłamy tam klucza API
        if resp.status not in (200, 201, 204):
            raise sogni.ProviderError('Wysyłka obrazu nie powiodła się.')
    _, r = sogni.request('GET', '/v1/image/downloadUrl?' + q, timeout=20)
    url = (r.get('data') or {}).get('downloadUrl')
    if not isinstance(url, str) or not url.startswith('https://'):
        raise sogni.ProviderError('Sogni nie zwróciło adresu obrazu.')
    return url


def _mime(p):
    return {'.png': 'image/png', '.webp': 'image/webp'}.get(Path(p).suffix.lower(), 'image/jpeg')


def build_body(step_id, prompt, ref_urls, size, confirm=False, max_units=None):
    """edit_image (FLUX 3 Klein) z referencjami lub generate_image (bez referencji, z samego opisu)."""
    if ref_urls:
        if not 1 <= len(ref_urls) <= 6 or not all(isinstance(u, str) and u.startswith('https://') for u in ref_urls):
            raise sogni.ProviderError('Referencje muszą być adresami HTTPS (1–6).', 400)
        step = {'id': step_id, 'toolName': 'edit_image', 'arguments': {'prompt': prompt, 'model': FLUX, 'referenceImageIndices': [-i for i in range(1, len(ref_urls) + 1)], 'width': size[0], 'height': size[1]}}
        model = FLUX
    else:
        step = {'id': step_id, 'toolName': 'generate_image', 'arguments': {'prompt': prompt, 'model': sogni.IMAGE_MODEL, 'width': size[0], 'height': size[1]}}
        model = sogni.IMAGE_MODEL
    body = {'input': {'title': f'Referencje {step_id}'[:120], 'steps': [step]}, 'app_source': 'nasz-dzien-film-studio-v87', 'token_type': 'auto', 'billing_mode': 'subscription', 'confirm_cost': bool(confirm)}
    if ref_urls:
        body['media_references'] = [{'kind': 'image', 'url': u} for u in ref_urls]
    if max_units is not None:
        body['max_estimated_capacity_units'] = float(max_units)
    sogni.subscription_guard(body, None)
    if model not in (FLUX, sogni.IMAGE_MODEL):
        raise sogni.ProviderError('Model spoza listy.', 403)
    return body


def capacity_total(est):
    """Liczba jednostek z odpowiedzi wyceny (liczba albo słownik z sumą)."""
    if isinstance(est, (int, float)) and not isinstance(est, bool):
        return float(est)
    if isinstance(est, dict):
        for k in ('totalWeightedUnits', 'total', 'totalCapacityUnits', 'units', 'estimatedCapacity'):
            v = est.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return float(v)
    raise sogni.ProviderError('Nie udało się odczytać wyceny — nie startuję bez znanej wyceny.', 502)


def _quote(body):
    sogni.assert_active_subscription()
    try:
        sogni.request('POST', '/v1/creative-agent/workflows', body, timeout=30)
    except sogni.ProviderError as e:
        if e.status == 400 and e.details.get('confirmationRequired') and e.details.get('estimatedCapacity') is not None:
            return capacity_total(e.details['estimatedCapacity'])
        raise
    return 0.0


def _wf(res):
    """Workflow z odpowiedzi API; odpowiedź bywa opakowana dokumentem (`_doc`)."""
    wf = (res.get('data') or {}).get('workflow') or {}
    return wf.get('_doc') or wf


def _poll(wf_id, timeout=1800):
    t0 = time.time()
    while time.time() - t0 < timeout:
        _, res = sogni.request('GET', '/v1/creative-agent/workflows/' + wf_id, timeout=30)
        wf = _wf(res)
        if wf.get('status') in TERMINAL:
            return wf
        time.sleep(6)
    raise TimeoutError(wf_id)


def _download(url, dest):
    if not url.startswith('https://'):
        raise ValueError('adres wyniku nie jest HTTPS')
    req = urllib.request.Request(url, headers={'User-Agent': 'NaszDzienFilmStudio/8.7'})
    with urllib.request.urlopen(req, timeout=240) as r:
        data = r.read(40_000_000)
    Path(dest).write_bytes(data)


def _refs_for(meta, view_id, upload=_upload):
    d = _dir(meta['id']); paths = []
    if view_id != ANCHOR[meta['kind']] and meta['anchor']:
        paths.append(d / meta['anchor'])
    for s in meta['sources']:
        paths.append(d / 'source' / s['file'])
    return [upload(p.read_bytes(), _mime(p), i) for i, p in enumerate(paths[:6], start=1)]


def generate(eid, view_ids, cands=1, max_units_total=120.0, upload=_upload):
    """Generuje podane widoki (po `cands` kandydatów). Zwraca listę nazw nowych plików."""
    meta = _load(eid); vmap = {x[0]: x for x in views_for(meta['kind'])}; made = []
    if any(v not in vmap for v in view_ids):
        raise ValueError('Nieznany widok')
    if any(v != ANCHOR[meta['kind']] for v in view_ids) and not meta['anchor']:
        raise HaltError('Najpierw zatwierdź kotwicę (widok główny) — reszta zestawu opiera się na niej')
    before = usage_snapshot()
    for vid in view_ids:
        for c in range(cands):
            gate()
            key = f'{vid}_{chr(97 + sum(1 for k in meta["images"] if k.startswith(vid + "_")))}'
            size = SIZES[meta['kind']][vmap[vid][3]]
            body = build_body(key, view_prompt(meta, vid), _refs_for(meta, vid, upload), size)
            tot = _quote(body)
            if meta['units'] + tot > max_units_total:
                raise HaltError('bezpiecznik sumy jednostek')
            meta['units'] += tot
            body['confirm_cost'] = True; body['max_estimated_capacity_units'] = max(2.0, math.ceil(tot * 1.4))
            sogni.subscription_guard(body, None)
            _, res = sogni.request('POST', '/v1/creative-agent/workflows', body, extra_headers={'Idempotency-Key': str(uuid.uuid4())}, timeout=40)
            wf = _wf(res)
            wid = wf.get('workflowId')
            if not wid:
                raise sogni.ProviderError('Brak identyfikatora workflow')
            meta['log'].append(f'{now()} start {key} {wid} (wycena {tot:g})'); _save(meta)
            r = _poll(wid)
            step = next((s for s in r.get('steps', []) if s.get('id') == key), {})
            url = next((a.get('url') for a in step.get('artifacts') or [] if isinstance(a.get('url'), str)), None)
            meta['ledger'].append({'at': now(), 'view': key, 'workflow': wid, 'billingMode': r.get('billingMode'), 'status': r.get('status'), 'estimate': tot})
            if url:
                fn = f'{key}.png'; _download(url, _dir(eid) / fn)
                meta['images'][key] = {'file': fn, 'view': vid, 'sha256': hashlib.sha256((_dir(eid) / fn).read_bytes()).hexdigest(), 'created': now()}
                made.append(fn)
            else:
                meta['log'].append(f'{now()} BRAK wyniku {key} ({r.get("status")})')
            _save(meta)
    assert_free(before, usage_snapshot(), 'kreator referencji')
    return made


def approve(eid, image_key, viewed_confirmed=False):
    """Zatwierdza obraz jako wzorzec widoku. Zatwierdzenie wymaga jawnego potwierdzenia człowieka, że obraz obejrzał."""
    if viewed_confirmed is not True:
        raise PermissionError('Zatwierdzenie wymaga potwierdzenia, że obraz został obejrzany')
    meta = _load(eid)
    if image_key not in meta['images']:
        raise KeyError('Nie ma takiego obrazu')
    f = _dir(eid) / meta['images'][image_key]['file']
    if hashlib.sha256(f.read_bytes()).hexdigest() != meta['images'][image_key]['sha256']:
        raise ValueError('Plik obrazu został zmieniony po wygenerowaniu')
    vid = meta['images'][image_key]['view']
    meta['approved'][vid] = {'image': image_key, 'file': f.name, 'sha256': meta['images'][image_key]['sha256'], 'at': now()}
    if vid == ANCHOR[meta['kind']]:
        meta['anchor'] = f.name
    _save(meta)
    return meta


def manifest(eid):
    """Zapisuje manifest.json z zatwierdzonymi widokami i sumami SHA-256 (do użycia jako referencje ujęć)."""
    meta = _load(eid); missing = [v[0] for v in views_for(meta['kind']) if v[0] not in meta['approved']]
    man = {'id': meta['id'], 'kind': meta['kind'], 'name': meta['name'], 'style': meta['style'], 'description': meta['description'],
           'approved': meta['approved'], 'missing_views': missing, 'complete': not missing, 'generated': now(),
           'note': 'SHA-256 to kontrola pliku, nie gwarancja tożsamości twarzy/miejsca w filmie; zgodność ocenia człowiek.'}
    (_dir(eid) / 'manifest.json').write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding='utf8')
    return man


def contact_sheet(eid, out=None):
    from PIL import Image, ImageDraw
    meta = _load(eid); keys = list(meta['images'])
    if not keys:
        return None
    w, h = 270, 360; cols = 6; rows = (len(keys) + cols - 1) // cols
    sh = Image.new('RGB', (cols * w, rows * h), 'white')
    for i, k in enumerate(keys):
        im = Image.open(_dir(eid) / meta['images'][k]['file']).convert('RGB'); im.thumbnail((w, h)); d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 110, 16), fill='black'); d.text((3, 2), k + (' ✓' if any(a['image'] == k for a in meta['approved'].values()) else ''), fill='white')
        sh.paste(im, ((i % cols) * w, (i // cols) * h))
    out = Path(out or _dir(eid) / 'plansza.png'); sh.save(out); return out


def list_all():
    ROOT.mkdir(parents=True, exist_ok=True)
    rows = []
    for d in sorted(ROOT.iterdir()):
        f = d / 'meta.json'
        if f.exists():
            m = json.loads(f.read_text(encoding='utf8'))
            rows.append({k: m[k] for k in ('id', 'kind', 'name', 'style', 'anchor')} | {'images': len(m['images']), 'approved': len(m['approved']), 'views': len(views_for(m['kind']))})
    return rows


def public_view(meta):
    return {k: meta[k] for k in ('id', 'kind', 'name', 'description', 'style', 'anchor', 'units')} | {
        'views': [{'id': v[0], 'label': v[1], 'approved': v[0] in meta['approved']} for v in views_for(meta['kind'])],
        'images': {k: {'view': i['view'], 'sha256': i['sha256']} for k, i in meta['images'].items()}, 'sources': len(meta['sources'])}

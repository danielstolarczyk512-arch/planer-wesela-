"""V4 editorial director: human-action-first shot planning. No network or cost.

Offline story is deliberately a *template* for the real product feature, not an AI script.
"""
from __future__ import annotations

import copy
import uuid

from studio.engine import now

V4_SHOT_PLAN = [
    # duration weights, role, action, lens, dialogue, mode, character(s)
    (2.0, 'hook', 'Zbliżenie dłoni przesuwającej dwie winietki obok siebie; ręka drugiej osoby łagodnie ją zatrzymuje.', '85mm macro, gentle handheld, tiny rack focus', '', 't2v', ['ONA', 'ON']),
    (2.5, 'reaction', 'Maja unosi brwi, spogląda na Kubę, z trudem powstrzymuje śmiech; oboje patrzą na winietki, nie na kamerę.', '50mm close two-shot, eye line continuity', 'Nie. Tylko nie obok siebie.', 't2v', ['ONA', 'ON']),
    (2.0, 'conflict', 'Ciocia Marianna uśmiecha się przesadnie uprzejmie do kogoś poza kadrem i poprawia serwetkę.', '70mm medium close-up, camera locked', '', 't2v', ['CIOCIA']),
    (1.8, 'reaction', 'Wujek Boguś na moment zastyga z filiżanką, po czym odwraca wzrok.', '70mm close-up, subtle natural breathing', '', 't2v', ['WUJEK']),
    (2.3, 'action', 'Kuba wskazuje plan stołów na stole; Maja przysuwa laptop. Krótki, autentyczny ruch dłoni.', '35mm over-shoulder, small dolly', 'Dobra. Zróbmy to inaczej.', 't2v', ['ONA', 'ON']),
    (4.0, 'product_before_after', 'AUTENTYCZNY SCREEN CAPTURE: plan stołów Nasz Dzień, przybliżenie na jednego gościa, przesunięcie do innego stołu, widoczny wynik PRZED i PO. Bez fikcyjnego UI.', 'Real screen recording, deliberate crop, readable labels', '', 'ui', []),
    (2.8, 'relief', 'Kuba patrzy na Maję z niedowierzaniem, po chwili lekko się uśmiecha. Maja odpowiada krótkim spojrzeniem.', '50mm medium two-shot, natural imperfect timing', 'I już?', 't2v', ['ONA', 'ON']),
    (3.5, 'payoff', 'Ciocia Marianna przy innym stole rozmawia radośnie z gośćmi. Wujek Boguś w tle dyskretnie podnosi filiżankę na znak pokoju.', '35mm warm wide shot, one slow handheld move', '', 't2v', ['CIOCIA', 'WUJEK']),
    (3.0, 'human_close', 'Maja i Kuba wymieniają spojrzenia i spontanicznie, krótko się śmieją — bez patrzenia w kamerę.', '50mm intimate two-shot, shallow but realistic depth', '', 't2v', ['ONA', 'ON']),
    (4.1, 'cta', 'Oryginalne logo Nasz Dzień i hasło „Mniej stresu. Więcej Was.” zmontowane lokalnie na prawdziwym ujęciu lub własnej planszy.', 'Static branded end card created in editor, safe margins', '', 'overlay', []),
]
PEOPLE = [
 {'id':'ONA','name':'Maja','look':'fictional Polish woman, 28, chestnut shoulder-length hair, brown eyes, subtle natural makeup, ivory blazer, small gold hoop earrings','personality':'spokojna, dowcipna; subtelne reakcje','avoid':'no glamour filter, no overly broad smile, no frontal advertising poses'},
 {'id':'ON','name':'Kuba','look':'fictional Polish man, 29, short dark brown hair, light stubble, dark charcoal shirt, navy trousers','personality':'ciepły, nieco roztargniony; łagodny humor','avoid':'no overacting, no exaggerated surprise, no speaking to camera'},
 {'id':'CIOCIA','name':'Marianna','look':'fictional Polish woman, 63, short silver hair, burgundy silk jacket, discreet pearl earrings','personality':'dumna, dowcipna, uprzejma aż do przesady','avoid':'no changing age or wardrobe'},
 {'id':'WUJEK','name':'Bogdan „Boguś”','look':'fictional stylized Polish man, 52, long narrow face, thin dark moustache, swept brown hair with grey temples, plum suit, open pale pink shirt, gold chain','personality':'powściągliwy, lekko ironiczny','avoid':'same long narrow face, thin dark moustache and plum suit; no round Daniel jaw'},
]
SCENE = ('Same lived-in Polish wedding venue, ivory linen, subtle flowers, warm practical light, '
         'believable skin texture and naturally imperfect placement of tableware.')
NATURAL = ('Observational cinematic live action, modest facial micro-expressions, imperfect natural timing, '
           'one physically plausible action. Stable identity, garments and prop placement. '
           'NO eye contact with camera, NO exaggerated acting, NO uncanny smiles, NO fake screens, '
           'NO subtitles, NO generated logos, NO written text.')


def apply_director_v4(project: dict) -> dict:
    """Rebuild shot plan, preserving script history; invalidates old footage by generation ID."""
    if not project.get('script') or project.get('storyboard_stale'):
        raise ValueError('Najpierw przygotuj aktualny scenariusz. Nie można reżyserować nieaktualnego storyboardu.')
    if project.get('feature','').lower() not in ('plan stołów','plan stolow'):
        raise ValueError('Ten gotowy szablon reżyserski v4 dotyczy planu stołów. Inne funkcje wymagają planu AI i ręcznej akceptacji.')
    target=float(project.get('duration',30))
    if not 20 <= target <= 60:
        raise ValueError('Szablon v4 obsługuje reklamy 20–60 s; zalecamy 30 s.')
    original=copy.deepcopy(project.get('shots',[]))
    project.setdefault('script_versions',[]).append({'script':project['script'],'shots':original,'created':now(),'reason':'director_v4_upgrade'})
    total=sum(s[0] for s in V4_SHOT_PLAN)
    durations=[round(x[0]*target/total,3) for x in V4_SHOT_PLAN]
    durations[-1]=round(target-sum(durations[:-1]),3)
    cast=copy.deepcopy(PEOPLE)
    shots=[];t=0.0
    for i,(base,role,action,camera,dialogue,mode,people) in enumerate(V4_SHOT_PLAN):
        people_desc='; '.join(p['look'] for p in cast if p['id'] in people)
        prompt=(f'{SCENE} {NATURAL} Character continuity: {people_desc}. Scene action: {action}. Camera: {camera}.') if mode=='t2v' else action
        d=durations[i]
        shot={'id':f'S{i+1:02}', 'index':i+1, 'start':round(t,3),'duration':d,
              'in_point':0.0,'out_point':round(d,3),'shot_role':role,'function':role,
              'beat':action,'dialogue':dialogue,'dialogue_id':f'D{i+1:02}' if dialogue else None,
              'camera':camera,'prompt':prompt,'mode':mode,
              'characters':people,'continuity_id':'SALA_A_2026','location':'Sala weselna, światło ciepłe, wieczór',
              'wardrobe_locked':True,'approved':False,'qc_approved':False,
              'generation_seconds':5.2 if mode=='t2v' else 0,
              'video_model':'minimax-h3-fasth3-t2v-turbo' if mode=='t2v' else None,
              'media_url':None,'workflow_id':None,'reference_image_urls':[],
              'edit_version':str(uuid.uuid4())}
        shots.append(shot);t+=d
    project.update(shots=shots,cast=cast,storyboard_stale=False,shot_generation=str(uuid.uuid4()),
       v4_quality_mode=True, v4_approved_screen=False, status='director_v4',updated=now(),
       v4_story_review={'method':'offline_template','observations':[
           'Hook pokazany działaniem w pierwszych 2 s','Naturalna reakcja bohaterów bez patrzenia w kamerę',
           'Autentyczny produkt z konkretnym gestem przesunięcia gościa','Wizualna puenta przed końcowym CTA',
           'Ujęcia zgrupowane w jednym spójnym wnętrzu']})
    project['script'] = (f'NASZ DZIEŃ — OPERACJA: PLAN STOŁÓW | DIRECTOR V4 | {target:g}s\n'
       'To przykładowy scenariusz reżyserski offline, nie wynik LLM.\n\n' + '\n\n'.join(
       f'{s["start"]:.1f}–{s["start"]+s["duration"]:.1f} s · {s["id"]} · {s["shot_role"]}\n'
       f'{s["beat"]}\n{("Dialog: "+s["dialogue"]) if s["dialogue"] else "Bez dialogu"}' for s in shots))
    return project

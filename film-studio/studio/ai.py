"""Multi-pass LLM pipeline: distinct ideation, two blind reviews, screenplay."""
import json
import re
import uuid

from . import engine, sogni

SYSTEM='''Jesteś profesjonalnym scenarzystą polskich reklam krótkich filmowych dla fikcyjnych bohaterów, brand Nasz Dzień (planer wesela). Nie opisuj funkcji niepotwierdzonych, nie cytuj filmów, nie kopiuj istniejących postaci. Specjalizujesz się w inteligentnej komedii i storytellingu: konflikt, stawka, eskalacja, puenta i konkretna korzyść dla odbiorcy. Odpowiadaj TYLKO poprawnym JSON bez Markdown, bez ukrytego rozumowania. W scenach produktu używaj REALNEGO nagrania UI, nigdy generowanego fałszywego UI. Zwracaj rzeczywiste polskie dialogi, a prompty dla generatora wideo po angielsku.'''

def parse_json(raw):
    raw=raw.strip()
    if raw.startswith('```'):
        raw=re.sub(r'^```(?:json)?\s*','',raw)
        raw=re.sub(r'\s*```$','',raw)
    try:return json.loads(raw)
    except json.JSONDecodeError as e:
        # Some providers prepend short commentary; allow only the first complete object.
        try:
            decoder=json.JSONDecoder(); begin=raw.index('{')
            obj,_=decoder.raw_decode(raw[begin:]);return obj
        except (ValueError,json.JSONDecodeError):raise ValueError('Model zwrócił nieprawidłowy JSON — ponów etap.') from e

def generate_concepts(p):
    brief={k:p[k] for k in ('idea','objective','tone','audience','duration','format','feature')}
    brief['avoid_previously_used']=[x.get('title','') for x in p.get('creative_memory',[])][-30:]
    brief['must_be_factual']=True
    text,_=sogni.chat(SYSTEM,'''STAGE 1 / IDEATION. Wymyśl 10 radykalnie różnych, ale wykonalnych 15–60 s koncepcji reklamy. Przynajmniej 4 pomysły nie mogą opierać się na tym samym stereotypie chaosu organizacyjnego. Przynajmniej 2 powinny mieć nieoczywistą puentę. Skonstruuj jasną stawkę, działanie i przyczynowo-skutkowy twist. Nie powtarzaj wcześniej użytych tytułów. Różnicuj dramaturgię, kąt narracji, napięcie, żart i twist. Brak generycznych zachodów słońca i banałów. Nie zmuszaj bohaterów do czytania napisów wygenerowanych przez video AI. Schemat dokładnie {"concepts":[{"id":"C01","title":"...","genre":"...","hook":"...","conflict":"...","twist":"...","feature":"...","synopsis":"..."},...]} — 10 pozycji. BRIEF: '''+json.dumps(brief,ensure_ascii=False),max_tokens=3900)
    data=parse_json(text); concepts=data.get('concepts')
    if not isinstance(concepts,list) or len(concepts)<6:raise ValueError('Model musi dostarczyć co najmniej sześć koncepcji.')
    clean=[]
    for i,c in enumerate(concepts[:10]):
        if not isinstance(c,dict):raise ValueError('Nieprawidłowa koncepcja AI')
        fields=['title','genre','hook','conflict','twist','feature','synopsis']
        if not all(isinstance(c.get(f),str) and len(c[f].strip())>=4 for f in fields):raise ValueError('Koncepcja AI jest niekompletna')
        clean.append({**{k:c[k].strip()[:1300] for k in fields},'id':f'C{i+1:02}','fit':'AI'})
    return clean

def assess(concepts,reviewer):
    prompt=('STAGE 2 / BLIND EVALUATION. Jesteś '+reviewer+'. Nie oceniając uprzejmości, oceń KAŻDY pomysł według rubryki: '+str(engine.WEIGHTS)+'''. Wypisz osobno 7 liczb całkowitych w granicach maksimów dla hook, story, originality, product, marketing, feasibility, silent_readability. Jeśli fałszywa obietnica produktu lub brak faktycznej korzyści, wystaw veto=true i uzasadnij. Zwróć TYLKO {"reviews":[{"concept_id":"C01","scores":{"hook":0,"story":0,"originality":0,"product":0,"marketing":0,"feasibility":0,"silent_readability":0},"strength":"...","weakness":"...","veto":false}, ...]}. Koncepcje: '''+json.dumps(concepts,ensure_ascii=False))
    text,_=sogni.chat(SYSTEM,prompt,max_tokens=4200)
    rows=parse_json(text).get('reviews',[])
    byid={c['id'] for c in concepts}
    if not isinstance(rows,list) or set(r.get('concept_id') for r in rows if isinstance(r,dict))!=byid:raise ValueError('Recenzja AI nie obejmuje wszystkich koncepcji.')
    out={}
    for r in rows:
        scores={}
        for name,maximum in engine.WEIGHTS.items():
            x=r.get('scores',{}).get(name)
            if type(x) not in (int,float) or not 0<=x<=maximum:raise ValueError('Recenzent zwrócił wynik spoza skali: '+name)
            scores[name]=int(x)
        out[r['concept_id']]={'reviewer':reviewer,'scores':scores,'total':sum(scores.values()),'strength':str(r.get('strength',''))[:600], 'weakness':str(r.get('weakness',''))[:600],'veto':bool(r.get('veto',False)),'kind':'sogni_ai'}
    return out

def create_script(p,concept,direction=None):
    payload={k:p[k] for k in ('title','idea','duration','format','tone','feature','objective')}
    prompt='''STAGE 3 / DIRECTOR + SCRIPT DOCTOR. Zaprojektuj gotową reklamę wg zwycięskiej koncepcji. Przemyśl fizycznie wykonalną akcję i montaż. Film musi mieć 8–12 ujęć; od 1 do 3 sekund dla hooka, nie dopisuj czasu poza wskazanym duration; czasy sumują się do podanej wartości; osobne ujęcie prawdziwego interfejsu (mode="ui"), osobna plansza końcowa (mode="overlay"); reszta mode="t2v". Dialogi naturalne krótkie. Pokaż konflikt zamiast go tłumaczyć. Wymagaj wizualnej puenty przed CTA, a na początku co najmniej jednego działania i reakcji bez słów. Zachowaj jedną lokację, garderobę i rekwizyty. Telefon z białym ekranem jest niedozwolony. Brak frontalnych monologów i przerysowanej mimiki. Zróżnicuj plany makro / zbliżenie / średni / szeroki. Wideo-generowane ujęcia mają single physical action i kamera dynamiczna tylko gdy uzasadniona. Prompty bez liter, napisów i marek, po angielsku. "generation_seconds" 5.2 do 15.0 dla t2v, nawet jeśli ujęcie w montażu krótsze. Modele t2v: minimax-h3-fasth3-t2v-turbo. Dokładny schemat JSON {"script":"pełny scenariusz po polsku", "cast":[{"id":"ONA","name":"Maja","look":"detailed English appearance","personality":"...","avoid":"..."}, {"id":"ON","name":"Kuba","look":"...","personality":"...","avoid":"..."}],"shots":[{"id":"S01","start":0,"duration":3,"beat":"...","function":"Hook","dialogue":"...","camera":"...","prompt":"detailed English prompt","mode":"t2v","characters":["ONA","ON"],"generation_seconds":5.2,"video_model":"minimax-h3-fasth3-t2v-turbo"},...]}. Nie pomijaj żadnych pól. Oto koncept: '''+json.dumps(concept,ensure_ascii=False)+' BRIEF: '+json.dumps(payload,ensure_ascii=False)+(' WYMAGANE POPRAWKI KRYTYKA: '+json.dumps(direction,ensure_ascii=False) if direction else '')
    raw,_=sogni.chat(SYSTEM,prompt,max_tokens=6500)
    body=parse_json(raw)
    if not isinstance(body.get('script'),str) or len(body['script'])<100:raise ValueError('Scenariusz AI jest niekompletny.')
    if not isinstance(body.get('shots'),list) or not 8<=len(body['shots'])<=12:raise ValueError('Scenariusz AI wymaga 8–12 ujęć.')
    shots=[]; total=0
    for i,s in enumerate(body['shots']):
        if not isinstance(s,dict):raise ValueError('Błędne ujęcie AI')
        mode=s.get('mode','t2v')
        if mode not in ('t2v','ui','overlay'):raise ValueError('Nieobsługiwany typ ujęcia.')
        d=float(s.get('duration',0))
        if d<=0 or d>20:raise ValueError('Błędny czas ujęcia.')
        gen=float(s.get('generation_seconds',5.2)) if mode=='t2v' else 0
        if mode=='t2v' and not 5.17<=gen<=15.08:raise ValueError('Zły czas renderowania H3')
        shot={'id':f'S{i+1:02}','index':i+1,'start':round(total,2),'duration':d,'generation_seconds':gen,'beat':str(s.get('beat',''))[:1000], 'function':str(s.get('function',''))[:100], 'dialogue':str(s.get('dialogue',''))[:1000], 'camera':str(s.get('camera',''))[:1000], 'prompt':str(s.get('prompt',''))[:5000], 'mode':mode, 'video_model':'minimax-h3-fasth3-t2v-turbo' if mode=='t2v' else None, 'media_url':None,'workflow_id':None,'reference_image_urls':[], 'in_point':0, 'shot_role':str(s.get('function','')).lower(), 'characters':[str(x)[:60] for x in s.get('characters', ['ONA','ON'])[:4]] if isinstance(s.get('characters', ['ONA','ON']), list) else ['ONA','ON'], 'continuity_id':'SALA_A','qc_approved':False,'edit_version':str(uuid.uuid4())}
        shots.append(shot);total+=d
    if abs(total-p['duration'])>0.6:raise ValueError(f'Suma ujęć wynosi {total}s zamiast {p["duration"]}s. Zleć poprawkę AI.')
    if not any(x['mode']=='ui' for x in shots) or not any(x['mode']=='overlay' for x in shots):raise ValueError('Brakuje autentycznego UI lub planszy CTA')
    cast=body.get('cast')
    if not isinstance(cast,list) or len(cast)<2:raise ValueError('Brakuje biblii postaci')
    from .character_bible_v83 import canonical_cast
    stable=canonical_cast()
    extras=[c for c in cast if c.get('id') not in ('ONA','ON') and isinstance(c,dict)]
    return body['script'], shots,stable+extras[:3]

def develop_live(p,save):
    p['concepts']=generate_concepts(p)
    p.update(status='ideas_generated',mode='sogni_ai',updated=engine.now());save(p)
    a=assess(p['concepts'],'Dramaturg — bezlitosny krytyk narracji')
    b=assess(p['concepts'],'Strateg performance marketingu — sceptyk')
    c_review=assess(p['concepts'],'Reżyser wideo AI: rygor wykonalności scen i unikania sztucznego UI')
    p['reviews']=[{'concept_id':c['id'],'reviews':[a[c['id']],b[c['id']],c_review[c['id']]], 'average':round((a[c['id']]['total']+b[c['id']]['total']+c_review[c['id']]['total'])/3,1)} for c in p['concepts']]
    best=[x for x in p['reviews'] if not any(r['veto'] for r in x['reviews'])]
    if not best:raise ValueError('Wszystkie koncepcje otrzymały veto. Zmień brief.')
    p['selected_concept_id']=max(best,key=lambda x:x['average'])['concept_id']
    used=next(c for c in p['concepts'] if c['id']==p['selected_concept_id'])
    p.setdefault('creative_memory',[]).append({'title':used['title'],'at':engine.now()})
    p.update(status='ideas_reviewed',updated=engine.now());save(p)
    c=next(c for c in p['concepts'] if c['id']==p['selected_concept_id'])
    if p.get('duration',30)>60:
        from .longform_v83 import build
        build(p,c)
        p['longform_planning']='AI evaluates concepts, deterministic 46-shot production plan; dialogue to be reviewed manually'
    else:
        p['script'],p['shots'],p['cast']=create_script(p,c)
    p.update(status='storyboard', storyboard_stale=False, v4_quality_mode=True, updated=engine.now(),shot_generation=str(uuid.uuid4()));save(p)
    return p


def script_doctor(p,save):
    # Requires explicit paid consent at HTTP boundary.
    if p.get('revisions',0)>=3:raise ValueError('Limit trzech przepisań AI został osiągnięty.')
    if not p.get('script') or not p.get('shots'):raise ValueError('Brak gotowego scenariusza.')
    concept=next((c for c in p.get('concepts',[]) if c['id']==p.get('selected_concept_id')),None)
    if not concept:raise ValueError('Brak wybranej koncepcji.')
    if p.get('duration',30)>60:
        # Local-only: never call external text AI just to reject the format.
        from .story_director_v84 import review_story
        p['script_review']=review_story(p)
        p['updated']=engine.now()
        save(p)
        return p
    doctor_prompt = ('STAGE 4 / INDEPENDENT SCRIPT DOCTOR. Nie przyjmuj ocen koncepcji jako dowodu jakości scenariusza. '
        'Oceń osobno: hook, dramaturgię, wiarygodność, naturalne dialogi, wykonalność w AI wideo, produkt, puentę. '
        'Wskaż 3 najważniejsze poprawki i sposób ich realizacji. Zwróć TYLKO JSON: '
        '{"verdict":"...","critical_issues":["...","...","..."],"revision_directions":["...","...","..."],"score_before":0}. '
        'SCORE 0..100. SCENARIUSZ: '+p['script'][:18000]+' SHOTS: '+json.dumps(p['shots'],ensure_ascii=False)[:12000])
    raw,_=sogni.chat(SYSTEM,doctor_prompt,max_tokens=1900)
    critique=parse_json(raw)
    if not isinstance(critique.get('critical_issues'),list) or not isinstance(critique.get('revision_directions'),list) or len(critique['revision_directions'])<2:
        raise ValueError('Krytyk scenariusza zwrócił niekompletny raport.')
    # Save both critique and original draft before paying for an additional call.
    p.setdefault('script_versions',[]).append({'script':p['script'],'shots':p['shots'],'created':engine.now(),'reason':'before_script_doctor'})
    p['script_review']=critique
    p['updated']=engine.now();save(p)
    if p.get('duration',30)>60:
        raise ValueError('Script Doctor dla 180 s wymaga aktualizacji; nie zastępuj zatwierdzonego storyboardu planem krótkiej reklamy.')
    script,shots,cast=create_script(p,concept,direction=critique)
    p.update(script=script,shots=shots,cast=cast,revisions=p.get('revisions',0)+1,status='storyboard',mode='sogni_ai',storyboard_stale=False,v4_quality_mode=True,updated=engine.now(),shot_generation=str(uuid.uuid4()))
    save(p)
    return p


def sync_storyboard_from_script(p, save):
    """Rebuild shot list from user-edited script, never silently re-use old render IDs."""
    if not p.get('script','').strip():
        raise ValueError('Najpierw zapisz scenariusz.')
    if not p.get('storyboard_stale'):
        raise ValueError('Storyboard jest aktualny.')
    concept=next((c for c in p.get('concepts',[]) if c['id']==p.get('selected_concept_id')), None)
    if not concept:
        raise ValueError('Nie znaleziono koncepcji projektu.')
    # Original script is binding creative brief. Never treat it as random inspiration.
    binding={'user_script_is_source_of_truth':p['script'][:24000],
             'must_keep': 'Zachowaj działania i dialogi zapisane w scenariuszu, bez dopisywania niepotwierdzonych funkcji.',
             'original_cast':p.get('cast',[])}
    script,shots,cast=create_script(p, concept, direction=binding)
    p.setdefault('script_versions',[]).append({'script':p['script'],'shots':p.get('shots',[]),
                                                'created':engine.now(),'reason':'before_synced_storyboard'})
    p.update(script=script,shots=shots,cast=cast,storyboard_stale=False,
             shot_generation=str(uuid.uuid4()),updated=engine.now(),status='storyboard',v4_quality_mode=True,
             revisions=p.get('revisions',0)+1)
    save(p)
    return p

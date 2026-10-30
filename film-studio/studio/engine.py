"""Concept generators, deterministic offline reviewers, cast and shot planner.
Offline mode is clearly labelled: this is template reasoning, NOT an LLM.
"""
import re
import uuid
from datetime import UTC, datetime

WEIGHTS={'hook':20,'story':15,'originality':15,'product':15,'marketing':10,'feasibility':15,'silent_readability':10}
ANGLES=[
    ('Operacja: Plan Stołów','Komedia szpiegowska','Jedna wizytówka potrafi wywołać kryzys dyplomatyczny.','Ciocia odkrywa, że siedzi obok dawnej rywalki.','Okazuje się, że największą bronią pary jest spokojne przesunięcie miejsca.', 'plan stołów'),
    ('Kontrola budżetu','Thriller finansowy','Dzwoni telefon. „Mamy mały problem z budżetem”.','Nagle pojawia się lista kolejnych niespodziewanych wydatków.','Na ekranie pojawia się przejrzysty budżet i ważne terminy płatności.', 'budżet'),
    ('Agentka RSVP','Komedia kryminalna','Ktoś wysłał wiadomość: „Przyjdziemy w pięcioro”.','Detektyw w sukni ślubnej rozpracowuje tajemnicze odpowiedzi gości.','Lista gości i RSVP pozwalają odzyskać kontrolę.', 'lista gości'),
    ('Wesele na 37 karteczkach','Mockument','Przyszły pan młody wypowiada słowa: „Wszystko mam zapisane”.','Kamera odsłania lodówkę pełną karteczek i zakreślaczy.','Jeden planer zastępuje improwizowany system.', 'harmonogram'),
    ('Powrót do przyszłości','Komedia science fiction','Para otrzymuje wiadomość od samych siebie z dnia wesela.','Przyszli nowożeńcy ostrzegają przed jednym szczegółem organizacyjnym.','Teraz mogą go wcześniej zaplanować.', 'harmonogram'),
    ('Sąd nad listą gości','Satyra sądowa','Sędzia uderza młotkiem: „Kto zaprosił kuzyna?”','Świadkowie przedstawiają sprzeczne wersje listy gości.','Planer porządkuje zaproszenia i odpowiedzi.', 'lista gości'),
    ('Misja: Ostatni piątek','Film akcji','Do wesela zostało 48 godzin. Wszystko nagle przyspiesza.','W rytmie kina akcji para odhacza zadania.','Harmonogram zamienia pośpiech w jasny plan.', 'harmonogram'),
    ('Jedna wiadomość za dużo','Komedia romantyczna','Narzeczeni otrzymują 17 pytań od rodziny w 30 sekund.','Każdy telefon dotyczy zupełnie innego szczegółu.','Wspólny plan pomaga odpowiadać spokojnie.', 'harmonogram'),
    ('Władca Exceli','Fantasy z humorem','Na stole pojawia się ogromna mapa weselnych krain.','Bohaterowie szukają utraconej tabeli budżetu.','Realistyczne przejście do prostego planowania.', 'budżet'),
    ('Przesłuchanie fotografa','Komedia proceduralna','Z pokoju przesłuchań dobiega: „A umowa?”','Para rozlicza własne notatki o usługodawcach.','Oferty i ustalenia trafiają w jedno uporządkowane miejsce.', 'usługodawcy'),
]
BEATS={
 'plan stołów':['Dwie bezimienne winietki zaczynają zbliżać się do siebie','Narzeczona wstrzymuje ruch dłoni i patrzy wprost w obiektyw','Przebitki na skonfliktowanych gości jak w thrillerze','Narzeczony wskazuje stos kartek z planem sali','Autentyczny widok planu stołów w Nasz Dzień','Para spokojnie rozmawia przy kawie; logo i hasło'],
 'budżet':['Na ekranie telefonu pojawia się kolejny koszt','Narzeczony z niedowierzaniem odkłada kalkulator','Wymykające się kartki z tabelkami; narastająca muzyka','Para spogląda na siebie, milknie telefon','Prawdziwy moduł budżetu i płatności Nasz Dzień','Szeroki kadr: para spokojnie planuje dalsze zadania'],
 'lista gości':['Koperta z nieoczekiwaną odpowiedzią przybywa do domu','Detektywistyczne zbliżenie na reakcję narzeczonej','Dynamiczne zdjęcia anonimowych kart odpowiedzi','Para układa stosy kopert i notatek','Prawdziwa lista gości i RSVP Nasz Dzień','Uśmiech porozumienia; logo i hasło'],
 'harmonogram':['Szybkie tykanie zegara; sterta ślubnych notatek','Bohater w popłochu przegląda kolejne karteczki','Montażowy chaos: telefon, koperty, terminarz','Narzeczona zatrzymuje serię powiadomień gestem dłoni','Prawdziwy harmonogram dnia Nasz Dzień','Wyciszenie muzyki, para odzyskuje spokój'],
 'usługodawcy':['Telefon z pytaniem o potwierdzenie terminu','Wymiana spojrzeń: „Która oferta jest aktualna?”','Przebitki na anonimowe foldery i notatki','Para porządkuje dokumenty przy stole','Prawdziwy interfejs ofert usługodawców Nasz Dzień','Ulga i uśmiech; hasło zachęcające do sprawdzenia aplikacji']
}

from .character_bible_v83 import canonical_cast

CAST=canonical_cast()

def now():return datetime.now(UTC).isoformat(timespec='seconds')

def new_project(form):
    text=lambda k,d: str(form.get(k,d)).strip()[:1000]
    return {'id':str(uuid.uuid4()), 'title':text('title','Nowa reklama')[:100], 'idea':text('idea','Chaos planowania wesela'),'objective':text('objective','Rejestracje'), 'duration':max(15,min(180,int(form.get('duration',30)))), 'project_type':'story_film' if int(form.get('duration',30))>60 else 'short_ad', 'format': text('format','9:16') if text('format','9:16') in ['9:16','16:9','1:1'] else '9:16', 'tone':text('tone','Komedia'), 'audience':text('audience','Narzeczeni 23–35'), 'feature':text('feature','plan stołów'), 'claims_approved':bool(form.get('claims_approved', False)), 'created':now(), 'updated':now(), 'status':'brief', 'concepts':[], 'reviews':[], 'selected_concept_id':None, 'script':'', 'cast':[], 'shots':[], 'mode':'demo', 'revisions':0,'storyboard_stale':False,'creative_memory':[]}

def make_concepts(project):
    result=[]
    for i,(title,genre,hook,conflict,twist,feature) in enumerate(ANGLES):
        preferred=project['feature'].casefold() in feature.casefold() or feature.casefold() in project['feature'].casefold()
        result.append({'id':f'C{i+1:02}','title':title,'genre':genre,'hook':hook,'conflict':conflict,'twist':twist,'feature':feature,'synopsis':f'{hook} {conflict} {twist}', 'fit': 'wysokie' if preferred else 'alternatywna funkcja'})
    return result

def review_concept(c,reviewer_index):
    num=int(re.sub(r'\D','',c['id']) or 1)
    # Independent deterministic rubric; deliberate score differences, no claim this is an LLM.
    bases=[{'hook':18,'story':13,'originality':13,'product':14,'marketing':9,'feasibility':12,'silent_readability':9},{'hook':17,'story':12,'originality':12,'product':14,'marketing':8,'feasibility':13,'silent_readability':9}]
    row=bases[reviewer_index].copy()
    row['originality']=max(7,row['originality']-(num%4))
    if num%3==0:row['feasibility']-=2
    if num%5==0:row['hook']-=2
    return {'reviewer':'Dramaturg' if reviewer_index==0 else 'Krytyk marketingowy','scores':row,'total':sum(row.values()),'strength':f'Wyrazisty pomysł: {c["hook"]}', 'weakness':'Sprawdź tempo eskalacji i czy nie ma zbyt długiej ekspozycji.' if reviewer_index==0 else 'Upewnij się, że korzyść produktu jest widoczna przed końcową planszą.', 'veto':False, 'kind':'rule_based_demo'}

def reviews(concepts):
    return [{'concept_id':c['id'],'reviews':[review_concept(c,0),review_concept(c,1)], 'average':round(sum(review_concept(c,i)['total'] for i in (0,1))/2,1)} for c in concepts]

def choose_best(project):
    ranked=sorted(project['reviews'],key=lambda r:r['average'],reverse=True)
    preferred=[r for r in ranked if next((c for c in project['concepts'] if c['id']==r['concept_id']),{}).get('feature')==project['feature']]
    return (preferred or ranked)[0]['concept_id']

def prepare_script(project,concept):
    duration=project['duration']
    weights=[.10,.16,.17,.17,.24,.16]
    durations=[round(duration*w,2) for w in weights]
    durations[-1]=round(duration-sum(durations[:-1]),2)
    beats=BEATS.get(concept.get('feature'),BEATS['harmonogram'])
    scripts=[
      f'HOOK: {concept["hook"]}',
      f'REAKCJA: {concept["conflict"]}',
      'ESKALACJA: drobny problem pokazany jak wielka filmowa katastrofa.',
      'PUNKT ZWROTNY: bohaterowie zatrzymują chaos; krótka emocjonalna pauza.',
      f'ROZWIĄZANIE: autentyczny ekran Nasz Dzień — {concept.get("feature","planowanie")}. Bez generowania fałszywego interfejsu.',
      'PUENTA: wraca spokój. Hasło: "Nasz Dzień. Mniej chaosu, więcej Was."'
    ]
    cams=['Macro, 85mm, slow push-in','Medium close-up, rack focus','Alternating close-ups, whip pan','Over-shoulder, controlled dolly','Real recorded screen capture, no AI depiction','Warm two-shot, gentle pullback']
    lines=['','„Nie. Tylko nie to.”','','„To przecież miało być proste...”','','„Nasz Dzień. Mniej chaosu, więcej Was.”']
    start=0
    shots=[]
    for i,beat in enumerate(beats):
        mode='ui' if i==4 else 'overlay' if i==5 else 't2v'
        action=('Cinematic realistic live action, original fictional Polish couple. '+beat+'. '+cams[i]+'. Stable natural faces, physically believable hands, simple single continuous action, no subtitles, no logos, no written text.')
        if i in [1,3]:action+=' Featured woman: '+CAST[0]['look']+'. Featured man: '+CAST[1]['look']+'.'
        shot={'id':f'S{i+1:02}','index':i+1,'start':round(start,2),'duration':durations[i], 'generation_seconds':5.2 if mode=='t2v' else 0,'beat':beat,'function':['Hook','Reakcja','Eskalacja','Zwrot','Produkt','CTA'][i], 'dialogue':lines[i],'camera':cams[i],'prompt':action if mode=='t2v' else ('Nagraj autentyczny interfejs aplikacji Nasz Dzień, pokaż rzeczywistą funkcję, zamazuj dane prywatne.' if mode=='ui' else 'Nałóż własne logo i hasło w montażu, bez generowania tekstu w modelu wideo.'),'mode':mode,'video_model':'minimax-h3-fasth3-t2v-turbo' if mode=='t2v' else None,'media_url':None,'workflow_id':None,'reference_image_urls':[]}
        start+=durations[i];shots.append(shot)
    script=f'''TYTUŁ: {concept['title']}\nGATUNEK: {concept['genre']} | FORMAT: {project['format']} | CZAS: {duration} s\n\nLOGLINE\n{concept['synopsis']}\n\nSCENARIUSZ\n'''+ '\n\n'.join(f'{s["start"]:05.1f}–{s["start"]+s["duration"]:05.1f} s | {s["function"]}\n{s["beat"]}\nDialog: {s["dialogue"] or "[bez dialogu]"}' for s in shots)+'\n\nUWAGA: film fikcyjny, lecz ekran aplikacji musi pochodzić z prawdziwego nagrania. Wszystkie roszczenia produktowe wymagają potwierdzenia.'
    return script,shots

def develop_demo(project):
    if project.get('duration',30)>60:
        from . import longform_v83
        project['concepts']=make_concepts(project)
        project['reviews']=reviews(project['concepts'])
        project['selected_concept_id']=choose_best(project)
        longform_v83.build(project)
        project.update(status='storyboard',mode='demo',updated=now(),shot_generation=str(uuid.uuid4()))
        return project
    project['concepts']=make_concepts(project)
    project['reviews']=reviews(project['concepts'])
    project['selected_concept_id']=choose_best(project)
    project['cast']=CAST
    selected=next(c for c in project['concepts'] if c['id']==project['selected_concept_id'])
    project['script'],project['shots']=prepare_script(project,selected)
    project.update(status='storyboard',mode='demo',storyboard_stale=False,updated=now(),shot_generation=str(uuid.uuid4()))
    return project

def select_demo(project,concept_id):
    selected=next((c for c in project['concepts'] if c['id']==concept_id),None)
    if not selected:raise ValueError('Nie znaleziono koncepcji.')
    project['selected_concept_id']=concept_id
    memory=project.setdefault('creative_memory',[])
    if selected['title'] not in [x.get('title') for x in memory]:memory.append({'title':selected['title'],'at':now()})
    if project.get('duration',30)>60:
        from . import longform_v83
        longform_v83.build(project,selected)
    else:
        project['script'],project['shots']=prepare_script(project,selected)
    project.update(status='storyboard',storyboard_stale=False,updated=now(),shot_generation=str(uuid.uuid4()))
    return project

def validate_story(project):
    issues=[]
    shots=project.get('shots',[])
    if not shots: issues.append('Brak listy ujęć')
    if not project.get('script'):issues.append('Brak scenariusza')
    if project.get('storyboard_stale'):issues.append('Storyboard nie odpowiada aktualnej wersji scenariusza — zsynchronizuj przed generowaniem')
    if shots and abs(sum(float(s['duration']) for s in shots)-project['duration'])>.2:issues.append('Suma czasów ujęć nie zgadza się z czasem filmu')
    if not any(s.get('mode')=='ui' for s in shots):issues.append('Brakuje ujęcia prawdziwego interfejsu produktu')
    if not project.get('claims_approved'):issues.append('Funkcje produktu nie zostały zatwierdzone — nie publikuj jako reklamy produktu')
    for s in shots:
        if s.get('mode')=='t2v' and (not s.get('prompt') or len(s['prompt'])<50):issues.append('Za krótki prompt dla '+s['id'])
    return issues

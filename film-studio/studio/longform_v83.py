"""Offline 180s narrative storyboard. Every shot is editable and renderable separately.
Creates no network requests and makes no claims about real finished media.
"""
from __future__ import annotations

import uuid

from .character_bible_v83 import canonical_cast

ACTS=[
 ('A1','HOOK / WSPÓLNE MARZENIE', [
  ('t2v','Kuchnia; żartobliwa pewność siebie narzeczonego','two-shot, quick push-in',['ONA','ON']),
  ('t2v','Zbliżenie twarzy mężczyzny; „Przecież to tylko wesele”','close-up, held 2 seconds',['ON']),
  ('t2v','Kobieta patrzy z niedowierzaniem; krótka pauza','reaction close-up',['ONA']),
  ('t2v','Lawina karteczek opada na kuchenny stół','insert detail, tilt down',['ONA','ON']),
  ('t2v','Spokojne wspomnienie zaręczyn: uśmiech i gest dłoni','warm medium shot',['ONA','ON']),
  ('t2v','Spacer; naturalna wymiana spojrzeń','tracking side profile',['ONA','ON']),
  ('t2v','Detal splecionych dłoni i pierścionka','insert macro',['ONA','ON']),
  ('t2v','Powrót do kuchni; niespodziewany dzwonek telefonu','whip cut, medium',['ONA','ON']),
  ('t2v','Krótka reakcja na lawinę powiadomień','close-up, restrained emotion',['ON']),
  ('ui','Wczesna zapowiedź aplikacji: realna lista zadań na telefonie','real screen recording',[])]),
 ('A2','CHAOS / KONFLIKT', [
  ('t2v','Przybywa nazwisk na liście gości','medium table action',['ONA','ON']),
  ('t2v','Mężczyzna liczy palcami i gubi rachubę','reaction close-up',['ON']),
  ('t2v','Kobieta przestawia winietki na stole','over shoulder',['ONA']),
  ('t2v','Niespodziewany telefon od krewnej','phone insert',['ONA']),
  ('t2v','Błyskawiczna wymiana spojrzeń','shot reverse shot',['ONA','ON']),
  ('t2v','Paragon zaczyna rozwijać się przez cały stół','wide reveal,['+' comedic action' +']',['ON']),
  ('t2v','Zbliżenie twarzy mężczyzny na widok ceny','tight face close-up',['ON']),
  ('t2v','Kobieta chwyta koniec długiego paragonu','medium close-up',['ONA']),
  ('t2v','Paragon ciągnie się po podłodze','low angle insert',['ON']),
  ('t2v','Oboje śmieją się z absurdalnej sytuacji','warm two-shot',['ONA','ON']),
  ('t2v','Stos dokumentów zasłania ekran laptopa','desk insert',['ONA','ON']),
  ('t2v','Kobieta z wahaniem patrzy na listę zadań','quiet close-up',['ONA']),
  ('ui','Prawdziwy interfejs budżetu; jedna zmiana kwoty','screen recording, fill frame',[]),
  ('t2v','Reakcja mężczyzny: zaskoczenie i ulga','reaction shot',['ON'])]),
 ('A3','ODKRYCIE / ROZWIĄZANIE', [
  ('t2v','Wieczór; krótka chwila szczerej rozmowy','two-shot, no orbit',['ONA','ON']),
  ('t2v','Zbliżenie kobiety wypowiadającej spokojną kwestię','static face close-up',['ONA']),
  ('t2v','Mężczyzna słucha, a potem kiwa głową','reverse close-up',['ON']),
  ('t2v','Para otwiera laptop z aplikacją Nasz Dzień','over shoulder',['ONA','ON']),
  ('ui','Nagranie prawdziwego panelu listy gości','real UI interaction',[]),
  ('t2v','Kobieta zauważa uporządkowaną listę','medium reaction',['ONA']),
  ('ui','Nagranie prawdziwego planu stołów','real UI drag and result',[]),
  ('t2v','Mężczyzna żartobliwie wznosi kubek','close-up',['ON']),
  ('ui','Nagranie prawdziwego harmonogramu','real UI task completion',[]),
  ('t2v','Oboje wracają do planowania z uśmiechem','medium two-shot',['ONA','ON']),
  ('t2v','Krótki humorystyczny kontrapunkt z paragonem','insert detail',['ONA','ON']),
  ('t2v','Ciepły moment czułości przy stole','gentle close-up',['ONA','ON'])]),
 ('A4','FINAŁ / CTA', [
  ('t2v','Para wychodzi na spacer przy zachodzie słońca','tracking wide',['ONA','ON']),
  ('t2v','Twarz kobiety w miękkim złotym świetle','close-up dialogue',['ONA']),
  ('t2v','Mężczyzna reaguje uśmiechem','reaction close-up',['ON']),
  ('t2v','Wspólny śmiech i przytulenie','medium two-shot',['ONA','ON']),
  ('t2v','Elegancka sala weselna odsłania się w szerokim planie','wide room reveal',[]),
  ('t2v','Krótki detal dekoracji stołu i złotych świateł','macro insert',[]),
  ('t2v','Para na sali patrzy na siebie','cinematic two-shot',['ONA','ON']),
  ('t2v','Powraca żart z początku — jedna karteczka','insert comedic punchline',['ON']),
  ('t2v','Ostatni uśmiech i ciepłe zbliżenie pary','slow face close-up',['ONA','ON']),
  ('overlay','Logo produktu i hasło „Mniej stresu. Więcej Was.”','designed graphic overlay',[])])
]

# Dialogues are editable *performances*, never an automatically approved voice.
# Deliberately short, filmable Polish lines; silence is intentional on reaction shots.
DIALOGUES={
 2:('ON','Przecież to tylko wesele. Co może być trudnego?','pewność siebie, lekka ironia'),
 3:('ONA','Naprawdę?','suchy humor, krótka pauza'),
 9:('ON','To wszystkie powiadomienia?','zaskoczenie, cichy śmiech'),
 11:('ONA','Dopisujemy jeszcze ciocię i jej rodzinę.','spokojna rzeczowość'),
 12:('ON','A oni wszyscy się znają?','niedowierzanie'),
 14:('ONA','Dzwoni kolejna ciocia.','rozbawione zmęczenie'),
 17:('ON','To chyba rachunek za cały pałac!','komediowe zaskoczenie'),
 22:('ONA','Nie wiem, od czego zacząć.','szczerość i delikatne zmęczenie'),
 24:('ON','Chyba mamy to pod kontrolą. Chyba.','ostrożny optymizm'),
 26:('ONA','Przecież to miał być nasz dzień.','ciepło, spokojna pauza'),
 27:('ON','Właśnie. Nie zgubmy go w tych kartkach.','łagodna empatia'),
 31:('ONA','O, lista wreszcie się zgadza!','radość i ulga'),
 33:('ON','Czyli ciocia może usiąść obok wujka?','żartobliwe pytanie'),
 36:('ONA','I znowu mamy dla siebie czas.','ciepło, ulga'),
 38:('ONA','Zobacz, ile już zrobiliśmy.','ciepło, ulga'),
 39:('ON','Podoba mi się taki plan.','czułość'),
 40:('ONA','Zwłaszcza że jesteś w nim ty.','spokojna czułość'),
 45:('ON','A tę ostatnią karteczkę zachowamy na pamiątkę.','naturalna puenta')
}
SCENE_LOCATIONS={'A1':'przytulna kuchnia i wspomnienie zaręczyn','A2':'kuchnia, stół, telefon i kartki',
 'A3':'wieczorna kuchnia i rzeczywista aplikacja na laptopie','A4':'park o zachodzie słońca i elegancka sala'}


def concept_variant(concept):
    c=concept or {}
    genre=str(c.get('genre','')).lower();feature=str(c.get('feature','')).lower()
    if 'szpieg' in genre or 'stoł' in feature:return 'seating'
    if 'budżet' in feature or 'finans' in genre:return 'budget'
    if 'goś' in feature or 'rsvp' in feature:return 'guests'
    if 'zadani' in feature or 'harmonogram' in feature:return 'tasks'
    return 'general'


def build(project,concept=None):
    duration=int(project.get('duration',180))
    if not 61<=duration<=180:
        raise ValueError('Długi format obsługuje od 61 do 180 sekund.')
    variant=concept_variant(concept)
    scene_focus={
      'seating':('dramatyczne winietki i rozmieszczenie gości','plan stołów'),
      'budget':('rachunki, koszty i paragon','budżet'),
      'guests':('zaproszenia, potwierdzenia gości','lista gości'),
      'tasks':('spiętrzone terminy i zadania','harmonogram'),
      'general':('logistyka wesela','planowanie')}
    conflict,feature=scene_focus[variant]
    entries=[]
    for act,title,actshots in ACTS:
        for mode,beat,camera,roles in actshots:
            if mode=='ui':
                beat='Prawdziwe nagranie aplikacji Nasz Dzień: '+feature+' — konkretna czynność i jej wynik'
            elif act=='A2' and mode=='t2v':
                beat=beat+'; motyw sytuacyjny: '+conflict
            entries.append((act,title,mode,beat,camera,roles))
    # Proportionally assign editorial target durations; actual generated H3 remains 5.2s.
    # Early first UI must arrive before 25% of runtime.
    count=len(entries)
    if count>99:raise ValueError('Maksymalnie 99 ujęć')
    weights=[0.77 if i < 10 else 1.04 for i in range(count)]
    # reserve 5 seconds for CTA and adjust last precisely
    weights[-1]=1.2
    unit=duration/sum(weights)
    durations=[round(w*unit,3) for w in weights]
    durations[-1]=round(duration-sum(durations[:-1]),3)
    start=0.0;shots=[];script=[]
    for i,((act,title,mode,beat,camera,roles),seconds) in enumerate(zip(entries,durations),1):
        prompt=('Premium Golden Storybook 3D stylized CGI short. '+beat+'. '+camera+
                '. Carefully preserve the exact approved character reference appearances, no captions, '+
                'no different face, no new wardrobe. One coherent action, natural acting, no split screen.')
        shot={'id':f'S{i:02d}','index':i,'act':act,'scene_title':title,'start':round(start,3),
              'duration':seconds,'generation_seconds':5.2 if mode=='t2v' else 0,
              'mode':mode,'function':'Produkt' if mode=='ui' else 'CTA' if mode=='overlay' else 'Fabuła',
              'beat':beat,'camera':camera,'prompt':prompt if mode=='t2v' else ('Wgraj rzeczywisty ekran aplikacji' if mode=='ui' else 'Własna plansza końcowa'),
              'video_model':'minimax-h3-fasth3-t2v-turbo' if mode=='t2v' else None,
              'dialogue':DIALOGUES.get(i,('','',''))[1] if mode=='t2v' else '',
              'speaker':DIALOGUES.get(i,('','',''))[0] if mode=='t2v' else '',
              'acting_direction':DIALOGUES.get(i,('','',''))[2] if mode=='t2v' else '',
              'voice_status':'needs_recording' if mode=='t2v' and i in DIALOGUES else 'not_applicable',
              'voice_approved':False,'lip_sync_approved':False,
              'scene_bible':{'location':SCENE_LOCATIONS[act],
                 'lighting':('ciepłe światło dzienne' if act in ('A1','A2') else 'miękkie światło wieczorne' if act=='A3' else 'złota godzina / sala weselna'),
                 'wardrobe':'zatwierdzona garderoba Golden Master, zmiana tylko po akceptacji',
                 'props':'utrzymuj przedmioty i ich położenie między sąsiednimi ujęciami',
                 'screen_direction':'nie przekraczaj osi rozmowy 180 stopni'},
              'continuity_status':'needs_visual_review' if mode=='t2v' else 'not_applicable',
              'characters':roles,'reference_image_urls':[],
              'qc_approved':False,'edit_version':str(uuid.uuid4()),'media_url':None,
              'workflow_id':None,'in_point':0,'shot_role':'narrative' if mode=='t2v' else mode}
        shots.append(shot)
        script.append(f'{start:06.2f}–{start+seconds:06.2f}s [{act}] {beat} | {camera}')
        start+=seconds
    project['cast']=canonical_cast()
    project['acts']=[{'id':a,'title':title,'shot_ids':[s['id'] for s in shots if s['act']==a]} for a,title,_ in ACTS]
    project['script']='NASZ DZIEŃ — FILM FABULARNO-REKLAMOWY\n'+(
        'Wariant: '+variant+' | '+str((concept or {}).get('title',''))+' | '+str((concept or {}).get('synopsis',''))+
        '\nDialogi: DO ODSŁUCHU I ZATWIERDZENIA; ruch ust wymaga audio-first i weryfikacji.\n\n')+         '\n'.join(f"{line} | {('DIALOG '+shots[idx]['speaker']+': '+shots[idx]['dialogue']+' ['+shots[idx]['acting_direction']+']') if shots[idx]['dialogue'] else 'bez dialogu'}"
                  for idx,line in enumerate(script))
    project['shots']=shots
    project['production_plan_version']='8.4.0'
    project['story_variant']=variant
    project['story_feature']=feature
    project['storyboard_stale']=False
    return project

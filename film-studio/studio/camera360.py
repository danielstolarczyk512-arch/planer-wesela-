"""Sogni 360 Shot Planner, V6.

Local, deterministic shot recipes inspired by official 360 camera waypoints.
No chargeable task is ever started from this module. 360 re-rendering is not
identical to 3D geometry and MUST be checked for identity / occlusions.
"""
from __future__ import annotations

import re

AZIMUTHS=('front','front-right','right','back-right','back','back-left','left','front-left')
ELEVATIONS=('low-angle','eye-level','elevated','high-angle')
DISTANCES=('close-up','medium','wide')
TEMPLATES={
 'portrait_trio': {'name':'Portret z trzech stron', 'use':'Arkusze i kontrola tożsamości postaci',
   'points':[('front','eye-level','medium'),('front-right','eye-level','medium'),('front-left','eye-level','medium'),('front','elevated','medium')]},
 'dialogue_reveal':{'name':'Filmowe odkrycie pary', 'use':'Krótkie ujęcie wspólne, maks. 45° zmiany',
   'points':[('front','eye-level','medium'),('front-right','eye-level','medium')]},
 'phone_reveal': {'name':'Odsłonięcie telefonu', 'use':'Płynny przejazd do ramienia, UI nakładane podczas montażu',
   'points':[('front-right','eye-level','medium'),('right','elevated','close-up')]},
 'wedding_room':{'name':'Odkrycie sali weselnej', 'use':'Duży plan i lekki ruch ponad scenografią',
   'points':[('front','eye-level','wide'),('front-right','elevated','wide')]},
 'hero_orbit':{'name':'Bohater — krótki orbit', 'use':'Jedna postać bez skomplikowanych gestów',
   'points':[('front','eye-level','medium'),('front-right','eye-level','medium'),('right','eye-level','medium')]},
 'full_360':{'name':'Pełen obrót 360 — ostrożnie', 'use':'Test modelu postaci lub produkt; nie domyślny montaż reklamowy',
   'points':[(v,'eye-level','medium') for v in AZIMUTHS]+[('front','eye-level','medium')]}
}
CAMERA_360_STYLE=(
 'Original Golden Storybook 3D animated character design, same approved character identity, '
 'fixed clothing and stable environment, warm hand-painted CGI shading, luminous amber rim light. '
 'Only camera perspective changes; the character performs one small simple gesture. '
 'No split-screen, duplicated people, new facial features, fake letters on screens, morphing limbs.'
)
WARNINGS=[
 '360 jest syntezą nowych widoków, a nie dokładną kamerą w prawdziwej scenie 3D; niewidoczne fragmenty są zgadywane.',
 'Przy dwóch osobach, dłoniach, telefonach i bogatym tle ryzyko deformacji rośnie.',
 'Pełne 360° często osłabia dramaturgię; w reklamie preferuj 2–3 punkty i maksymalnie 45–90° zmiany.',
 'Tekst interfejsu Nasz Dzień wstawiaj podczas montażu, a nie generuj przez 360.',
 'Nie wysyłaj automatycznie zleceń. Operacje wymagają aktualnego Unlimited, weryfikacji oraz billing_mode=subscription.'
]


def public_presets():
    return {'angles':{'azimuths':list(AZIMUTHS),'elevations':list(ELEVATIONS),'distances':list(DISTANCES)},
        'presets':{k:dict(name=v['name'],use=v['use'],angles_count=len(v['points']),points=[point(*p) for p in v['points']]) for k,v in TEMPLATES.items()},
        'warnings':WARNINGS,'service_url':'https://360.sogni.ai/',
        'cloud_generation_implemented':False,'local_planning_available':True}


def point(azimuth,elevation='eye-level',distance='medium'):
    if azimuth not in AZIMUTHS or elevation not in ELEVATIONS or distance not in DISTANCES:
        raise ValueError('Nieobsługiwany kąt, wysokość lub dystans kamery')
    return {'azimuth':azimuth,'elevation':elevation,'distance':distance}


def _angular_step(a,b):
    i,j=AZIMUTHS.index(a),AZIMUTHS.index(b)
    return 45*min((i-j)%8,(j-i)%8)


def analyze(points,shot=None):
    shot=shot or {}; issues=[]; warnings=[]
    if len(points)<2: issues.append('Co najmniej 2 punkty kamery')
    if len(points)>64:issues.append('Limit Sogni 360: 64 punkty kamery na projekt')
    for a,b in zip(points,points[1:]):
        try:
            step=_angular_step(a['azimuth'],b['azimuth'])
            if step>90:warnings.append(f'Duży skok perspektywy: {step}°. Dodaj punkt pośredni.')
        except (KeyError,ValueError): issues.append('Nieznany azymut')
        if a.get('distance')!=b.get('distance') and a.get('elevation')!=b.get('elevation'):
            warnings.append('Jednoczesna zmiana dystansu i wysokości może pogorszyć ciągłość.')
    if len(points)>4:warnings.append('W reklamie zalecane 2–4 punkty; dłuższy orbit wykorzystuj selektywnie.')
    if len(shot.get('characters') or [])>1:warnings.append('Dwie postacie: 360 może zmienić twarze i relację przestrzenną. Obowiązkowe porównanie ujęć.')
    if shot.get('mode')=='ui':issues.append('Nie wolno generować ekranów prawdziwej aplikacji przez Sogni 360.')
    if any('phone' in str(shot.get(k,'')).lower() for k in ('prompt','description')):
        warnings.append('Telefon powinien mieć pusty ekran do kompozycji, autentyczne UI dodaj w montażu.')
    return {'blocking':list(dict.fromkeys(issues)),'warnings':list(dict.fromkeys(warnings)),
        'recommendation':'Krótki ruch + zatwierdzone keyframes + prawdziwe klipy. Bez pełnego obrotu, gdy postacie rozmawiają.'}


def build(preset,shot=None,points=None):
    if preset not in TEMPLATES: raise ValueError('Nieznany preset Sogni 360')
    shot=shot or {}
    chosen=[point(**p) if isinstance(p,dict) else point(*p) for p in (points if points is not None else TEMPLATES[preset]['points'])]
    if not 2<=len(chosen)<=64:raise ValueError('Wybierz 2–64 punkty kamery')
    report=analyze(chosen,shot)
    if report['blocking']:raise ValueError('; '.join(report['blocking']))
    cast='ONA i ON' if {'ONA','ON'}<=set(shot.get('characters') or []) else ', '.join(shot.get('characters') or []) or 'zatwierdzona postać'
    return {'preset_id':preset,'name':TEMPLATES[preset]['name'], 'points':chosen,
            'characters':cast,'shot_id':shot.get('id',''),'description':TEMPLATES[preset]['use'],
            'prompt':CAMERA_360_STYLE+' Scene: '+str(shot.get('prompt') or shot.get('description') or 'character introduction')[:1500],
            'transition':'Camera Orbit' if preset!='phone_reveal' else 'Parallax Zoom',
            'render_policy':'manual_review_before_sogni_subscription_only','analysis':report,
            'data_source':'Sogni 360 official 8x4x3 angle space; local planner only'}


def make_cli_recipe(plan,source_path,output_dir='results/360'):
    """Machine-readable commands for explicit manual execution using official sogni-agent CLI.
    The app does not execute these or send source images. All jobs require subscription.
    The reference is deliberately a caller-supplied on-disk path (no shell invocation).
    """
    if not isinstance(source_path,str) or not source_path or len(source_path)>450:
        raise ValueError('Podaj lokalną ścieżkę do zatwierdzonej klatki (PNG/JPG)')
    if not source_path.lower().endswith(('.png','.jpg','.jpeg')):raise ValueError('Wymagany zatwierdzony obraz PNG/JPG')
    if not re.fullmatch(r'[A-Za-z0-9_./\\ -]+',source_path):raise ValueError('Niedozwolone znaki ścieżki')
    if not re.fullmatch(r'[A-Za-z0-9_./-]+',output_dir):raise ValueError('Nieprawidłowy folder wyjściowy')
    angles=[]
    for i,p in enumerate(plan['points']):
        args=['sogni-agent','--multi-angle','--billing-mode','subscription','--token-type','spark',
              '-c',source_path,'--azimuth',p['azimuth'],'--elevation',p['elevation'],
              '--distance',p['distance'],'--angle-strength','0.9',
              '-o',f'{output_dir}/angle_{i:02d}.png',
              'same approved animated character, Golden Storybook 3D, same face, no new people']
        angles.append({'step':i,'arguments':args,'result':f'{output_dir}/angle_{i:02d}.png'})
    return {'dry_run':True,'instructions':'Sprawdź sogni-agent --json --balance. Uruchamiaj RĘCZNIE pojedyncze polecenia; potwierdź paymentModel=subscription po każdym wyniku. Nie uruchamiaj tych komend bez zgody.',
            'required':'Node >=22.11.0, @sogni-ai/sogni-creative-agent-skill, ffmpeg do przejść',
            'commands':angles,'transitions':'Po zatwierdzeniu kątów użyj udokumentowanego --ref A --ref-end B --video i --billing-mode subscription. Nie generuj automatycznie wszystkich przejść.',
            'premium_fallback_enabled':False}

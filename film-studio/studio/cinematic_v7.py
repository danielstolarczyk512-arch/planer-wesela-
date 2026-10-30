"""V7 editorial grammar: coverage for dialogue + 360 risk analysis.
A cut to another shot is an edit, not a fake orbit from one static image.
"""
from __future__ import annotations

PRESETS={
 'speaker_closeup': {'title':'Twarz mówiącego','azimuth':'front','distance':'close-up','motion':'locked camera / slow 5 cm push-in','max_orbit':0},
 'speaker_medium':{'title':'Półzbliżenie','azimuth':'front-right','distance':'medium','motion':'restrained dolly-in','max_orbit':0},
 'reaction_closeup':{'title':'Reakcja drugiej osoby','azimuth':'front-left','distance':'close-up','motion':'static close-up, mouth stays closed','max_orbit':0},
 'over_shoulder':{'title':'Przez ramię','azimuth':'front-right','distance':'medium','motion':'quiet over-the-shoulder, keep line of action','max_orbit':0},
 'couple_two_shot':{'title':'Para w kadrze','azimuth':'front','distance':'medium','motion':'small lateral tracking','max_orbit':0},
 'gentle_orbit':{'title':'Orbit 45°','azimuth':'front-right','distance':'medium','motion':'two anchored approved angles, max 45 degrees','max_orbit':45},
 'location_reveal':{'title':'Odsłonięcie sali','azimuth':'front-right','distance':'wide','motion':'short lateral reveal with background parallax','max_orbit':45},
 'turnaround_reference_only':{'title':'Turntable 360 — tylko referencja','azimuth':'front','distance':'medium','motion':'model-sheet quality control, not speaking scene','max_orbit':360}
}

def plan(shot,preset='speaker_closeup',speaker=None):
    if preset not in PRESETS:raise ValueError('Nieznany preset reżyserski')
    if shot.get('mode')=='ui':raise ValueError('Ujęcie ekranu aplikacji wymaga prawdziwego UI')
    char=shot.get('characters') or []
    dialogue=bool((shot.get('dialogue') or '').strip())
    if speaker and speaker not in char:raise ValueError('Postać nie występuje w ujęciu')
    if preset=='turnaround_reference_only' and dialogue:
        raise ValueError('Pełnego 360 nie używaj podczas mówienia; zastosuj montaż ujęć')
    if dialogue and preset=='gentle_orbit':
        raise ValueError('Mowę realizuj na stabilnej kamerze; orbit wstaw jako osobne ujęcie bez dialogu')
    p=PRESETS[preset]
    return {'shot_id':shot.get('id'),'preset_id':preset,'speaker':speaker,
        'title':p['title'],'camera':p['motion'],'recommended_azimuth':p['azimuth'],
        'distance':p['distance'],'orbit_degrees':p['max_orbit'],
        'duration_seconds':shot.get('duration',0),
        'requires_separate_angle_frames':p['max_orbit']>0,
        'needs_lip_sync':dialogue and preset in ('speaker_closeup','speaker_medium','over_shoulder'),
        'qc':['zgodność twarzy z master','prawidłowa perspektywa i brak kolażu',
              'montaż według osi spojrzeń','kontrola ust dla scen dialogowych'],
        'warnings':(['Obrót 360 może zmienić tożsamość postaci i tło. Użyj zaakceptowanych widoków.']
                    if p['max_orbit'] else [])}

def coverage(shot, speaker='ONA'):
    if shot.get('mode')!='t2v':raise ValueError('Coverage dotyczy animowanych postaci')
    characters=shot.get('characters') or []
    if speaker not in characters:raise ValueError('Mówiący nie znajduje się w ujęciu')
    duration=float(shot.get('duration',0))
    if duration<=0:raise ValueError('Brak czasu ujęcia')
    listener='ON' if speaker=='ONA' else 'ONA'  # WUJEK speaks to ONA by default
    is_pair=listener in characters
    # A short shot has just a speaker close-up, avoiding fake unrendered cuts.
    if duration<3.5:return {'duration':duration,'shots':[{'preset':'speaker_closeup','speaker':speaker,'seconds':round(duration,2),'purpose':'wypowiedź'}], 'separate_renders_required':True}
    structure=[('couple_two_shot',None,0.15,'orientacja'),('speaker_closeup',speaker,0.60,'słowa + mimika'),
               ('reaction_closeup',listener if is_pair else speaker,0.25,'reakcja słuchającego' if is_pair else 'pauza')]
    pieces=[];assigned=0
    for i,(preset,who,part,purpose) in enumerate(structure):
        seconds=round(duration-assigned,3) if i==len(structure)-1 else round(duration*part,3)
        assigned+=seconds
        pieces.append({'preset':preset,'speaker':who,'seconds':seconds,'purpose':purpose,
            'requires_new_source_shot':True})
    return {'duration':duration,'shots':pieces,'separate_renders_required':True,
            'note':'To plan montażowy. Różne kąty wymagają osobnych klipów, nie tylko dopisania 360 do promptu.'}

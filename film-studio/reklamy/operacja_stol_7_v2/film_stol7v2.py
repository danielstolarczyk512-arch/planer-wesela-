"""OPERACJA STÓŁ 7 — MISJA NIEMOŻLIWA? (V2, reklama 20 s). Plan ujęć wg scenariusza V8.5 i hierarchii referencji:
1) MASTER STYLE V8.5 (portret pary), 2) arkusze tożsamości (zgodne z masterem), 3) opis sceny."""
PROJECT = 'operacja_stol_7_cinematic_v2'
HALL = ('one single elegant wedding hall in the evening: warm golden chandeliers, round banquet tables with white linen, crystal glasses, candles, '
        'string lights, soft golden bokeh, painterly depth')
ROLE = {
    'master': 'The FIRST image is the MASTER STYLE portrait of the couple: reproduce its stylized 3D animated-film rendering, warm golden light, skin, eyes, hair and clothes exactly. ',
    'ona': 'The woman must look EXACTLY like the woman in the first image and the second (character sheet): same face: a ROUND soft face with full rosy cheeks, very large round dark-brown eyes with thick lashes and the same proportions, thick arched brows, light freckles on nose and cheeks, a small closed-lip smile, brown hair in a loose bun with sunglasses resting on her head, black polka-dot halter top, light wide-leg trousers. ',
    'on': 'The man must look EXACTLY like the man in the first image and the third (character sheet): same face and jaw, short brown hair, gentle smile, dark grey T-shirt, beige shorts. ',
}
TAIL = (' Same stylized 3D animated-film look as the first reference image, not photorealistic, not plastic. Vertical 9:16 composition. '
        'ONE single continuous full-frame picture: not a collage, no split screen, no borders. No text, letters, numbers or logos anywhere in the picture.')

def P(scene, who):
    r = ROLE['master'] + (ROLE['ona'] if who in ('ona', 'both') else '') + (ROLE['on'] if who in ('on', 'both') else '')
    people = {'ona': 'ONE person only: the woman.', 'on': 'ONE person only: the man.', 'both': 'TWO people: the woman and the man, each exactly once.'}[who]
    return f'SCENE (follow exactly): {scene} {people} {r}{TAIL}'

SHOTS = [
 dict(id='v01', kind='ai', mode='reuse', chars='none', seconds=1.2, scene='Hak: szybki najazd wzdłuż zastawy na pustą winietkę (numer i napis w montażu).', camera='fast lateral dolly', reuse_from='stol7:o01'),
 dict(id='v02', kind='ai', mode='ia2v', chars='on', refs=['master', 'ona', 'on'], seconds=3.0, who='on', line='Stół siódmy. Mamy problem.',
   scene=f'Medium close-up of the man, seen from a slightly LOW angle like an action movie but without face distortion, in {HALL}. He holds a tablet in front of his chest with its BACK facing the camera (no screen visible), brows drawn together with comic alarm, eyes looking past the camera toward the woman off-screen, mouth closed.',
   camera='slight low angle, medium close-up, slow dolly-in', action='He speaks in a low serious whisper, brows tense, small natural head movement, never looks into the lens.'),
 dict(id='v04', kind='ai', mode='ia2v', chars='ona', refs=['master', 'ona', 'on'], seconds=2.25, who='ona', line='Spokojnie. Mam plan.',
   scene=f'Close-up reverse shot of the woman in slight three-quarter view in {HALL}: calm confident small smile, one eyebrow slightly raised, looking at the man off-screen, mouth closed, her sunglasses resting on her head.',
   camera='close-up, eye level, very gentle push-in', action='She speaks calmly with a warm confident smile and a slight raised eyebrow, a small head tilt.'),
 dict(id='v06', kind='ai', mode='i2v', chars='both', refs=['master', 'ona', 'on'], seconds=2.0,
   scene=f'Medium two-shot of the couple standing side by side in {HALL}, both looking down at the tablet the woman holds (back of the tablet toward the camera, no screen visible); he is exhaling with relief, shoulders dropping, she smiles at him warmly; both fully visible from the knees up.',
   camera='medium two-shot, eye level, slow dolly-out', action='He exhales with exaggerated relief and straightens; they exchange a warm knowing look and smile at each other. No high-five.'),
 dict(id='v07', kind='ai', mode='ia2v', chars='on', refs=['master', 'ona', 'on'], seconds=3.2, who='on', line='A stół ósmy?',
   scene=f'Over-the-shoulder shot in {HALL}: the man seen from a three-quarter side angle, the blurred back and shoulder of the woman in the near foreground at the edge of the frame: she wears the black polka-dot halter top with its neck tie visible from behind, her brown hair in a loose bun with sunglasses on her head; his face shows satisfaction that turns into a sudden worry; he looks toward her; mouth closed.',
   camera='over-the-shoulder, eye level, static with tiny handheld drift', action='He pauses, then asks with comic uncertainty, eyebrows going up and then a small worried wince.'),
 dict(id='v08', kind='ai', mode='i2v', chars='ona', refs=['master', 'ona', 'on'], seconds=1.8,
   scene=f'Close-up of the woman in {HALL}, a confident smirk, one eyebrow raised high, holding a smartphone up beside her face with its BACK toward the camera (no screen visible), looking straight at the man off-screen.',
   camera='close-up, slight push-in', action='She raises one eyebrow with a confident smirk and lifts the phone slightly, a tiny nod.'),
]
BY = {s['id']: s for s in SHOTS}
for s in SHOTS:
    if s['kind'] == 'ai' and s['mode'] != 'reuse':
        s['prompt_override'] = P(s['scene'], s['chars'])

# Tożsamość kobiety: wycinek twarzy z arkusza jako PIERWSZY obraz, master jako drugi, krótki prompt (długi opis sceny zaburzał twarz).
def _W(scene):
    return ('The first image is a close-up of the woman and the second image is the MASTER STYLE portrait of the couple. Draw THIS EXACT woman from both images: '
            'the same round face, the same very large round dark-brown eyes, thick arched brows, freckles, brown hair in a loose bun with sunglasses on her head, black polka-dot halter top. '
            f'{scene} ONE person only: the woman.' + TAIL)
for _id, _sc in (('v04', 'Close-up reverse shot in a warm golden wedding hall with chandeliers and set round tables: she is in slight three-quarter view, calm confident small smile, one eyebrow slightly raised, looking at someone off-screen to the side, mouth closed.'),
                 ('v08', 'Close-up in the same warm golden wedding hall: a confident smirk, one eyebrow raised, holding a smartphone beside her face with its BACK toward the camera (no screen visible), looking at someone off-screen.')):
    BY[_id]['refs'] = ['ona_face', 'master']; BY[_id]['prompt_override'] = _W(_sc)
BY['v06']['refs'] = ['ona_face', 'master', 'on']
BY['v06']['prompt_override'] = ('The first image is a close-up of the woman, the second is the MASTER STYLE portrait of the couple, the third is the man. Draw THIS EXACT couple: the woman with the same round face, very large round dark-brown eyes, freckles, brown bun with sunglasses on her head, black polka-dot halter top and light wide trousers; the man with the same face, short brown hair, dark grey T-shirt and beige shorts. '
    'Medium two-shot in a warm golden wedding hall with chandeliers and set round tables: they stand side by side looking down at a tablet she holds (its back toward the camera), he exhales with relief, she smiles warmly at him; both visible from the knees up. TWO people only.' + TAIL)

# Scena 6 jako shot / reverse shot (twarz kobiety jest wiarygodna tylko w zbliżeniu z wycinkiem arkusza jako pierwszą referencją).
BY['v06']['chars'] = 'ona'; BY['v06']['seconds'] = 0.9
BY['v06']['action'] = 'She looks at the man and smiles warmly with relief, a small satisfied nod.'
BY['v06']['prompt_override'] = _W('Close-up in the same warm golden wedding hall: she looks at someone off-screen with a warm relieved smile and shining eyes, mouth closed, the sunglasses on her head.')
_m = dict(id='v06m', kind='ai', mode='i2v', chars='on', refs=['on', 'master'], seconds=0.9,
          action='He lets out an exaggerated breath of relief, shoulders dropping, and breaks into a happy smile.')
_m['prompt_override'] = ('The first image is a character sheet of the man and the second is the MASTER STYLE portrait of the couple. Draw THIS EXACT man: the same face and jaw, short brown hair, gentle smile, dark grey T-shirt. '
    'Medium close-up in a warm golden wedding hall with chandeliers: he looks toward someone off-screen with a relieved happy smile, mouth closed. ONE person only: the man.' + TAIL)
SHOTS.append(_m); BY['v06m'] = _m
BY['v06']['refs'] = ['ona_face', 'master']

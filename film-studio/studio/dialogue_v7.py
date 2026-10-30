"""V7 Polish-first audio track and talking-shot planning. No paid calls or secrets.

Final spoken voice is supplied and approved by the editor *before* video creation.
This avoids adding a voice track to a silent, unmoving face at montage time.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

SPEAKERS=('ONA','ON','WUJEK')
AUDIO_CONTENT_TYPES={'audio/wav':'.wav','audio/x-wav':'.wav','audio/mpeg':'.mp3','audio/mp3':'.mp3','audio/mp4':'.m4a','audio/x-m4a':'.m4a'}
MAX_BYTES=25*1024*1024
MAX_SECONDS=60


def audio_probe(file):
    path=Path(file)
    if not path.is_file() or path.stat().st_size>MAX_BYTES or path.stat().st_size<100:
        raise ValueError('Nieprawidłowe lub zbyt duże nagranie audio')
    try:
        p=subprocess.run(['ffprobe','-v','error','-select_streams','a:0',
            '-show_entries','stream=codec_name,sample_rate,channels,duration',
            '-show_entries','format=duration','-of','json',str(path)],capture_output=True,text=True,timeout=15)
        if p.returncode:raise ValueError('FFprobe nie rozpoznał nagrania')
        data=json.loads(p.stdout);stream=(data.get('streams') or [{}])[0]
        if not stream.get('codec_name'):raise ValueError('Nagranie nie zawiera ścieżki audio')
        dur=float(data.get('format',{}).get('duration') or stream.get('duration') or 0)
        if not 0.20<=dur<=MAX_SECONDS:raise ValueError('Długość nagrania musi wynosić 0,2–60 s')
        return {'seconds':round(dur,3),'codec':stream['codec_name'],
                'sample_rate':int(stream.get('sample_rate') or 0),
                'channels':int(stream.get('channels') or 0),
                'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    except (FileNotFoundError,subprocess.TimeoutExpired):
        raise ValueError('Zainstaluj FFprobe, aby weryfikować dźwięk') from None
    except (KeyError,IndexError,TypeError,OverflowError) as e:
        raise ValueError('Nieprawidłowa struktura pliku audio') from e


def dialogue_clean(text):
    if not isinstance(text,str) or len(text)>550:return False
    return bool(text.strip()) and not bool(re.search(r'[<>\x00-\x08]',text))


def prepare_talking_shot(shot,speaker,transcript,recording,angle='speaker_closeup'):
    if shot.get('mode')!='t2v':raise ValueError('Ujęcie produktu/UI nie może udawać ruchu ust postaci')
    if speaker not in SPEAKERS or speaker not in (shot.get('characters') or []):
        raise ValueError('Mówiący musi należeć do obsady tego ujęcia')
    if not dialogue_clean(transcript):raise ValueError('Podaj poprawny polski tekst wypowiedzi (maks. 550 znaków)')
    info=audio_probe(recording)
    if info['seconds']>15.08:raise ValueError('Podziel dialog na ujęcia krótsze niż limit H3 (15,08 s)')
    if angle not in ('speaker_closeup','speaker_medium','over_shoulder'):
        raise ValueError('Nieznany wariant kamery dialogowej')
    return {'speaker':speaker,'language':'pl-PL','transcript':transcript.strip(),
            'voice_path':str(Path(recording).resolve()),'audio':info,
            'camera_preset':angle,'model':'minimax-h3-fasth3-ia2v-turbo',
            'mode':'image_audio_to_video','audio_first':True,'approval_required':True,
            'lip_sync_review':False,
            'notes':'H3 porusza usta na podstawie dostarczonego nagrania. Poprawność wymaga ludzkiej kontroli odsłuchowej.'}


def prompt_for_speaker(speaker,transcript,camera='speaker_closeup'):
    if speaker not in SPEAKERS or not dialogue_clean(transcript):raise ValueError('Niepoprawny speaker lub tekst')
    framings={'speaker_closeup':'intimate close-up of only the speaking character, full face clearly visible, face occupying 45 percent of frame',
              'speaker_medium':'medium close-up with both shoulders and the full face visible',
              'over_shoulder':'over-the-shoulder close-up of the speaking character; the listener is partly out of focus'}
    if camera not in framings:raise ValueError('Nieprawidłowa kamera')
    return (f'Use the approved Golden Storybook 3D character. {framings[camera]}. '
            'One stable continuous cinematic shot, eye-level camera, warm amber practical light, '
            'subtle head motion, authentic small eye movements and facial expressions. '
            f'Character {speaker} speaks Polish naturally with the supplied audio: '
            f'<d>[Polish] {transcript.strip()}</d>. '
            'The visible lips and jaw follow the actual uploaded voice soundtrack; '
            'keep the other character silent and listening if visible. '
            'Preserve facial identity, hair and wardrobe; no double faces, split screens or subtitles embedded in image.')

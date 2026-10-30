"""Głosy do OPERACJA STÓŁ 7 V2: 3 kwestie x kilka wariantów (Supertonic 3, lokalnie, CPU)."""
import json
import os

from supertonic import TTS

OUT = r"D:\film-studio\OPERACJA_STOL_7_V2\POLISH_VOICES\takes"
os.makedirs(OUT, exist_ok=True)
tts = TTS(auto_download=True)
V = {"on": tts.get_voice_style(voice_name="M5"), "ona": tts.get_voice_style(voice_name="F5")}

# (id, kto, tekst, parametry) — wariant A to naturalny zapis, B/C zmieniają tempo, pauzy i kroki dyfuzji
LINES = {
    "M1": ("on", [
        ("A", "Stół siódmy. Mamy problem.", dict(speed=0.92, total_steps=10, silence_duration=0.45)),
        ("B", "Stół siódmy... Mamy problem.", dict(speed=0.88, total_steps=12, silence_duration=0.6)),
        ("C", "Stół siódmy. Mamy problem!", dict(speed=0.96, total_steps=10, silence_duration=0.35)),
    ]),
    "K1": ("ona", [
        ("A", "Spokojnie. Mam plan.", dict(speed=0.98, total_steps=10, silence_duration=0.5)),
        ("B", "Spokojnie... Mam plan.", dict(speed=0.93, total_steps=12, silence_duration=0.6)),
        ("C", "Spokojnie. Mam plan.", dict(speed=1.04, total_steps=10, silence_duration=0.4)),
    ]),
    "M2": ("on", [
        ("A", "A stół ósmy?", dict(speed=0.92, total_steps=10)),
        ("B", "A... stół ósmy?", dict(speed=0.9, total_steps=12, silence_duration=0.5)),
        ("C", "A stół ósmy?", dict(speed=1.0, total_steps=10)),
    ]),
}
meta = {}
for lid, (who, takes) in LINES.items():
    for tag, text, kw in takes:
        wav, dur = tts.synthesize(text, voice_style=V[who], lang="pl", **kw)
        f = os.path.join(OUT, f"{lid}_{tag}.wav")
        tts.save_audio(wav, f)
        d = float(dur) if not hasattr(dur, "__len__") else float(dur[0])
        meta[f"{lid}_{tag}"] = dict(who=who, text=text, params=kw, seconds=round(d, 3), file=f)
        print(lid, tag, round(d, 2), flush=True)
json.dump(meta, open(os.path.join(OUT, "meta.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)

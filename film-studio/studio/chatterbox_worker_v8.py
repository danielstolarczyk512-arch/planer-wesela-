"""Standalone OPTIONAL local TTS worker. Never imports on application startup."""
import json
import sys
from pathlib import Path


def main():
    args=json.loads(sys.stdin.read())
    import torch
    import torchaudio as ta
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    device='cuda' if torch.cuda.is_available() else 'cpu'
    if device != 'cuda':
        raise RuntimeError('Ten profil wysokiej jakości wymaga NVIDIA CUDA. Użyj importu audio bez GPU.')
    model=ChatterboxMultilingualTTS.from_pretrained(device=device, t3_model="v3")
    output=Path(args['output_dir']).resolve();output.mkdir(parents=True,exist_ok=True)
    ref=args.get('reference_path')
    files=[]
    for i,variant in enumerate(args['variants']):
        kwargs={'language_id':'pl','exaggeration':float(variant['exaggeration']),
                'cfg_weight':float(variant['cfg_weight'])}
        if ref:kwargs['audio_prompt_path']=ref
        wav=model.generate(args['text'],**kwargs)
        f=output/f'variant_{i+1}.wav'
        ta.save(str(f),wav,model.sr);files.append(str(f))
    print(json.dumps({'files':files,'device':device}))

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('Local voice synthesis error: '+str(exc)[:220],file=sys.stderr)
        sys.exit(1)

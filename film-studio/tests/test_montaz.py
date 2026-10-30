import json
import tempfile
import unittest
from pathlib import Path

from montaz import probe_format, render


class MontageTests(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(probe_format('9:16','final'),(1080,1920))
        self.assertEqual(probe_format('16:9','final'),(1920,1080))
        with self.assertRaises(ValueError):probe_format('4:3','final')
    def test_missing_real_clips_not_silently_faked(self):
        with tempfile.TemporaryDirectory() as d:
            project=Path(d)/'project.json'
            project.write_text(json.dumps({'format':'9:16','shots':[{'id':'S01','duration':3,'mode':'ui'}]}))
            with self.assertRaisesRegex(FileNotFoundError,'S01'):render(project,d,Path(d)/'out.mp4',quality='draft')

    def test_actual_ffmpeg_three_clips(self):
        import shutil
        import subprocess
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            self.skipTest('ffmpeg/ffprobe not installed')
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);clips=d/'clips';clips.mkdir()
            for i,color in enumerate(['blue','red','pink'],1):
                subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',
                    '-f','lavfi','-i',f'color=c={color}:s=240x426:r=24:d=0.6',
                    '-c:v','libx264','-preset','ultrafast',str(clips/f'S{i:02}.mp4')],check=True)
            p=d/'proj.json';p.write_text(json.dumps({'format':'9:16',
                'shots':[{'id':f'S{i:02}', 'duration':0.3,'mode':'t2v'} for i in range(1,4)]}))
            output=d/'result.mp4';result=render(p,clips,output,quality='draft')
            self.assertTrue(output.exists());self.assertGreater(output.stat().st_size,1000)
            self.assertEqual(result['shots'],3)

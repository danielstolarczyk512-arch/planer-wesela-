"""Regresja V6: Sogni CLI dopisuje nazwę kąta do pliku wyjściowego."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio import camera360_cli, reference_v6, sogni

PNG=bytes([0x89])+b'PNG'+bytes([13,10,26,10])+b'0'*2000

class OutputNaming(unittest.TestCase):
    def test_cli_suffix_file_is_found(self):
        with tempfile.TemporaryDirectory() as d,patch.object(camera360_cli,'RENDERS',Path(d)),patch.object(reference_v6,'find',return_value={'review':'approved'}),             patch.object(reference_v6,'file_for',return_value=Path(d)/'ref.png'),patch.object(sogni,'key',return_value='k'),patch.object(sogni,'assert_active_subscription',return_value={}),             patch('shutil.which',return_value='sogni-agent'):
            def fake_run(cmd,**k):
                out=Path(cmd[cmd.index('-o')+1]);(out.parent/(out.stem+'-front-right.png')).write_bytes(PNG)
                return subprocess.CompletedProcess(cmd,0,json.dumps({'success':True}),'')
            with patch('subprocess.run',fake_run):
                meta=camera360_cli.generate_one('X','front-right','eye-level','medium',True)
            self.assertTrue((Path(d)/(meta['render_id']+'.png')).exists())
            self.assertEqual(meta['billing_mode_requested'],'subscription')
    def test_failure_message_has_safe_tail_without_key(self):
        with tempfile.TemporaryDirectory() as d,patch.object(camera360_cli,'RENDERS',Path(d)),patch.object(reference_v6,'find',return_value={'review':'approved'}),             patch.object(reference_v6,'file_for',return_value=Path(d)/'ref.png'),patch.object(sogni,'key',return_value='SECRETKEY'),patch.object(sogni,'assert_active_subscription',return_value={}),             patch('shutil.which',return_value='sogni-agent'):
            bad=subprocess.CompletedProcess([],1,'','Error SECRETKEY see https://x.y/z?sig=abc')
            with patch('subprocess.run',return_value=bad):
                with self.assertRaises(RuntimeError) as cm:camera360_cli.generate_one('X','front','eye-level','medium',True)
            self.assertNotIn('SECRETKEY',str(cm.exception));self.assertNotIn('https://',str(cm.exception));self.assertIn('[KEY]',str(cm.exception))

class Size(unittest.TestCase):
    def test_output_size_keeps_aspect(self):
        self.assertEqual(camera360_cli._output_size(Path('assets/reference_v6/PARA/INTERACTIONS/02_laptop.png')),(1152,768))
    def test_command_has_size_and_subscription(self):
        ref=Path('assets/reference_v6/PARA/INTERACTIONS/02_laptop.png')
        with tempfile.TemporaryDirectory() as d,patch.object(camera360_cli,'RENDERS',Path(d)),patch.object(reference_v6,'find',return_value={'review':'approved'}),             patch.object(reference_v6,'file_for',return_value=ref),patch.object(sogni,'key',return_value='k'),patch.object(sogni,'assert_active_subscription',return_value={}),patch('shutil.which',return_value='sogni-agent'):
            seen={}
            def fake(cmd,**k):
                seen['c']=cmd;out=Path(cmd[cmd.index('-o')+1]);out.write_bytes(PNG);return subprocess.CompletedProcess(cmd,0,'{}','')
            with patch('subprocess.run',fake):camera360_cli.generate_one('X','front','eye-level','medium',True)
            c=seen['c'];self.assertIn('subscription',c);self.assertEqual(c[c.index('-w')+1],'1152');self.assertEqual(c[c.index('-h')+1],'768')


class Jpeg(unittest.TestCase):
    def test_jpeg_named_png_is_converted(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'x.png';Image.new('RGB',(64,64),(200,120,40)).save(f,'JPEG')
            self.assertTrue(camera360_cli._normalize_to_png(f));self.assertEqual(f.read_bytes()[1:4],b'PNG')
            f.write_bytes(b'not an image at all, definitely');self.assertFalse(camera360_cli._normalize_to_png(f))


if __name__=='__main__':unittest.main()

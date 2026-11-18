"""A retimed shot must consume the right source range and preserve 30 fps."""
import subprocess
import tempfile
import unittest
from pathlib import Path

import cv2

from services.achievement_montage import prepare_scene,validate_recipe
from services.editing import probe_media
from utils.helpers import get_ffmpeg_path


class MontageRetimeTests(unittest.TestCase):
    def test_half_speed_uses_one_second_of_source_for_two_seconds_of_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'ramp.mp4';cache=root/'cache';cache.mkdir();ff=get_ffmpeg_path()
            subprocess.run([ff,'-v','error','-y','-f','lavfi','-i',
                "color=c=black:s=160x90:r=60:d=2,geq=lum='16+100*T':cb=128:cr=128",
                '-c:v','libx264','-pix_fmt','yuv420p',str(source)],check=True,capture_output=True)
            scene={'path':str(source),'source_start':.25,'duration':2,'playback_rate':.5}
            target=prepare_scene(scene,cache,ff);media=probe_media(target,ff)
            self.assertAlmostEqual(media['duration'],2,delta=.06)
            values=[]
            for path,time in [(source,1.23),(target,1.97)]:
                capture=cv2.VideoCapture(str(path));capture.set(cv2.CAP_PROP_POS_MSEC,time*1000)
                ok,frame=capture.read();capture.release();self.assertTrue(ok);values.append(float(frame.mean()))
            self.assertAlmostEqual(values[0],values[1],delta=6)
            recipe={'schema':'ssr-achievement-montage','canvas':{'width':160,'height':90,'fps':30},
                'hook':{'text':'TEST','duration':0},'music':{'path':str(source)},
                'scenes':[scene,{'path':str(source),'source_start':1.25,'duration':.5}]}
            self.assertEqual(validate_recipe(recipe),2.5)
            recipe['scenes'][1]['source_start']=1.0
            with self.assertRaisesRegex(ValueError,'Repeated source range'):
                validate_recipe(recipe)


if __name__=='__main__':unittest.main()

"""Shared tracking follows small and large movements with a slow continuous pan."""
import math
import unittest
from services.face_tracking import CameraPlanner, Track, scene_changed

def face(center, ident=1):
    return Track(ident,(center-.04,.2,.08,.22),0)

class CameraSmoothingTests(unittest.TestCase):
    def test_small_head_motion_is_followed_slowly_in_all_cropped_formats(self):
        for aspect in (9/16,1,4/3):
            planner=CameraPlanner(1920,1080,aspect_ratio=aspect)
            first=planner.update([face(.50)],0)['x']
            positions=[planner.update([face(.512)],i/30)['x'] for i in range(1,121)]
            self.assertGreater(positions[0],first)
            self.assertLess(positions[14]-first,4)
            self.assertGreater(positions[-1]-first,22)
            self.assertLessEqual(positions[-1]-first,23.04)
            self.assertTrue(all(a<b for a,b in zip(positions,positions[1:])))

    def test_real_motion_eases_without_overshoot_or_fast_steps(self):
        planner=CameraPlanner(1920,1080)
        first=planner.update([face(.5)],0)['x']
        positions=[first]+[planner.update([face(.65)],i/30)['x'] for i in range(1,151)]
        steps=[b-a for a,b in zip(positions,positions[1:])]
        self.assertTrue(all(-.0001<=step<=planner.max_pan/30+.0001 for step in steps))
        self.assertLess(positions[3]-first,2)
        self.assertGreater(positions[-1]-first,250)
        self.assertLessEqual(positions[-1]-first,288)
        self.assertLess(steps[15],max(steps))
        self.assertLess(steps[-1],max(steps))

    def test_response_does_not_depend_on_frame_rate(self):
        results=[]
        for fps in (24,30,60):
            planner=CameraPlanner(1920,1080)
            planner.update([face(.5)],0)
            for i in range(1,2*fps+1):
                result=planner.update([face(.65)],i/fps)
            results.append(result['x'])
        self.assertLess(max(results)-min(results),6)

    def test_noisy_second_face_and_short_loss_do_not_change_canvas(self):
        planner=CameraPlanner(1920,1080)
        first=planner.update([face(.5)],0)
        self.assertEqual(planner.update([face(.5),face(.8,2)],.1)['mode'],'speaker')
        self.assertEqual(planner.update([], .2)['x'],first['x'])
        self.assertEqual(planner.update([face(.5)],.3)['x'],first['x'])
        self.assertEqual(planner.update([face(.5),face(.8,2)],1.2)['mode'],'fit')

    def test_reacquired_face_continues_slow_pan_instead_of_snapping(self):
        planner=CameraPlanner(1920,1080)
        first=planner.update([face(.5)],0)['x']
        planner.update([],1)
        resumed=planner.update([face(.52)],1+1/30)['x']
        self.assertLess(abs(resumed-first),planner.max_pan/30)

    def test_scene_cut_reframes_immediately_without_slow_pan_between_shots(self):
        planner=CameraPlanner(1920,1080)
        first=planner.update([face(.4)],0)['x']
        result=planner.update([face(.7,2)],.1,scene_cut=True)
        self.assertGreater(result['x']-first,500)
        self.assertTrue(result['scene_cut'])
        self.assertEqual(result['track_id'],2)

    def test_dark_studio_shot_changes_are_detected_but_small_motion_is_not(self):
        self.assertTrue(scene_changed([25]*256,[75]*256))
        self.assertFalse(scene_changed([25]*256,[30]*256))

"""Build an editable native Jedag Jedug recipe and render its Ironman example."""
import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.achievement_montage import render_recipe, validate_recipe
from services.storage import atomic_json

OUT = ROOT / 'output/ironman-tests-20261013'
DEST = OUT / 'jedag-jedug'


def build():
    read = lambda p: json.loads(p.read_text(encoding='utf-8'))
    a, b, c = [read(OUT / 'recipes' / f'ironman-test-{n:02}.json') for n in (1, 2, 3)]
    fixed = read(OUT / 'revisions/film-burn-v2/recipe.json')
    measured = read(DEST / 'beat-analysis.json')
    fps = 30
    period_frames = round(fps * 60 / measured['estimated_bpm'])
    drop_frame = round((5 + measured['phase_seconds']) * fps)
    scenes = copy.deepcopy([c['scenes'][0], c['scenes'][1], c['scenes'][2],
                            c['scenes'][3], b['scenes'][3], c['scenes'][5],
                            a['scenes'][5], a['scenes'][6], fixed['scenes'][-1]])
    for scene, seconds in zip(scenes, [drop_frame / fps, 1, 2, 2, 2, 2, 3, 3, 3]):
        scene['duration'] = seconds
    end_frame = drop_frame + 15 * fps
    effects = {'enabled': True, 'start_seconds': drop_frame / fps,
        'end_seconds': end_frame / fps,
        'beats_seconds': [frame / fps for frame in range(drop_frame, end_frame, period_frames)],
        'estimated_bpm': measured['estimated_bpm'], 'music_phase_seconds': measured['phase_seconds'],
        'measurement': str((DEST / 'beat-analysis.json').resolve()),
        'punch_scale': .075, 'shake_pixels': 8, 'rotation_degrees': .4,
        'brightness_pulse': .055, 'decay_seconds': .28,
        'registry_inspiration': ['beat-accent', 'camera-shake'],
        'native_adaptation': True}
    recipe = {k: copy.deepcopy(c[k]) for k in ['schema', 'version', 'canvas', 'constraints',
                                              'cta', 'hook', 'music', 'reference_role']}
    recipe.update(id='ironman-jedag-jedug-01', variant='achievement_jedag_jedug',
        title='Ironman · Jedag Jedug', description='Latihan konsisten hingga menuntaskan IRONMAN 70.3. Perjalanan Bevan Pramudito.',
        finished_clipper_reference_used_as_source=False, scenes=scenes, beat_effects=effects,
        transitions=[{'at': (drop_frame + 9 * fps) / fps, 'duration': .3, 'intensity': .65, 'seed': 21},
                     {'at': end_frame / fps, 'duration': .3, 'intensity': .65, 'seed': 22}])
    recipe['hook'].update(duration=drop_frame / fps,
        text='LATIHAN KONSISTEN\nIRONMAN DITUNTASKAN\nBEVAN PRAMUDITO')
    duration = validate_recipe(recipe)
    template = {k: copy.deepcopy(recipe[k]) for k in ['version', 'canvas', 'hook', 'constraints', 'cta', 'beat_effects']}
    template.update(schema='ssr-achievement-montage-template', id='achievement_jedag_jedug',
        name='Jedag Jedug', renderer='services.achievement_montage.render_recipe',
        editable_fields=['hook', 'canvas', 'constraints', 'scenes', 'music', 'beat_effects', 'transitions', 'cta'],
        scene_slots=[{'role': role, 'duration_beats': beats} for role, beats in
            [('identity_hook', None), ('running_detail', 2), ('swim_training', 4),
             ('cycle_training', 4), ('run_training', 4), ('race_swim', 4),
             ('race_cycle', 6), ('race_run', 6), ('positive_finisher', 6)]],
        music_policy={'beat_grid': 'Measure on the selected music passage, then snap cuts and beats to output frames.',
                      'new_track_requires_new_grid': True, 'music_is_separate_asset': True},
        scene_policy={'requires_official_source': True, 'same_source_range_within_clip': False,
                      'hook_held_without_beat_effects': True, 'final_expression_requires_visual_review': True,
                      'stable_final_seconds': 3},
        editing_interface='editable_json_recipe')
    template['constraints']['hook_required_word'] = ''
    template['hook']['text'] = 'JUDUL CAMPAIGN\nPROSES & PENCAPAIAN\nNAMA TOKOH'
    # The measured grid is specific to the separate example soundtrack.
    template['beat_effects']['grid_role'] = 'example_120_bpm_remeasure_when_music_changes'
    atomic_json(DEST / 'recipe.json', recipe)
    atomic_json(OUT / 'templates/achievement_jedag_jedug.json', template)
    atomic_json(DEST / 'timeline.json', {'duration_seconds': duration, 'fps': fps,
        'cuts_seconds': [sum(s['duration'] for s in scenes[:i]) for i in range(1, len(scenes))],
        'beat_effects': effects, 'stable_ending_seconds': 3})
    print(f'Jedag Jedug definition and {duration:.3f}s example recipe saved.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'render'])
    args = parser.parse_args()
    if args.action == 'build':
        build()
    else:
        render_recipe(DEST / 'recipe.json', DEST / 'master.mp4')

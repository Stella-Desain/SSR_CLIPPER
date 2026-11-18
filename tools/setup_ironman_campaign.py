"""Create the new Ironman workspace without changing the old GMGN campaign."""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import WebAPI
from services.storage import atomic_json

OUT = ROOT / 'output/ironman-tests-20261013'
REF = ROOT / 'output/ironman-reference-20261013'
ACCOUNT = '6ace2d7262caae1e047427c2'
URL = 'https://app.clippo.id/campaigns/cmu8mx81e0fwab826k9w6pug7'


def api_instance():
    api = WebAPI.__new__(WebAPI)
    api.config_file = str(ROOT / 'config.json')
    api.output_dir = str(ROOT / 'output')
    api.worker_enabled = False
    return api


def main():
    api = api_instance()
    mapped = json.loads((REF / 'campaign-mapped-brief.json').read_text(encoding='utf-8'))
    payload = copy.deepcopy(mapped['brief'])
    payload.update(status='active', audience_scope='Indonesia · prestasi Bevan, disiplin latihan dan Ironman triathlon',
                   account_ids=[ACCOUNT], source_links=copy.deepcopy(mapped['source_links']),
                   external_campaign={**mapped['metadata'], 'url': URL, 'campaign_id': 'cmu8mx81e0fwab826k9w6pug7'})
    payload['image_url'] = mapped['metadata'].get('image_url', '')
    payload['external_campaign']['cta_source_value'] = payload['brief'].get('cta')
    if payload['brief'].get('cta', '').strip() == '-':
        payload['brief']['cta'] = ''
    # Source collection requirements are preserved. They describe approved origins;
    # each output's provenance records the individual files actually selected.
    for link in payload['source_links']:
        link['campaign_required_source'] = link.get('required', False)
        link['required'] = False
    payload['editing'] = {'preset_id': 'standard', 'selection_mode': 'fixed', 'review_mode': 'manual',
        'framing': 'fit', 'source_role': 'campaign', 'endcard': {'path': '', 'required': False},
        'montage': {'renderer': 'services.achievement_montage', 'status': 'test_recipes',
                    'recipe_directory': str(OUT / 'recipes'), 'hook_seconds': 5,
                    'transitions': {'type': 'film_burn', 'enabled': True, 'editable': True}},
        'music': {'policy': 'auto', 'required': True, 'catalog': 'jamendo'}}
    payload['assets'] = []
    race_ids = {a['id'] for a in json.loads((OUT / 'sunshine-inventory.json').read_text(encoding='utf-8')).get('files', [])} if (OUT / 'sunshine-inventory.json').exists() else set()
    for item in json.loads((OUT / 'assets-index.json').read_text(encoding='utf-8')):
        # Lifestyle assets stay in the central index, outside this campaign's pool.
        if item['id'] == '1Di-7obtEoG9-IC-L806rI-kCgdkg-gbR':
            continue
        if item['id'] in race_ids or item['title'].startswith(('Bevan Running', 'Bevan Struggle')) or item['id'] in {
            '1_4rxERjSXHsiuhywN2qMI02UmbgXRjUc', '1V8T8h5CCXTUvdC2iOh2ZhXcVb4LeDfhz',
            '1CnJmFTEJqWGxpPnc1ruMwZe_ZbxOI6oh', '1vvSKOAXyxX16Wef6MsFt2osJuBS8q9tP'}:
            payload['assets'].append({'path': item['path'], 'name': item['title'], 'role': 'broll',
                                     'sha256': item['sha256'], 'provenance': item['url']})
    for name in ['IMG_0937.png', 'IMG_0939.png']:
        payload['assets'].append({'path': str(REF / 'official-assets' / name), 'name': 'Ironman resmi · ' + name,
                                 'role': 'image', 'provenance': 'https://drive.google.com/drive/folders/17spOI2GBEbuevxka4NTd5hEZz2Uq3UCL'})
    vlog = OUT / 'assets/official-ironman-vlog.mp4'
    if vlog.exists():
        payload['assets'].append({'path': str(vlog), 'name': 'Vlog resmi · Dari 0 jadi Ironman 70.3 dalam 5 Bulan',
            'role': 'video', 'required': False, 'provenance': 'https://www.youtube.com/watch?v=u9d14ssEc0c'})
    for name, origin in [('bevan-finisher-728.png', 'https://www.youtube.com/watch?v=u9d14ssEc0c&t=728s'),
                         ('bevan-finish-close-7_8.png', 'https://drive.google.com/file/d/1QR5DUiZ5gyOGwx2PYJnfxcauXB64U1Kp/view')]:
        path = OUT / 'assets' / name
        if path.exists():
            payload['assets'].append({'path': str(path), 'name': 'Frame pencapaian resmi · ' + name,
                                     'role': 'image', 'provenance': origin})
    prior = next((c for c in api._get_cfg().get('campaigns', [])
                  if c.get('external_campaign', {}).get('campaign_id') == 'cmu8mx81e0fwab826k9w6pug7'), None)
    result = api.save_campaign_workspace(prior['id'] if prior else None, payload)
    if result['status'] != 'ok':
        raise RuntimeError(result)
    campaign = result['campaign']
    profile = api.save_account_profile(ACCOUNT, {'campaign_id': campaign['id'], 'name': 'Anak.clipo',
        'platform': 'instagram', 'daily_limit': 3})
    if profile['status'] != 'ok':
        raise RuntimeError(profile)
    atomic_json(OUT / 'campaign-saved.json', result)
    print(json.dumps({'campaign_id': campaign['id'], 'name': campaign['name'],
                      'assets': len(campaign['assets']), 'account_ids': campaign['account_ids'],
                      'readiness': result['readiness']}, ensure_ascii=True))


if __name__ == '__main__':
    main()

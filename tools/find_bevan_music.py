"""Find commercially reusable instrumental hip-hop tracks in configured Jamendo."""
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
import sys
sys.stdout.reconfigure(encoding='utf-8',errors='replace')
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/bevan-production-20261009'
cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
def query(offset):
    params={'client_id':cfg['jamendo']['client_id'],'format':'json','limit':100,'offset':offset,
            'include':'musicinfo','audioformat':'mp32','audiodlformat':'mp32','fuzzytags':'hiphop'}
    return requests.get('https://api.jamendo.com/v3.0/tracks/',params=params,timeout=40).json().get('results',[])
rows=[r for group in ThreadPoolExecutor(max_workers=4).map(query,[0,100,200,300,400]) for r in group]
usable=[r for r in rows if '/by/' in r.get('license_ccurl','') and r.get('audiodownload_allowed')
        and r.get('musicinfo',{}).get('vocalinstrumental')=='instrumental']
(OUT/'music-candidates.json').write_text(json.dumps(usable,ensure_ascii=False,indent=2),encoding='utf-8')
for row in usable:
    print({k:row.get(k) for k in ('id','name','artist_name','duration','license_ccurl','musicinfo')},flush=True)

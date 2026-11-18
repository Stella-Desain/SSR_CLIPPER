"""Serve the real UI against a temporary offline bridge. No account/provider calls.

Run: python tests/ui_fixture.py --port 8769
"""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_workflow import Harness


def main():
    args=argparse.ArgumentParser();args.add_argument('--port',type=int,default=8769)
    args.add_argument('--account-error',action='store_true');args.add_argument('--music',action='store_true');options=args.parse_args()
    project=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as temporary:
        folder=Path(temporary);api=Harness(folder);errors=[]
        campaign=api.save_campaign_workspace(None,{'name':'Demo keluarga','audience_scope':'Film keluarga','account_ids':['a'],
            'brief':{'hashtags':['#keluarga'],'durasi_min':1,'durasi_max':60}})['campaign']
        api.save_account_profile('a',{'audience_scope':'Film keluarga'})
        media=folder/'master.mp4'
        subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=0x244c35:s=270x480:d=2',
            '-c:v','libx264','-pix_fmt','yuv420p',str(media)],check=True,capture_output=True)
        api._register_clip(media,{'title':'Cerita keluarga','caption':'Cerita keluarga #keluarga','campaign_id':campaign['id'],
            'campaign_version_id':campaign['version_id'],'campaign_snapshot':campaign,'duration_seconds':2})
        if options.music:
            from services.editing import mix_music, file_sha256
            dry=folder/'music-dry.mp4'
            subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=0x244c35:s=270x480:d=6',
                '-f','lavfi','-i','sine=frequency=440:duration=6','-c:v','libx264','-threads','2',
                '-pix_fmt','yuv420p','-c:a','aac',str(dry)],check=True,capture_output=True)
            alternatives=[]
            for number,hz in enumerate((220,660,880)):
                track=folder/f'candidate-{number}.wav'
                subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i',f'sine=frequency={hz}:duration=12',str(track)],check=True,capture_output=True)
                alternatives.append({'id':str(number),'candidate_id':str(number)+':0','name':['Reflektif','Action','Alternatif'][number],
                    'artist':'Offline fixture','start':number,'end':number+6,'score':90-number*10,
                    'reason':'Audio sintetis untuk pengujian UI, bukan hasil provider.', 'path':str(track),'sha256':file_sha256(track)})
            final=folder/'music-mixed.mp4';music=mix_music(dry,{'path':alternatives[0]['path'],'volume':.4,'start_seconds':0,'ducking':False,
                'attribution':{key:alternatives[0][key] for key in ('id','name','artist')}},final)
            music['selection']={'alternatives':alternatives,'review_required':True,'reason':'Offline UI test'}
            api._register_clip(final,{'title':'Uji musik A/B','caption':'Preview musik #keluarga','campaign_id':campaign['id'],
                'campaign_snapshot':campaign,'duration_seconds':6,'music':music,
                'dry_master':{'path':str(dry),'sha256':file_sha256(dry)}})
        api._campaign_ai_source=lambda *_:{'name':'Demo dari brief','audience_scope':'Film keluarga','brief':{'durasi_min':30,'durasi_max':60,'hashtags':['#keluarga'],'cta':'Tonton ceritanya'}}
        allow={'get_account_profiles','get_repliz_accounts','get_stock_clips','get_review_clip','review_clip','preview_distribution',
               'confirm_distribution','get_workflow_jobs','get_publication_tracking','control_publication','save_campaign_workspace',
               'get_campaign_workspace','save_account_profile','extract_campaign_files','get_editing_templates','get_template_preview',
               'preview_clip_music','apply_clip_music','record_music_feedback','record_highlight_feedback'}
        def invoke(name,values):
            if name=='get_repliz_accounts' and options.account_error:return {'status':'error','message':'Provider akun sementara tidak tersedia.'}
            if name in allow:return getattr(api,name)(*values)
            if name=='get_campaigns':return api.cfg['campaigns']
            if name=='log_frontend_error':errors.append(values);return {'status':'ok'}
            if name=='fixture_errors':return errors
            if name=='get_dashboard_stats':return {'totalVideosClipped':1,'storageUsed':'10 KB','activeJobs':[],'recentJobs':[]}
            if name=='get_account_stats':return {'status':'ok','accounts':[],'total':2}
            if name=='get_campaign_stats':return {'account_count':1,'clip_in_stock':1}
            if name=='get_provider_type':return {'provider_type':'custom'}
            if name=='get_app_config':return {'owner_name':'Offline test'}
            if name=='get_system_fonts':return {'status':'ok','fonts':['Arial']}
            if name in ('check_dependencies','check_dependencies_detailed'):return {}
            if name=='get_dependency_install_status':return {'status':'ok','jobs':{}}
            if name.startswith('get_'):return {}
            return {'status':'error','message':'Offline fixture does not execute '+name}
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self,*a,**k):super().__init__(*a,directory=str(project/'web'),**k)
            def log_message(self,*_):pass
            def do_GET(self):
                if self.path.split('?')[0] in ('/','/index.html'):
                    text=(project/'web/index.html').read_text(encoding='utf-8')
                    bridge="""<script>window.pywebview={api:new Proxy({}, {get:(_,name)=>(...args)=>fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,args})}).then(r=>r.json())})};window.addEventListener('load',()=>window.dispatchEvent(new Event('pywebviewready')));</script>"""
                    body=text.replace('<head>','<head>'+bridge).encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
                else:super().do_GET()
            def do_POST(self):
                if self.path!='/api':self.send_error(404);return
                try:
                    request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    response=invoke(request['name'],request.get('args',[]))
                except Exception as exc:response={'status':'error','message':str(exc)}
                body=json.dumps(response).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        server=ThreadingHTTPServer(('127.0.0.1',options.port),Handler)
        try:server.serve_forever()
        finally:
            server.server_close()
            if hasattr(api,'_media_preview'):api._media_preview.close()


if __name__=='__main__':main()

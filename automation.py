#!/usr/bin/env python3
"""Türkçe tarih Shorts üretimi ve zamanlanmış YouTube yüklemesi."""
import argparse, contextlib, ctypes, datetime as dt, fcntl, json, os, sqlite3
import subprocess, sys, tempfile, urllib.request, wave
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly']

class Blocked(RuntimeError): pass

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def run(args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

def probe(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))

def duration(path): return float(probe(path)['format']['duration'])

def validate_video(path):
    data=probe(path)
    video=[s for s in data['streams'] if s['codec_type']=='video']
    audio=[s for s in data['streams'] if s['codec_type']=='audio']
    if not video or not audio or video[0]['width']!=1080 or video[0]['height']!=1920:
        raise Blocked('1080×1920 görüntü ve ses kanalı gerekli.')
    if not 30 <= float(data['format']['duration']) <= 60.1:
        raise Blocked('Video 30–60 saniye aralığında olmalı.')
    run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(path),'-f','null','-'])

def local_voice(text, output):
    import espeakng_loader as loader
    lib=loader.load_library()
    lib.espeak_Initialize.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_char_p,ctypes.c_int]
    sr=lib.espeak_Initialize(2,0,str(Path(loader.get_data_path()).parent).encode(),0)
    if sr<=0 or lib.espeak_SetVoiceByName(b'tr')!=0: raise Blocked('Türkçe yerel ses bulunamadı.')
    lib.espeak_SetParameter(1,150,0)
    chunks=[]
    @ctypes.CFUNCTYPE(ctypes.c_int,ctypes.POINTER(ctypes.c_short),ctypes.c_int,ctypes.c_void_p)
    def callback(ptr,count,events):
        if ptr and count: chunks.append(ctypes.string_at(ptr,count*2))
        return 0
    lib.espeak_SetSynthCallback(callback)
    lib.espeak_Synth.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint,ctypes.c_int,ctypes.c_uint,ctypes.c_uint,ctypes.c_void_p,ctypes.c_void_p]
    buf=ctypes.create_string_buffer(text.encode('utf-8'))
    if lib.espeak_Synth(buf,len(buf),0,1,0,1,None,None)!=0: raise Blocked('Ses oluşturulamadı.')
    with wave.open(str(output),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(sr);f.writeframes(b''.join(chunks))
    lib.espeak_Terminate()

def antalia_voice(text, output, config):
    # Modelin resmi kullanım API'si erişim açılınca doğrulanacak. Remote code çalıştırılmaz.
    command=config.get('antalia_command',[])
    if not command: raise Blocked('Antalia çalıştırma komutu henüz doğrulanıp yapılandırılmadı.')
    text_file=output.with_suffix('.txt');text_file.write_text(text,encoding='utf-8')
    args=[arg.replace('{text_file}',str(text_file)).replace('{output_file}',str(output)) for arg in command]
    run(args)
    if not output.is_file() or duration(output)<0.1: raise Blocked('Antalia geçerli ses üretmedi.')

def wrap(text,font,width):
    lines=[]
    for paragraph in text.split('\n'):
        line=''
        for word in paragraph.split():
            trial=(line+' '+word).strip()
            if font.getlength(trial)>width and line: lines.append(line);line=word
            else: line=trial
        lines.append(line)
    return lines

def card(scene,index,episode,output):
    from PIL import Image, ImageDraw, ImageFont
    im=Image.new('RGB',(1080,1920),'#10202b');d=ImageDraw.Draw(im)
    regular='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    def text(value,y,size,color='#fff6e6',heavy=False,width=920):
        font=ImageFont.truetype(bold if heavy else regular,size)
        lines=wrap(value,font,width)
        for line in lines:
            d.text(((1080-font.getlength(line))/2,y),line,font=font,fill=color)
            y+=int(size*1.4)
        return y
    d.line((80,130,1000,130),fill='#dbb875',width=5)
    text('OSMANLI TARİHİ',190,36,'#dbb875',True)
    text(episode['title'],300,43,'#dbb875',True)
    text(scene['heading'],620,62,heavy=True)
    if text(scene['tr'],960,39)>1330: raise Blocked('Türkçe sahne metni görsele sığmıyor.')
    d.rounded_rectangle((70,1390,1010,1650),radius=25,fill='#09151e')
    if text(scene['en'],1430,34)>1620: raise Blocked('İngilizce altyazı görsele sığmıyor.')
    text('@dolunay-baran',1730,30,'#dbb875')
    text(f'{index+1:02d}',1790,25,'#dbb875')
    im.save(output)

def srt_time(seconds):
    ms=round(seconds*1000)
    h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'

def render(episode,config,state,preview=False):
    folder=state/'renders'/episode['id']/('preview' if preview else 'antalia')
    folder.mkdir(parents=True,exist_ok=True)
    if not preview and not config.get('antalia_command'): raise Blocked('Antalia entegrasyonu henüz tamamlanmadı.')
    scenes=episode['scenes'];lengths=[]
    if not scenes: raise Blocked('Sahne listesi boş.')
    for i,scene in enumerate(scenes):
        voice=folder/f'{i}.wav'
        if preview: local_voice(scene['tr'],voice)
        else: antalia_voice(scene['tr'],voice,config)
        seconds=max(5.,duration(voice)+0.4);lengths.append(seconds)
    total=sum(lengths)
    if not 30<=total<=60: raise Blocked(f'Ses toplam süresi {total:.1f}s; metni 30–60 saniyeye göre düzenleyin.')
    subtitles=[];offset=0
    for i,(scene,seconds) in enumerate(zip(scenes,lengths)):
        image=folder/f'{i}.png';card(scene,i,episode,image)
        frames=round(seconds*30);seconds=frames/30
        subtitles.append(f'{i+1}\n{srt_time(offset)} --> {srt_time(offset+seconds)}\n{scene["en"]}')
        offset+=seconds
        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(image),'-i',str(folder/f'{i}.wav'),
             '-vf',f"zoompan=z='min(zoom+0.00012,1.03)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={frames}:s=1080x1920:fps=30",
             '-af','loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,apad','-t',str(seconds),
             '-c:v','libx264','-preset','fast','-crf','23','-threads','2','-pix_fmt','yuv420p',
             '-c:a','aac','-b:a','160k',str(folder/f'{i}.mp4')])
    (folder/'concat.txt').write_text(''.join(f"file '{i}.mp4'\n" for i in range(len(scenes))))
    video=folder/'video.mp4'
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(folder/'concat.txt'),'-c','copy','-movflags','+faststart',str(video)])
    (folder/'english.srt').write_text('\n\n'.join(subtitles)+'\n',encoding='utf-8')
    validate_video(video)
    return video

def state_path(config):
    return Path(config.get('state_dir') or ROOT/'.state').expanduser().resolve()

@contextlib.contextmanager
def locked(state):
    state.mkdir(parents=True,exist_ok=True)
    with (state/'worker.lock').open('a') as f:
        try: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise Blocked('Başka bir üretim/yükleme işlemi çalışıyor.')
        yield

def database(state):
    db=sqlite3.connect(state/'jobs.sqlite3')
    db.execute('CREATE TABLE IF NOT EXISTS jobs(slot TEXT PRIMARY KEY, episode TEXT UNIQUE, status TEXT NOT NULL, video_id TEXT)')
    return db

def reserve(db,slot,episodes):
    if db.execute("SELECT 1 FROM jobs WHERE status IN ('uploading','uncertain')").fetchone():
        raise Blocked('Önceki yüklemenin sonucu belirsiz; tekrar yüklemeyi önlemek için işlem durdu.')
    row=db.execute('SELECT episode,status FROM jobs WHERE slot=?',(slot,)).fetchone()
    if row:
        if row[1]=='uploaded': return None
        if row[1] in ('reserved','failed'):
            db.execute("UPDATE jobs SET status='reserved' WHERE slot=?",(slot,));db.commit()
            return next(e for e in episodes if e['id']==row[0])
    if db.execute("SELECT count(*) FROM jobs WHERE slot LIKE ? AND status!='failed'",(slot[:10]+'%',)).fetchone()[0]>=2:
        raise Blocked('Bugünün iki video sınırına ulaşıldı.')
    db.execute("UPDATE jobs SET status='failed' WHERE status='reserved'")
    used={r[0] for r in db.execute("SELECT episode FROM jobs WHERE status!='failed'")}
    episode=next((e for e in episodes if e['id'] not in used),None)
    if not episode: raise Blocked('İçerik kuyruğu tükendi; yeni bölümler eklenmeli.')
    db.execute("DELETE FROM jobs WHERE episode=? AND status='failed'",(episode['id'],))
    db.execute("INSERT INTO jobs VALUES(?,?,'reserved',NULL)",(slot,episode['id']));db.commit()
    return episode

def slot_now(config,now=None):
    now=now or dt.datetime.now(ZoneInfo(config.get('timezone','Europe/Istanbul')))
    for value in config.get('times',['12:00','19:00']):
        hour,minute=map(int,value.split(':'));due=now.replace(hour=hour,minute=minute,second=0,microsecond=0)
        if 0<=(now-due).total_seconds()<600: return f'{now.date()}T{value}'
    raise Blocked('Şu an yayın saati değil. Varsayılan saatler: Türkiye 12.00 ve 19.00.')

def youtube(config):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    path=state_path(config)/'token.json'
    if not path.exists(): raise Blocked('YouTube bağlantısı yok; kendi bilgisayarınızda authorize komutunu çalıştırın.')
    creds=Credentials.from_authorized_user_file(str(path),SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request());secure_write(path,creds.to_json())
    if not creds.valid: raise Blocked('Google izni eksik veya süresi dolmuş.')
    return build('youtube','v3',credentials=creds,cache_discovery=False)

def secure_write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(dir=path.parent,prefix='.secret-')
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w') as f:f.write(text)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def check_channel(client,config):
    channels=client.channels().list(part='id,snippet',mine=True).execute().get('items',[])
    handle=config.get('expected_handle','@dolunay-baran').casefold()
    match=[x for x in channels if x['snippet'].get('customUrl','').casefold()==handle]
    if len(match)!=1: raise Blocked('Google ile seçilen kanal @dolunay-baran ile eşleşmiyor.')
    return match[0]['id']

def authorize(config,secret_file):
    from google_auth_oauthlib.flow import InstalledAppFlow
    state=state_path(config)
    with locked(state):
        creds=InstalledAppFlow.from_client_secrets_file(secret_file,SCOPES).run_local_server(port=0,access_type='offline',prompt='consent')
        from googleapiclient.discovery import build
        client=build('youtube','v3',credentials=creds,cache_discovery=False)
        channel=check_channel(client,config)
        secure_write(state/'token.json',creds.to_json())
        print('Kanal doğrulandı; izin dosyası güvenli yerel konuma kaydedildi. Kanal ID:',channel)

def upload(client,episode,video,config):
    from googleapiclient.http import MediaFileUpload
    request=client.videos().insert(part='snippet,status',body={
        'snippet':{'title':episode['title'],'description':episode['description'],
                   'tags':['Osmanlı tarihi',episode['id']],'categoryId':'27',
                   'defaultLanguage':'tr','defaultAudioLanguage':'tr'},
        'status':{'privacyStatus':config.get('privacy','public'),'selfDeclaredMadeForKids':False}},
        media_body=MediaFileUpload(str(video),mimetype='video/mp4',resumable=True,chunksize=8*1024*1024))
    response=None
    while response is None:
        _,response=request.next_chunk(num_retries=0)
    if not response.get('id'): raise Blocked('Yükleme yanıtında video ID yok.')
    return response['id']

def persist_state(config):
    command=config.get('persist_command',[])
    if command: run(command)

def publish(config,episodes,slot):
    if not config.get('antalia_command'): raise Blocked('Antalia doğrulanmadı; robotik önizleme otomatik yayımlanmaz.')
    state=state_path(config)
    with locked(state), database(state) as db:
        client=youtube(config);check_channel(client,config)
        episode=reserve(db,slot,episodes)
        if episode is None:print('Bu yayın aralığı zaten tamamlandı.');return
        try: video=render(episode,config,state)
        except BaseException:
            db.execute("UPDATE jobs SET status='failed' WHERE slot=?",(slot,));db.commit();raise
        db.execute("UPDATE jobs SET status='uploading' WHERE slot=?",(slot,));db.commit()
        # Uzak kayıt kalıcılaşmadan YouTube isteği gönderilmez.
        persist_state(config)
        try: video_id=upload(client,episode,video,config)
        except BaseException:
            db.execute("UPDATE jobs SET status='uncertain' WHERE slot=?",(slot,));db.commit()
            persist_state(config)
            raise
        db.execute("UPDATE jobs SET status='uploaded',video_id=? WHERE slot=?",(video_id,slot));db.commit()
        persist_state(config)
        print('Yükleme tamamlandı:',f'https://www.youtube.com/watch?v={video_id}')

def audit_model(state):
    state.mkdir(parents=True,exist_ok=True)
    for name,url in [('metadata.json','https://huggingface.co/api/models/cloud0day3/antalia-mini'),
                     ('README.md','https://huggingface.co/cloud0day3/antalia-mini/raw/main/README.md')]:
        with urllib.request.urlopen(url,timeout=30) as response:
            (state/name).write_bytes(response.read())
    data=load(state/'metadata.json')
    print('Model revision:',data.get('sha'))
    print('License metadata:',data.get('cardData',{}).get('license','not specified'))
    print('Model belgeleri indirildi. Lisansı ve resmi kullanım kodunu inceleyin; dosyalar otomatik çalıştırılmaz.')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',default=str(ROOT/'config.json'))
    sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('audit-model')
    sub.add_parser('doctor')
    p=sub.add_parser('authorize');p.add_argument('--client-secrets',required=True)
    p=sub.add_parser('render');p.add_argument('--episode',required=True);p.add_argument('--local-preview',action='store_true')
    p=sub.add_parser('run');p.add_argument('--scheduled-time',choices=['12:00','19:00'])
    sub.add_parser('status')
    args=parser.parse_args();config=load(args.config);state=state_path(config)
    queue_path=Path(config.get('queue','content/episodes.json'))
    episodes=load(queue_path if queue_path.is_absolute() else ROOT/queue_path)
    ids=[e['id'] for e in episodes]
    if len(ids)!=len(set(ids)):raise Blocked('Bölüm ID değerleri benzersiz olmalı.')
    if any(not x.replace('-','').isalnum() for x in ids):raise Blocked('Bölüm ID yalnızca harf, rakam ve tire içermeli.')
    if args.action=='audit-model':audit_model(state/'model-audit')
    elif args.action=='authorize':authorize(config,args.client_secrets)
    elif args.action=='render':
        episode=next((e for e in episodes if e['id']==args.episode),None)
        if episode is None:raise Blocked('Bölüm bulunamadı.')
        with locked(state):print(render(episode,config,state,args.local_preview))
    elif args.action=='run':
        if args.scheduled_time:
            now=dt.datetime.now(ZoneInfo(config.get('timezone','Europe/Istanbul')))
            hour,minute=map(int,args.scheduled_time.split(':'))
            due=now.replace(hour=hour,minute=minute,second=0,microsecond=0)
            if not 0<=(now-due).total_seconds()<6*3600:raise Blocked('Zamanlanmış iş altı saatlik çalışma aralığının dışında.')
            slot=f'{now.date()}T{args.scheduled_time}'
        else:slot=slot_now(config)
        publish(config,episodes,slot)
    elif args.action=='status':
        state.mkdir(parents=True,exist_ok=True)
        with database(state) as db:
            for row in db.execute('SELECT slot,episode,status,video_id FROM jobs ORDER BY slot'):print(*row)
    elif args.action=='doctor':
        import shutil
        print('FFmpeg:',bool(shutil.which('ffmpeg')),'FFprobe:',bool(shutil.which('ffprobe')))
        print('Antalia adapter configured:',bool(config.get('antalia_command')))
        print('YouTube authorized:',(state/'token.json').exists())
        print('Queued episodes:',len(episodes),'Timezone:',config.get('timezone'))
        print('GitHub Actions schedule prepared; local systemd is optional. Neither scheduler has been activated.')

if __name__=='__main__':
    try: main()
    except Blocked as e:print('DURDU:',str(e),file=sys.stderr);sys.exit(2)
    except Exception as e:
        # Google istisnalarında token/istek içeriklerini günlüklerden uzak tut.
        print('İşlem başarısız:',type(e).__name__,'. Ayrıntılar gizli veri içerebileceği için yazdırılmadı.',file=sys.stderr);sys.exit(1)

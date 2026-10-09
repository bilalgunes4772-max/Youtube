# Dolunay Baran — Türkçe tarih Shorts otomasyonu

Türkçe ses → 1080×1920 hareketli metin görselleri → İngilizce altyazı → YouTube yüklemesi. Türkiye saatiyle günde iki çalışma: **12.00 ve 19.00**. Otomasyon geliştirilmiştir; Antalia ve YouTube entegrasyonlarının canlı doğrulaması henüz tamamlanmamıştır. GitHub Actions zamanlayıcısı hazırlandı; otomatik YouTube yayını henüz etkin değildir. main dalına kod push edilmesi önizleme üretimini tetikler, YouTube yüklemesi yapmaz. Kendi bilgisayarınız veya VPS şart değildir.

## Mevcut durum

- Gerçek yerel Türkçe sesli video üretimi `--local-preview` ile sınanabilir. Bu ses eSpeak NG'dir; Antalia değildir. Önizleme otomatik yayımlanmaz.
- Antalia Mini: https://huggingface.co/cloud0day3/antalia-mini . Ağ erişimi engelli olduğundan lisansı, model dosyaları, CPU/GPU ihtiyacı ve resmi kullanım API'si incelenemedi. Ücretsiz erişim ticari kullanım izni anlamına gelmez. `antalia_command` bilinçli olarak boştur; gerçek entegrasyon tamamlanana kadar üretim yüklemesi durur.
- Başlangıç kuyruğunda iki bölüm var: Osmanlı'nın doğuşu ve 1302 Bafeus Savaşı. Bu, bir günlük içeriktir. Sonsuz günlük içerik üreticisi veya yeni tarih metinleri yazan dil modeli henüz yoktur. Kuyruk bittiğinde durur; eski videoları tekrar yüklemez.
- Tarih kaynakları mevcut ağda okunamadı. `source_checked` alanı false'tur. Kaynak denetimini tamamlamadan kamuya yayın yapmayın.
- Robotik önizleme, metin kartları ve otomatik üretim tek başına izlenme veya para kazanma garantisi sağlamaz. Henüz Antalia ile üretilmiş bir video veya YouTube'a gerçek yükleme yoktur.

## Bilgisayar/VPS olmadan: GitHub Actions

`.github/workflows/daily-shorts.yml` günlük 09.00 ve 16.00 UTC çalıştırmaları tanımlar; Türkiye'de 12.00 ve 19.00 olur. Zamanlanmış işler GitHub'ın varsayılan dalındaki workflow'u kullanır. `AUTOMATION_ENABLED` repository variable değeri `true` yapılana kadar otomatik yükleme çalışmaz. GitHub işleri gecikebilir; kesin dakika garantisi yoktur. Ücretsiz kullanım kotası depo türüne ve hesabınıza bağlıdır; sınırsız ücretsiz çalışma varsayılmamıştır. Uzun süre etkinlik olmayan herkese açık depolarda schedule devre dışı kalabilir.

GitHub Actions standart çalıştırıcısı CPU kullanır. Antalia'nın GPU/RAM gereksinimleri doğrulanmadan bu modelin orada çalışacağı söylenemez. Gerekirse desteklenen bir GPU çalıştırıcı veya dış ses üretim servisi gerekir; henüz seçilmedi.

1. Kodları GitHub deposunun varsayılan dalına yerleştirin.
2. Actions → Daily Turkish history Shorts → Run workflow → `audit-model` ile resmi model belgelerini indirin. Çalışma tamamlanınca **Artifacts** alanından belgeleri indirebilirsiniz. Bu, model ses üretimini doğrulamaz.
3. Antalia lisansını ve kullanımını inceleyip gerçek `antalia_command` ve gereken bağımlılıkları yapılandırın.
4. Google OAuth bağlantısıyla üretilen token JSON'unu **Settings → Secrets and variables → Actions → Secrets** içinde `YOUTUBE_OAUTH_JSON` adıyla kaydedin. JSON içeriğini sohbete göndermeyin. Refresh token kalıcı OAuth izni gerektirir.
5. main dalına kod push edilmesi veya Actions üzerinden `preview` çalışması sentetik yerel Türkçe sesli MP4 üretir. **Artifacts → shorts-output-...** ZIP dosyasını indirip MP4'ü açabilirsiniz. Bu sohbetten açılamayan dosyalar için teslim yolu budur; workflow GitHub'a yerleştirilip çalıştırılmadan gerçek indirme bağlantısı oluşmaz.
6. Antalia üretimi, kanal izni, kaynaklar ve gerçek yükleme doğrulandıktan sonra **Variables** alanında `AUTOMATION_ENABLED=true` ayarlayın.

`runtime/jobs.sqlite3` yalnızca bölüm ID, yayın aralığı, durum ve video ID içerir. Token, video veya kişisel hesap bilgisi bu kayda yazılmaz. GitHub çalıştırıcısı bu kaydı her yükleme isteğinden **önce** depoya commit/push eder; bu işlem başarısızsa YouTube'a istek göndermez. Upload tamamlandıktan sonra kayıt tekrar güncellenir. Workflow için `contents: write` gerekir; branch koruması bot push'larını engelliyorsa kalıcılık adımı durur. Aynı anda iki workflow çalışmaz. Secrets ve tokenlar artifact veya Git'e eklenmez. Kayıt dosyasını silmek tekrar yükleme riskini doğurur.

## İsteğe bağlı: kalıcı Linux makineye kurulum

Her gün çalışacak, açık kalan bir Linux bilgisayar veya sunucu gerekir. Bu sohbetin çalışma ortamı kalıcı zamanlayıcı değildir. RAM/GPU satın almadan önce Antalia gereksinimlerini doğrulayın.

Depoyu `~/youtube-automation` altına yerleştirin. Mevcut checkout kullanın; kullanıcı istemedikçe Git worktree oluşturmayın. Gereksinimler: Python 3.11+, FFmpeg/FFprobe, DejaVu Sans yazı tipleri, systemd kullanıcı oturumu.

```sh
cd ~/youtube-automation
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp -n config.example.json config.json
.venv/bin/python automation.py doctor
.venv/bin/python -m unittest discover -s tests -v
```

## Antalia entegrasyonu: henüz çözülmemiş adım

```sh
.venv/bin/python automation.py audit-model
```

Bu komut resmi model metadatasını ve README'yi `.state/model-audit` altına indirir; model kodunu çalıştırmaz. Model kartı ve lisans okunduktan sonra resmi çalıştırma API'sine uygun gerçek adaptör yazılmalıdır. `antalia_command` bir argv dizisidir. `{text_file}` UTF-8 Türkçe metin dosyasını, `{output_file}` üretilmesi gereken ses dosyasını temsil eder. Shell çalıştırılmaz. Örnek bir Antalia API'si uydurulmamıştır; alan şu anda çalışır bir entegrasyon değildir.

## Yerel sesli önizleme

```sh
.venv/bin/python automation.py render --episode osmanli-001 --local-preview
```

MP4 ve İngilizce SRT `.state/renders/osmanli-001/preview` altında oluşturulur. Bunları makinenizde VLC ile açabilirsiniz. Bu sohbetin dosya bağlantıları kullanıcı tarafından indirilemedi; yerel dosya varlığını gerçek dosya teslimi olarak değerlendirmeyin.

## YouTube hesabını bir kez bağlama

1. Google Cloud Console'da proje oluşturun ve **YouTube Data API v3** hizmetini etkinleştirin.
2. Google Auth Platform'da izin ekranını yapılandırın. Test modundaysa kanal sahibi Google hesabını test kullanıcısı olarak ekleyin.
3. **Desktop app** türünde OAuth istemcisi oluşturup JSON'u kendi bilgisayarınıza indirin. Şifre, JSON içeriği veya tokenları sohbete göndermeyin.
4. Kendi bilgisayarınızda (tarayıcı ve callback aynı makinede):

```sh
.venv/bin/python automation.py authorize --client-secrets /guvenli/konum/client_secret.json
```

Google'ın izin ekranında `@dolunay-baran` kanalını seçin. Kod kanalın handle değerini kontrol eder, yanlış kanala izin vermez. Upload ve salt okunur kanal izinleri kullanılır. Refresh token, `.state/token.json` dosyasında 0600 izinleriyle saklanır ve Git'ten dışlanır. Sunucuda çalışacaksa bu dosyayı güvenli şekilde aynı uygulamanın `.state` dizinine taşıyın; sohbet veya Git kullanmayın. OAuth uygulaması test modundayken refresh token kısa süreli olabilir; sürekli otomasyon için uygulamanın yayın durumunu ve Google kurallarını kontrol edin. Servis hesabı kişisel YouTube kanalının OAuth izninin yerine geçmez.

### Sürekli açık bilgisayar olmadan ilk Google izni

İlk izin işlemi için sürekli açık bilgisayar gerekmez. Masaüstü authorize komutunu bir kez güvenilir bir bilgisayarda çalıştırabilirsiniz. Yalnızca tarayıcı kullanacaksanız Google'ın resmi [OAuth Playground](https://developers.google.com/oauthplayground/) aracı alternatifidir: kendi OAuth istemcinizi kullanmanız gerekir; Playground'un varsayılan istemcisi sürekli otomasyon için uygun değildir.

Google Cloud'da **Web application** OAuth istemcisi için izin verilen redirect URI `https://developers.google.com/oauthplayground` olmalıdır. Playground ayarlarında **Use your own OAuth credentials** seçilir, kendi istemci bilgileri yalnızca bu Google sayfasına girilir. `https://www.googleapis.com/auth/youtube.upload` ve `https://www.googleapis.com/auth/youtube.readonly` kapsamlarına kanal sahibi izin verir; kod tokenlarla değiştirilir. İlgili Google ekranından alınan refresh token, client ID ve client secret sadece GitHub Actions Secret'a aşağıdaki authorized-user JSON yapısında kaydedilir. Buradaki büyük harfli yer tutucular gerçek değer değildir; sohbete değer göndermeyin.

```json
{
  "type": "authorized_user",
  "client_id": "KENDI_OAUTH_CLIENT_ID",
  "client_secret": "KENDI_OAUTH_CLIENT_SECRET",
  "refresh_token": "GOOGLE_IZNINDEN_ALINAN_REFRESH_TOKEN",
  "token_uri": "https://oauth2.googleapis.com/token",
  "scopes": [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
  ]
}
```

Bu yöntem burada denenmedi; Google projesi ve kanal sahibi izni henüz mevcut değil. Üretim kodu ayrıca kanal handle değerini kontrol eder. Google hesap şifresini, tokenları veya OAuth istemci sırrını bu sohbete göndermeyin.

API projesinin doğrulama/audit durumuna göre yüklemeler private ile sınırlanabilir; `privacy: public` ayarı tek başına herkese açık yayın garantisi değildir. Quota veya token sorununda işlem durur; hatayı bastırarak yayımlandı denmez.

## Zamanlayıcı

Antalia, kanal izni ve içerikler doğrulandıktan sonra, `~/youtube-automation` kurulumu için:

```sh
mkdir -p ~/.config/systemd/user
cp deploy/youtube-shorts.service deploy/youtube-shorts.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now youtube-shorts.timer
systemctl --user list-timers youtube-shorts.timer
```

Sunucuda kullanıcının oturumdan çıkınca da çalışması için yönetici, gerektiğinde `loginctl enable-linger KULLANICI_ADI` yapılandırmalıdır. Bu işlem bu oturumda uygulanmadı. Makine kapalıyken kaçırılan saatler topluca yayımlanmaz. Sistem bir saatte başlatılmışsa yalnızca o saatten sonraki on dakika içinde çalışır. Saatleri değiştirirken hem JSON hem timer dosyasını güncelleyin.

```sh
journalctl --user -u youtube-shorts.service
.venv/bin/python automation.py status
systemctl --user disable --now youtube-shorts.timer
```

## Tekrar yüklememe ve hata davranışı

Dosya kilidi eşzamanlı çalışan işleri engeller. SQLite aynı bölüm ve yayın aralığını tekrar kullanmaz; gün başına en fazla iki kayıt oluşturur. Ses/render hatasında YouTube çağrılmaz. Yükleme başladıktan sonra ağ kesilmesi veya makine çökmesi durumunda durum `uncertain`/`uploading` olur ve sonraki işler durur. Bu, YouTube'da var olan videoyu yanlışlıkla tekrar yüklemeyi engeller; API'de tam bir exactly-once garantisi yoktur. Böyle bir durumda YouTube Studio ve iş kaydı incelenip sonucu çözmek gerekir. Otomatik tekrar yükleme yapılmaz.

## Ağ gereksinimleri

Hugging Face model kartı için `huggingface.co`; Google OAuth ve YouTube API için `accounts.google.com`, `oauth2.googleapis.com`, `www.googleapis.com` gerekir. Model indirmelerinde karşılaşılan CDN/Xet alan adları ayrıca teşhis edilmeli; şu an doğrulanmadı. Mevcut ortam ayarları taslağına bu alanlar eklendi; taslağı kaydetmek çalışma ortamında erişim veya yayın başarısı kanıtı değildir.

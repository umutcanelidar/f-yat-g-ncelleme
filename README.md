# IdeaSoft Fiyat Karşılaştırma Paneli

Bu uygulama, IdeaSoft e-ticaret paneli ile yerel fiyat listelerini karşılaştırarak fiyat güncellemelerini otomatize eder.

## Özellikler
- **Fiyat Karşılaştırma**: IdeaSoft Excel çıktısı ile tedarikçi listesini karşılaştırır.
- **Otomatik Güncelleme**: Selenium tabanlı bot ile IdeaSoft panelinde fiyatları günceller.
- **2FA Desteği**: Manuel giriş desteği ile güvenli oturum yönetimi.
- **Akıllı Arayüz**: Flask tabanlı kullanıcı dostu kontrol paneli.

## Kurulum
1. Gerekli kütüphaneleri yükleyin:
   ```bash
   pip install -r requirements.txt
   ```
2. Uygulamayı başlatın:
   ```bash
   ./start.command
   ```

## Kullanım
- `http://localhost:5050` adresinden panele erişin.
- IdeaSoft ayarlarından giriş yapın.
- Dosyaları yükleyip karşılaştırın ve güncellemeyi başlatın.




__________________________________n11r Extender (Resolve Handle Script) | macOS________________________________________________________

Bu script, DaVinci Resolve içindeki post süreçlerini otomatikleştirmek amacıyla timeline'daki sarı renkteki ve seçilmiş kliplere otomatik 
25 kare handle (eğer 25 kare pay yoksa maksimum kare sayısı kadar) ekler ve klipleri yeni bir timeline'a ekler.


I. Kurulum (macOS)
Scriptin Resolve menüsünde görünmesi için Terminal üzerinden sembolik link oluşturulması gerekmektedir. Bu işlem sadece bir defa yapılır.
Kurulum Adımları
1. Dosyayı Yerleştirme n11r_handle.py dosyasını, kalıcı ve erişilebilir bir konuma kaydedin.
2. Terminal İşlemleri Terminal uygulamasını (⌘ + Boşluk ile aratın) açın ve aşağıdaki komutları sırasıyla çalıştırın.
DİKKAT: İlk komutta tırnak işaretleri içindeki dosya yolunu ("/Kendi/Kaydettiğin/Dosya/Yolu/n11r_handle.py") mutlaka kendi dosyanızın 
tam yolu ile değiştirin.

 /Users/NehirMacMini/Projects/handle/n11r_handle.py

# 1) Resolve'un Script klasörünü oluşturur
mkdir -p "$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit"

# 2) Scripti Resolve menüsüne bağlar (Sembolik Link)
# LÜTFEN DOSYA YOLUNU GÜNCELLEYİN!
ln -sf "/Users/Dosya/Yolu/n11r_handle.py" \
"$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit/n11r_Extender.py"

Bu işlemin ardından script, Resolve menüsünde "n11r Extender" adıyla görünecektir.


II. Kullanım Talimatları

1. Resolve Yenileme
Kurulum sonrası Resolve'da Workspace → Scripts → Reload Scripts komutunu çalıştırın veya uygulamayı yeniden başlatın.

2. Çalıştırma
	1	Edit Page (Kurgu Sayfası)'na geçiş yapın.
	2	Handle eklenecek klipleri seçin.
	3	Scripti, Workspace → Scripts → Edit → n11r Extender yolundan çalıştırın.
3. Raporlama
İşlem tamamlandığında, Console veya Log penceresinde hangi kliplere handle eklendiği ve kliplerin yer değiştirdiği raporlanır.

Bilinen Kısıtlamalar
DaVinci Resolve API'sinin mevcut kısıtlamaları nedeniyle, Retime (Hız Değiştirme) veya Reverse (Ters Çevirme) özelliği uygulanan 
kliplerin kare verileri doğru okunamamaktadır.
Bu nedenle, zamanlaması değiştirilmiş klipler script tarafından ATLANDI olarak raporlanır. Bu kliplere handle eklemek için, 
ilgili efektlerin geçici olarak kaldırılması, script çalıştırılması ve ardından efektlerin tekrar uygulanması gerekmektedir.

ÖNEMLİ NOT: Bu script Resolve Stduio sürümleri için yapılmıştır.
Script ile ilgili geri bildirimleriniz, yaşadığınız sorunlar veya yeni özellik talepleriniz için bana ulaşabilirsiniz.


# Türkiye EPDK şarj istasyonları

`stations.json`: EPDK'nın Serbest Erişim Platformu'nda yayımladığı halka açık şarj istasyonları
(Şarj Hizmeti Yönetmeliği Md. 17/2, 30/1), Şarj Haritası uygulamasının okuduğu biçimde.

- Kaynak: `https://apigateway.epdk.gov.tr/sarjIstasyonlari`, günde bir istek (`.github/workflows/refresh-stations.yml`).
- Üretim: `python3 scripts/build_stations.py` (yalnız standart kütüphane). Kontrol: `cd scripts && python3 test_build_stations.py`.
- Konumu olmayan ya da Türkiye dışına düşen kayıtlar alınmaz; bozuk görünen bir çekim yayımlanmaz.

`EPDK_Tum_Sarj_Istasyonlari.csv`, uygulamanın eski sürümleri için tutuluyor.

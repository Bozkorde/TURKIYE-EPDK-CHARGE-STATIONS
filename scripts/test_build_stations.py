"""Checks the feed-to-Station mapping, the only logic in build_stations.py that can quietly go wrong."""
from build_stations import display_brand, station

record = {
    "sarjIstasyonuNo": "ŞRJ/1", "sarjIstasyonuAdi": "Zorlu Center", "marka": "Zes",
    "adres": "Levazım Mah. / Beşiktaş / İSTANBUL", "enlem": "41.066826", "boylam": 29.018465,
    "soketler": [
        {"soketTipi": "AC", "soketTuru": "AC_TYPE2", "soketGucu": "22"},
        {"soketTipi": "DC", "soketTuru": "DC_CCS", "soketGucu": "120"},
        {"soketTipi": "DC", "soketTuru": "DC_CCS", "soketGucu": "180.0"},
        {"soketTipi": "DC", "soketTuru": "DC_CHADEMO", "soketGucu": "50"},
    ],
}

s = station(record)
assert (s["acAdet"], s["acGuc"]) == (1, 22), s
assert (s["dcAdet"], s["dcGuc"]) == (2, 180), s              # CHAdeMO is counted on its own, not as DC
assert (s["chademoAdet"], s["chademoGuc"]) == (1, 50), s
assert s["id"] == s["istasyonKodu"] == "ŞRJ/1" and s["lat"] == 41.066826 and s["hasExplicitAddress"]

assert station({**record, "enlem": "0", "boylam": "0"}) is None   # placeholder coordinates
assert station({**record, "enlem": ""}) is None                   # missing coordinates
assert station({**record, "sarjIstasyonuNo": " "}) is None        # no code to key on

bare = station({**record, "soketler": [], "sarjIstasyonuAdi": "", "adres": " "})
assert bare["acAdet"] is None and bare["dcGuc"] is None             # unknown, not "0 kW"
assert bare["officialName"] == "Zes Şarj Noktası" and not bare["hasExplicitAddress"]

unknown_power = station({**record, "soketler": [{"soketTipi": "AC", "soketTuru": "AC_TYPE2", "soketGucu": None}]})
assert unknown_power["acAdet"] == 1 and unknown_power["acGuc"] is None
for raw, shown in [("zes", "Zes"), ("eşarj", "Eşarj"), ("ispark", "İspark"), ("5 şarj", "5 Şarj"),
                   ("  wat   mobilite ", "Wat Mobilite"), ("VOLTRUN", "VOLTRUN"), ("EN YAKIT", "EN YAKIT"),
                   ("CHARGING VEHICLES CV", "CHARGING VEHICLES CV"), ("K-ŞARJ", "K-ŞARJ"),
                   ("ZEPLİN CAR rental", "ZEPLİN CAR Rental"), ("otoWATT", "otoWATT"), ("D-Charge", "D-Charge")]:
    assert display_brand(raw) == shown, (raw, display_brand(raw), shown)
assert station({**record, "marka": "zes"})["marka"] == "Zes"
print("OK")

# Test tłumaczenia napisów:  python narzedzia\test_tlumacz.py

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "addon", "appModules"))
from _slownik_pl import SLOWNIK  # noqa: E402
from _tlumacz import zbudujTlumacza  # noqa: E402

tr = zbudujTlumacza({"Cancel": "Anuluj", "%1 videos found": "Znalezione filmy: %1",
	"%1/%2 episodes": "Odcinki: %1 z %2", "%1 / %2": "%1 z %2", "Copy %1 to %1": "Kopiuj %1"})
assert tr("Cancel") == "Anuluj"
assert tr("  Cancel \n") == "Anuluj", "spacje i nowe wiersze nie przeszkadzają"
assert tr("Unknown") == "Unknown", "nieznany napis bez zmian"
assert tr("") == "" and tr(None) is None
assert tr("12 videos found") == "Znalezione filmy: 12"
assert tr("3/10 episodes") == "Odcinki: 3 z 10"
assert tr("3 / 10") == "3 / 10", "wzorzec bez słów jest pomijany"
assert tr("Copy a to a") == "Kopiuj a" and tr("Copy a to b") == "Copy a to b", "powtórzony %1 musi być taki sam"

# Prawdziwy słownik: każdy wzorzec da się zbudować, a %N z klucza jest w tłumaczeniu.
full = zbudujTlumacza(SLOWNIK)
assert full("All Download History") != "All Download History"
for en, pl in SLOWNIK.items():
	for n in "123456789":
		assert ("%" + n in en) <= ("%" + n in pl), en
print("OK, wpisów w słowniku: %d" % len(SLOWNIK))

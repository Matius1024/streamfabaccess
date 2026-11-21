# Pokazuje napisy StreamFab, których brakuje w polskim tłumaczeniu programu i w słowniku dodatku.
# Użycie po aktualizacji StreamFab:  python narzedzia\brakujace_napisy.py
# Nowe napisy trzeba przetłumaczyć i dopisać do addon\appModules\_slownik_pl.py.

import glob
import html
import os
import re
import struct
import sys

QLANG = r"C:\Program Files\StreamFab\StreamFab\QLanguage"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "addon", "appModules"))
from _slownik_pl import SLOWNIK  # noqa: E402
from _tlumacz import zbudujTlumacza  # noqa: E402

QM_MAGIC = bytes.fromhex("3cb86418caef9c95cd211cbf60a1bddd")


def parseQm(path):
	"""Lista (kontekst, tekst angielski, tłumaczenie) z pliku .qm Qt."""
	data = open(path, "rb").read()
	if data[:16] != QM_MAGIC:
		raise ValueError("to nie jest plik .qm: " + path)
	pos, msgs = 16, b""
	while pos < len(data):
		tag, size = data[pos], struct.unpack(">I", data[pos + 1:pos + 5])[0]
		if tag == 0x69:
			msgs = data[pos + 5:pos + 5 + size]
		pos += 5 + size
	out, cur, i = [], {}, 0
	while i < len(msgs):
		tag = msgs[i]
		i += 1
		if tag == 1:  # koniec wpisu
			out.append((cur.get(7), cur.get(6), cur.get(3)))
			cur = {}
		elif tag in (3, 6, 7, 8):
			size = struct.unpack(">I", msgs[i:i + 4])[0]
			i += 4
			if size == 0xFFFFFFFF:
				continue
			raw = msgs[i:i + size]
			i += size
			cur.setdefault(tag, raw.decode("utf-16-be" if tag == 3 else "utf-8", "replace"))
		elif tag in (2, 5):
			i += 4
		else:
			raise ValueError("nieznany znacznik %d w %s" % (tag, path))
	return out


def plain(text):
	text = re.sub(r"(?is)<style.*?</style>", "", text)
	return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", text))).strip()


def main():
	tr = zbudujTlumacza(SLOWNIK)
	missing = set()
	for base in ("Downloader", "uibase", "ReportQt"):
		pol = {src for ctx, src, t in parseQm(os.path.join(QLANG, base + "_POL.qm")) if src and t}
		for path in glob.glob(os.path.join(QLANG, base + "_*.qm")):
			for ctx, src, t in parseQm(path):
				if not src or src in pol:
					continue
				text = plain(src)
				# Pomijamy nazwy techniczne obiektów Qt (np. AIGeneratorWnd, episode.name) i teksty bez słów.
				if not re.search(r"[A-Za-z]{2}", text) or re.fullmatch(r"[A-Za-z0-9_.]*([a-z][A-Z]|[._])[A-Za-z0-9_.]*", text):
					continue
				if tr(text) == text:
					missing.add(text)
	for text in sorted(missing, key=str.lower):
		print(text)
	print("Brakujących napisów: %d" % len(missing), file=sys.stderr)


if __name__ == "__main__":
	main()

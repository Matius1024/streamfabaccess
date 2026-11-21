# Tłumaczenie angielskich napisów StreamFab na polski (bez zależności od NVDA, więc da się to testować osobno).

import re

_WS = re.compile(r"\s+")
_PLACEHOLDER = re.compile(r"%(\d)")


def _key(text):
	return _WS.sub(" ", text).strip()


def zbudujTlumacza(*slowniki):
	"""Zwraca funkcję tr(tekst): dokładne napisy ze słowników i wzorce dla napisów z %1, %2 (np. „%1 videos found”).

	Późniejszy słownik wygrywa z wcześniejszym. Nieznany napis wraca bez zmian.
	"""
	exact, patterns = {}, {}
	for slownik in slowniki:
		for en, pl in slownik.items():
			key = _key(en)
			if not _PLACEHOLDER.search(key):
				exact[key] = pl
				continue
			parts = re.split(r"(%\d)", key)
			literal = max((p for p in parts if not _PLACEHOLDER.fullmatch(p)), key=len)
			if len(literal.strip()) < 3:
				continue  # sam „%1 / %2” pasowałby do wszystkiego
			seen, rx = set(), ""
			for p in parts:
				m = _PLACEHOLDER.fullmatch(p)
				if not m:
					rx += re.escape(p)
				elif m.group(1) in seen:
					rx += "(?P=p%s)" % m.group(1)
				else:
					seen.add(m.group(1))
					rx += "(?P<p%s>.+?)" % m.group(1)
			patterns[key] = (literal, re.compile(rx, re.S), pl)
	# Najpierw najdłuższe, najbardziej konkretne wzorce.
	ordered = sorted(patterns.values(), key=lambda p: -len(p[0]))

	def tr(text):
		if not text:
			return text
		key = _key(text)
		pl = exact.get(key)
		if pl is not None:
			return pl
		for literal, rx, template in ordered:
			if literal in key:
				m = rx.fullmatch(key)
				if m:
					values = m.groupdict()
					return _PLACEHOLDER.sub(lambda x: values.get("p" + x.group(1), x.group(0)), template)
		return text

	return tr

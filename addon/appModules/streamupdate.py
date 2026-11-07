# StreamFab dostęp — moduł aplikacji NVDA dla StreamUpdate.exe (okno aktualizacji StreamFab, Qt6).
# To osobny proces od StreamFab64.exe, więc moduł streamfab64 w nim nie działa.
# AutomationId elementów to ścieżka nazw obiektów Qt, np.
# "LiveUpdateDlg.widgetBody.widget_tip.label_topTips" — rozpoznajemy je po ostatnim członie.

import ctypes
import ctypes.wintypes
import queue
import re
import threading
import time

import api
import appModuleHandler
import comtypes
import controlTypes
import NVDAObjects.UIA
import queueHandler
import ui
import UIAHandler
from logHandler import log
from scriptHandler import script

UIA = UIAHandler.UIA
CATEGORY = "StreamFab dostęp"

# Polskie nazwy elementów, które okno aktualizacji zostawia bez nazwy lub z nazwą angielską.
NAMES = {
	"pushButton_min": "Minimalizuj",
	"pushButton_close": "Zamknij",
	"pushButton_skipVersion": "Pomiń tę wersję",
	"pushButton_updateNow": "Uaktualnij teraz",
	"pushButton_cancel": "Anuluj",
	"checkBox_allowBeta": "Otrzymuj aktualizacje w wersji beta",
	"tableView_update": "Lista dostępnych aktualizacji",
	"textBrowser": "Co nowego",
	"LiveUpdateDlg": "Aktualizacja StreamFab",
}
# Tłumaczenia komunikatów okna (angielski -> polski). Nieznane teksty zostają bez zmian.
TRANSLATE = {
	"A new Official version of StreamFab is detected.": "Wykryto nową oficjalną wersję StreamFab.",
	"A new version of StreamFab is detected.": "Wykryto nową wersję StreamFab.",
	"A new Beta version of StreamFab is detected.": "Wykryto nową wersję beta StreamFab.",
	"Receive beta version updates": "Otrzymuj aktualizacje w wersji beta",
	"Beta versions may contain new features and experimental changes, but maybe less stable.":
		"Wersje beta mogą zawierać nowe funkcje i zmiany eksperymentalne, ale mogą być mniej stabilne.",
	"Skip this version": "Pomiń tę wersję",
	"Update now": "Uaktualnij teraz",
	"Cancel": "Anuluj",
	"Downloading": "Pobieranie",
	"Installing": "Instalowanie",
	"Download completed": "Pobieranie zakończone",
	"Download failed": "Pobieranie nie powiodło się",
	"Waiting": "Oczekiwanie",
	"Failed": "Błąd",
	"Completed": "Zakończono",
	"Retry": "Spróbuj ponownie",
	"Close": "Zamknij",
}
HEADERS = {
	"Name": "Nazwa",
	"Current Version": "Obecna wersja",
	"New Version": "Nowa wersja",
	"Size": "Rozmiar",
	"Status": "Stan",
}
# Fragment zdania opisującego komórkę w wierszu tabeli (kolumna -> opis).
ROW_PARTS = {
	"Current Version": "obecna wersja",
	"New Version": "nowa wersja",
	"Size": "rozmiar",
	"Status": "stan",
}
SKIP_LABELS = ("label_whatsnew", "label_more", "label_betaTextUp", "label_betaTextDown", "label_title",
	"label_topTips", "label_bottomTips", "label_iconOK")
TEXT_TYPE = 50020
HEADER_TYPE = 50034
DATAITEM_TYPE = 50029
TABLE_TYPE = 50036
PROGRESS_TYPE = 50012
HINT = ("Skróty: Ctrl+Shift+U lub O uaktualnij teraz, Ctrl+Shift+P pomiń wersję, Ctrl+Shift+C anuluj, "
	"Ctrl+Shift+I co nowego, Ctrl+Shift+M historia zmian, Ctrl+Shift+B aktualizacje beta, "
	"Ctrl+Shift+R przeczytaj okno, Ctrl+Shift+H pomoc. Tab przechodzi do przycisków.")
# Własny cykl Tab: (ostatni człon AutomationId, rodzaj, polska nazwa, rola mówiona).
TAB_ORDER = (
	("tableView_update", "table", "Tabela wersji", "tabela"),
	("textBrowser", "text", "Co nowego", "pole tekstowe, Ctrl+Shift+I czyta"),
	("label_more", "link", "Historia zmian", "link"),
	("checkBox_allowBeta", "check", "Otrzymuj aktualizacje w wersji beta", "pole wyboru"),
	("pushButton_skipVersion", "button", "Pomiń tę wersję", "przycisk"),
	("pushButton_updateNow", "button", "Uaktualnij teraz", "przycisk"),
	("pushButton_cancel", "button", "Anuluj", "przycisk"),
	("pushButton_min", "button", "Minimalizuj", "przycisk"),
	("pushButton_close", "button", "Zamknij", "przycisk"),
)
_PCT = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")


def say(text):
	queueHandler.queueFunction(queueHandler.eventQueue, ui.message, text)


def tr(text):
	text = (text or "").strip()
	return TRANSLATE.get(text, text)


def last(aid):
	return (aid or "").split(".")[-1]


class Worker(threading.Thread):
	"""Wątek z własnym klientem UIA: wykonuje polecenia skrótów i co sekundę sprawdza okno aktualizacji.

	Wszystkie wywołania UIA odbywają się tutaj, więc zawieszone okno nie blokuje NVDA.
	"""

	def __init__(self, pid):
		super().__init__(name="StreamUpdateDostep", daemon=True)
		self.pid = pid
		self.tasks = queue.Queue()
		self.running = True
		self.autoAnnounce = True
		self.uia = None
		self.present = False
		self.seen = {}  # klucz elementu -> ostatnio ogłoszona wartość (tekst lub procent)
		self.shownAt = 0.0
		self.cur = None  # klucz bieżącego elementu własnego cyklu Tab

	def run(self):
		comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
		try:
			try:
				clsid = UIA.CUIAutomation8._reg_clsid_
			except AttributeError:
				clsid = UIA.CUIAutomation._reg_clsid_
			self.uia = comtypes.CoCreateInstance(clsid, interface=UIA.IUIAutomation, clsctx=comtypes.CLSCTX_INPROC_SERVER)
			self.true = self.uia.CreateTrueCondition()
			self.pidCond = self.uia.CreatePropertyCondition(UIA.UIA_ProcessIdPropertyId, self.pid)
			while self.running:
				try:
					task = self.tasks.get(timeout=1.0)
				except queue.Empty:
					task = None
				try:
					if task:
						task()
					else:
						self.poll()
				except Exception:
					log.warning("StreamFab dostęp (aktualizacja): błąd UIA", exc_info=True)
		except Exception:
			log.error("StreamFab dostęp (aktualizacja): nie udało się uruchomić wątku UIA", exc_info=True)
		finally:
			self.uia = None
			comtypes.CoUninitialize()

	def stop(self):
		self.running = False
		self.tasks.put(None)

	# --- migawka okna ---
	def snapshot(self):
		"""Lista elementów wszystkich okien procesu: słowniki z kluczami el, last, name, type, aid. Pusta, gdy brak okna."""
		items = []
		root = self.uia.GetRootElement()
		try:
			tops = root.FindAll(UIA.TreeScope_Children, self.pidCond)
		except comtypes.COMError:
			return items
		for i in range(tops.Length):
			try:
				top = tops.GetElement(i)
				arr = top.FindAll(UIA.TreeScope_Subtree, self.true)
				for j in range(arr.Length):
					el = arr.GetElement(j)
					try:
						aid = el.CurrentAutomationId or ""
						items.append({"el": el, "aid": aid, "last": last(aid), "name": el.CurrentName or "",
							"type": el.CurrentControlType})
					except comtypes.COMError:
						continue
			except comtypes.COMError:
				continue
		if not any(it["last"] == "LiveUpdateDlg" for it in items):
			return []
		return items

	@staticmethod
	def byLast(items, name):
		for it in items:
			if it["last"] == name:
				return it
		return None

	def table(self, items):
		"""(nagłówki, wiersze) tabeli; wiersz to lista (nagłówek angielski, tekst komórki)."""
		start = next((k for k, it in enumerate(items) if it["last"] == "tableView_update"), None)
		if start is None:
			return [], []
		headers, cells = [], []
		for it in items[start + 1:]:
			if it["type"] == HEADER_TYPE:
				if it["name"]:
					headers.append(it["name"])
			elif it["type"] == DATAITEM_TYPE:
				cells.append(it)
			elif it["last"].startswith("widget_") or it["type"] == TEXT_TYPE and it["last"]:
				break  # koniec tabeli
		if not headers or not cells:
			return headers, []
		ncols = len(headers)
		if len(cells) % ncols and ncols > 1 and len(cells) % (ncols - 1) == 0:
			ncols -= 1  # ostatnia kolumna (Status) bez komórek
		rows = []
		for k in range(0, len(cells) - ncols + 1, ncols):
			rows.append([(headers[c], cells[k + c]["name"]) for c in range(ncols)])
		return headers, rows

	@staticmethod
	def rowText(row):
		if not row:
			return ""
		text = row[0][1]
		parts = []
		for head, val in row[1:]:
			if val:
				parts.append("%s %s" % (ROW_PARTS.get(head, HEADERS.get(head, head).lower()), val))
		return text + (": " + ", ".join(parts) if parts else "")

	def describe(self, items):
		out = []
		title = self.byLast(items, "label_title")
		out.append(title["name"] if title and title["name"] else "Aktualizacja StreamFab")
		for key in ("label_topTips", "label_bottomTips"):
			it = self.byLast(items, key)
			if it and it["name"]:
				out.append(tr(it["name"]))
		headers, rows = self.table(items)
		for r in rows:
			out.append(self.rowText(r))
		beta = self.byLast(items, "checkBox_allowBeta")
		if beta:
			out.append("Otrzymuj aktualizacje w wersji beta: " + self.toggleState(beta["el"]))
		for it in items:
			if it["type"] == PROGRESS_TYPE:
				v = self.rangeValue(it["el"])
				if v is not None:
					out.append("Postęp %d%%" % v)
		out.append(HINT)
		return ". ".join(t.rstrip(".") for t in out if t)

	# --- odczyty wzorców ---
	def toggleState(self, el):
		try:
			pat = el.GetCurrentPattern(UIA.UIA_TogglePatternId).QueryInterface(UIA.IUIAutomationTogglePattern)
			return "włączone" if pat.CurrentToggleState == 1 else "wyłączone"
		except (comtypes.COMError, AttributeError, ValueError):
			return "stan nieznany"

	def rangeValue(self, el):
		try:
			pat = el.GetCurrentPattern(UIA.UIA_RangeValuePatternId).QueryInterface(UIA.IUIAutomationRangeValuePattern)
			lo, hi, cur = pat.CurrentMinimum, pat.CurrentMaximum, pat.CurrentValue
			if hi > lo:
				return int(round((cur - lo) * 100.0 / (hi - lo)))
		except (comtypes.COMError, AttributeError, ValueError):
			pass
		return None

	# --- ogłaszanie zmian ---
	def poll(self):
		items = self.snapshot()
		if not items:
			self.cur = None
			if self.present:
				self.present = False
				self.seen.clear()
			return
		if not self.present:
			self.present = True
			self.cur = None
			self.seen.clear()
			self.shownAt = time.monotonic()
			self.remember(items)
			if self.autoAnnounce:
				say(self.describe(items))
			return
		if self.autoAnnounce:
			self.announceChanges(items)
		else:
			self.remember(items)

	def entries(self, items):
		"""(klucz, tekst) elementów, których zmiany ogłaszamy: etykiety, komórki tabeli i paski postępu."""
		out = []
		headers, rows = self.table(items)
		for r, row in enumerate(rows):
			for c, (head, val) in enumerate(row):
				out.append(("cell%d_%d" % (r, c), "%s: %s" % (HEADERS.get(head, head), tr(val)) if c else None, val))
		for k, it in enumerate(items):
			if it["type"] == TEXT_TYPE and it["name"] and it["last"] and it["last"] not in SKIP_LABELS:
				out.append((it["aid"], tr(it["name"]), it["name"]))
			elif it["type"] == PROGRESS_TYPE:
				v = self.rangeValue(it["el"])
				if v is not None:
					out.append(("progress%d" % k, "Postęp %d%%" % v, "%d%%" % v))
		return out

	def remember(self, items):
		for key, text, raw in self.entries(items):
			self.seen[key] = raw

	def announceChanges(self, items):
		for key, text, raw in self.entries(items):
			old = self.seen.get(key)
			if old == raw:
				continue
			if text is None:
				self.seen[key] = raw  # pierwsza kolumna (nazwa) — zmiany ciche
				continue
			newPct, oldPct = _PCT.search(raw or ""), _PCT.search(old or "")
			if newPct and oldPct:
				try:
					diff = abs(float(newPct.group(1).replace(",", ".")) - float(oldPct.group(1).replace(",", ".")))
					reached = float(newPct.group(1).replace(",", ".")) >= 100.0
				except ValueError:
					diff, reached = 100, True
				if diff < 5 and not reached:
					continue  # bez spamowania: co kilka procent
			self.seen[key] = raw
			if raw:
				say(text)

	# --- polecenia ---
	def press(self, el):
		"""Invoke w osobnym wątku, bo Qt nie wraca z niego, dopóki otwarte okno modalne jest otwarte."""
		try:
			inv = el.GetCurrentPattern(UIA.UIA_InvokePatternId).QueryInterface(UIA.IUIAutomationInvokePattern)
		except (comtypes.COMError, AttributeError, ValueError):
			inv = None
		if not inv:
			self.click(el)
			return

		def run():
			comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
			try:
				inv.Invoke()
			except comtypes.COMError:
				pass
			finally:
				comtypes.CoUninitialize()
		threading.Thread(target=run, daemon=True).start()
		time.sleep(0.3)

	def click(self, el):
		"""Etykieta Qt (link) reaguje tylko na kliknięcie myszą w środek."""
		r = el.CurrentBoundingRectangle
		x, y = (r.left + r.right) // 2, (r.top + r.bottom) // 2
		user32 = ctypes.windll.user32
		old = ctypes.wintypes.POINT()
		user32.GetCursorPos(ctypes.byref(old))
		user32.SetCursorPos(x, y)
		user32.mouse_event(0x0002, 0, 0, 0, 0)
		user32.mouse_event(0x0004, 0, 0, 0, 0)
		time.sleep(0.05)
		user32.SetCursorPos(old.x, old.y)

	def taskRead(self):
		items = self.snapshot()
		if not items:
			say("Okno aktualizacji StreamFab nie jest otwarte.")
			return
		say(self.describe(items))

	def taskButton(self, names, label):
		items = self.snapshot()
		if not items:
			say("Okno aktualizacji StreamFab nie jest otwarte.")
			return
		for n in names:
			it = self.byLast(items, n)
			if it:
				self.press(it["el"])
				say(label)
				return
		say("Nie znaleziono przycisku: %s." % label)

	def taskWhatsNew(self):
		items = self.snapshot()
		it = self.byLast(items, "textBrowser") if items else None
		if not it:
			say("Pole Co nowego jest niedostępne.")
			return
		text = ""
		try:
			pat = it["el"].GetCurrentPattern(UIA.UIA_TextPatternId).QueryInterface(UIA.IUIAutomationTextPattern)
			text = pat.DocumentRange.GetText(6000) or ""
		except (comtypes.COMError, AttributeError, ValueError):
			pass
		if not text.strip():
			try:
				pat = it["el"].GetCurrentPattern(UIA.UIA_ValuePatternId).QueryInterface(UIA.IUIAutomationValuePattern)
				text = pat.CurrentValue or ""
			except (comtypes.COMError, AttributeError, ValueError):
				pass
		text = re.sub(r"\s*\n\s*", ". ", text.strip())
		say("Co nowego: " + text if text else "Pole Co nowego jest puste.")

	def taskHistory(self):
		items = self.snapshot()
		it = self.byLast(items, "label_more") if items else None
		if not it:
			say("Link do historii zmian jest niedostępny.")
			return
		self.click(it["el"])
		say("Otwieram historię zmian")

	def taskBeta(self):
		items = self.snapshot()
		it = self.byLast(items, "checkBox_allowBeta") if items else None
		if not it:
			say("Pole aktualizacji beta jest niedostępne.")
			return
		try:
			pat = it["el"].GetCurrentPattern(UIA.UIA_TogglePatternId).QueryInterface(UIA.IUIAutomationTogglePattern)
			pat.Toggle()
		except (comtypes.COMError, AttributeError, ValueError):
			self.press(it["el"])
		time.sleep(0.2)
		say("Aktualizacje beta: " + self.toggleState(it["el"]))


	# --- własny Tab ---
	def tabItems(self, items):
		"""Elementy cyklu Tab, które istnieją, są włączone i widoczne."""
		out = []
		for key, kind, label, role in TAB_ORDER:
			it = self.byLast(items, key)
			if not it:
				continue
			try:
				if not it["el"].CurrentIsEnabled or it["el"].CurrentIsOffscreen:
					continue
			except comtypes.COMError:
				continue
			out.append((key, kind, label, role, it))
		return out

	def checkText(self, el):
		try:
			pat = el.GetCurrentPattern(UIA.UIA_TogglePatternId).QueryInterface(UIA.IUIAutomationTogglePattern)
			return "zaznaczone" if pat.CurrentToggleState == 1 else "niezaznaczone"
		except (comtypes.COMError, AttributeError, ValueError):
			return "stan nieznany"

	def taskTab(self, step):
		items = self.snapshot()
		if not items:
			say("Okno aktualizacji StreamFab nie jest otwarte.")
			return
		seq = self.tabItems(items)
		if not seq:
			say("Brak elementów do przejścia.")
			return
		keys = [k[0] for k in seq]
		if self.cur in keys:
			idx = (keys.index(self.cur) + step) % len(seq)
		else:
			idx = 0 if step > 0 else len(seq) - 1
		key, kind, label, role, it = seq[idx]
		self.cur = key
		try:
			it["el"].SetFocus()
		except Exception:
			pass
		if kind == "table":
			_, rows = self.table(items)
			if rows:
				label = "Tabela wersji: " + "; ".join(self.rowText(r) for r in rows)
				role = ""
		elif kind == "check":
			role = "pole wyboru, " + self.checkText(it["el"])
		elif kind == "link" and it["name"]:
			label = tr(it["name"]) if tr(it["name"]) != it["name"] else label
		say("%s, %s" % (label, role) if role else label)

	def taskActivate(self):
		items = self.snapshot()
		if not items:
			say("Okno aktualizacji StreamFab nie jest otwarte.")
			return
		seq = {k[0]: k for k in self.tabItems(items)}
		entry = seq.get(self.cur)
		if not entry:
			say("Element jest niedostępny.")
			return
		key, kind, label, role, it = entry
		if kind == "button":
			self.press(it["el"])
			say(label)
		elif kind == "link":
			self.click(it["el"])
			say("Otwieram historię zmian")
		elif kind == "check":
			try:
				pat = it["el"].GetCurrentPattern(UIA.UIA_TogglePatternId).QueryInterface(UIA.IUIAutomationTogglePattern)
				pat.Toggle()
			except (comtypes.COMError, AttributeError, ValueError):
				self.press(it["el"])
			time.sleep(0.2)
			say("%s: %s" % (label, self.checkText(it["el"])))
		elif kind == "text":
			self.taskWhatsNew()
		else:
			_, rows = self.table(items)
			say("Tabela wersji: " + "; ".join(self.rowText(r) for r in rows) if rows else "Tabela jest pusta.")


class AppModule(appModuleHandler.AppModule):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.worker = Worker(self.processID)
		self.worker.start()

	def terminate(self):
		self.worker.stop()
		super().terminate()

	def event_NVDAObject_init(self, obj):
		aid = getattr(obj, "UIAAutomationId", None)
		if aid is None:
			return
		try:
			name = last(aid)
			role = obj.role
			if name in NAMES:
				if name == "tableView_update" or name == "textBrowser":
					if not obj.name:
						obj.name = NAMES[name]
				else:
					obj.name = NAMES[name]
				if name == "checkBox_allowBeta":
					obj.description = TRANSLATE["Beta versions may contain new features and experimental changes, but maybe less stable."]
				return
			orig = obj.name
			if orig and orig in HEADERS and role in (controlTypes.Role.TABLECOLUMNHEADER, controlTypes.Role.TABLEROWHEADER):
				obj.name = HEADERS[orig]
			elif orig and orig in HEADERS and not name:
				obj.name = HEADERS[orig]
			elif role in (controlTypes.Role.DATAITEM, controlTypes.Role.TABLECELL) and orig:
				self._nameCell(obj, orig)
			elif orig and orig in TRANSLATE:
				obj.name = TRANSLATE[orig]
			elif name in ("label_topTips", "label_betaTextUp", "label_betaTextDown", "label_bottomTips") and orig:
				obj.name = tr(orig)
		except Exception:
			log.debugWarning("StreamUpdate: nie udało się nazwać elementu", exc_info=True)

	def _nameCell(self, obj, orig):
		"""Komórka tabeli aktualizacji: dopisuje polską nazwę kolumny."""
		try:
			col = obj._getUIACacheablePropertyValue(UIA.UIA_GridItemColumnPropertyId)
		except Exception:
			return
		heads = ["Nazwa", "Obecna wersja", "Nowa wersja", "Rozmiar", "Stan"]
		if isinstance(col, int) and 0 <= col < len(heads):
			obj.name = "%s: %s" % (heads[col], orig)

	def _put(self, task):
		self.worker.tasks.put(task)

	@script(description="Czyta treść okna aktualizacji StreamFab", category=CATEGORY, gesture="kb:control+shift+r")
	def script_readWindow(self, gesture):
		self._put(self.worker.taskRead)

	@script(description="Uaktualnij teraz (okno aktualizacji)", category=CATEGORY, gesture="kb:control+shift+u")
	def script_updateNow(self, gesture):
		self._put(lambda: self.worker.taskButton(("pushButton_updateNow",), "Uaktualnij teraz"))

	@script(description="Uaktualnij teraz (jak OK w oknach StreamFab)", category=CATEGORY, gesture="kb:control+shift+o")
	def script_ok(self, gesture):
		self._put(lambda: self.worker.taskButton(("pushButton_updateNow",), "Uaktualnij teraz"))

	@script(description="Pomiń tę wersję (okno aktualizacji)", category=CATEGORY, gesture="kb:control+shift+p")
	def script_skip(self, gesture):
		self._put(lambda: self.worker.taskButton(("pushButton_skipVersion",), "Pomiń tę wersję"))

	@script(description="Anuluj lub zamknij okno aktualizacji", category=CATEGORY, gesture="kb:control+shift+c")
	def script_cancel(self, gesture):
		self._put(lambda: self.worker.taskButton(("pushButton_cancel", "pushButton_close"), "Anuluj"))

	@script(description="Czyta tekst Co nowego z okna aktualizacji", category=CATEGORY, gesture="kb:control+shift+i")
	def script_whatsNew(self, gesture):
		self._put(self.worker.taskWhatsNew)

	@script(description="Otwiera historię zmian StreamFab", category=CATEGORY, gesture="kb:control+shift+m")
	def script_history(self, gesture):
		self._put(self.worker.taskHistory)

	@script(description="Przełącza otrzymywanie aktualizacji w wersji beta", category=CATEGORY, gesture="kb:control+shift+b")
	def script_beta(self, gesture):
		self._put(self.worker.taskBeta)

	@script(description="Włącza lub wyłącza ogłaszanie zmian w oknie aktualizacji", category=CATEGORY, gesture="kb:control+shift+a")
	def script_toggleAnnounce(self, gesture):
		self.worker.autoAnnounce = not self.worker.autoAnnounce
		ui.message("Ogłaszanie włączone" if self.worker.autoAnnounce else "Ogłaszanie wyłączone")

	@script(description="Czyta listę skrótów okna aktualizacji", category=CATEGORY, gesture="kb:control+shift+h")
	def script_help(self, gesture):
		ui.message(HINT + " Ctrl+Shift+A: ogłaszanie zmian.")

	# --- własny Tab (okno aktualizacji nie dopuszcza Tab do przycisków) ---
	def _tab(self, gesture, step):
		if not self.worker.present:
			gesture.send()
			return
		self._put(lambda: self.worker.taskTab(step))

	@script(description="Następny element okna aktualizacji", category=CATEGORY, gesture="kb:tab")
	def script_tabNext(self, gesture):
		self._tab(gesture, 1)

	@script(description="Poprzedni element okna aktualizacji", category=CATEGORY, gesture="kb:shift+tab")
	def script_tabPrev(self, gesture):
		self._tab(gesture, -1)

	@script(description="Wykonuje akcję bieżącego elementu okna aktualizacji", category=CATEGORY,
		gestures=["kb:enter", "kb:space", "kb:numpadEnter"])
	def script_activate(self, gesture):
		if not self.worker.present or self.worker.cur is None:
			gesture.send()
			return
		self._put(self.worker.taskActivate)

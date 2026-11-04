# StreamFab dostęp — moduł aplikacji NVDA dla StreamFab64.exe (Qt6 + CEF).
# Qt udostępnia elementy przez UI Automation; AutomationId to ścieżka nazw obiektów Qt,
# np. "StreamMainWnd.widget_Main....StreamNavigateBar.pushButtonReload".

import ctypes
import ctypes.wintypes
import os
import queue
import re
import struct
import subprocess
import threading
import time

import api
import appModuleHandler
import comtypes
import controlTypes
import core
import eventHandler
import gui
import NVDAObjects.UIA
import queueHandler
import ui
import UIAHandler
import winUser
import wx
from logHandler import log
from scriptHandler import script

UIA = UIAHandler.UIA
CATEGORY = "StreamFab dostęp"

# Polskie nazwy elementów, które StreamFab zostawia bez nazwy (ostatni człon AutomationId).
NAMES = {
	"pushButtonHistoryBack": "Wstecz",
	"pushButtonHistoryForward": "Dalej",
	"pushButtonReload": "Odśwież",
	"pushButtonCollect": "Dodaj stronę do zakładek",
	"pushButton_operate": "Pobierz wideo",
	"comboBox_afterWorkFinish": "Akcja po zakończeniu pobierania",
	"websiteSearchEdit": "Szukaj serwisów",
	"pushButton_dialogClose": "Zamknij",
	"pushButton_close": "Zamknij",
	"pushButtonClose": "Zamknij",
	"btn_close": "Zamknij",
	"pushButton_path": "Wybierz folder",
	"lineEdit_directory": "Katalog",
	"ledt_urlInput": "Adres URL",
	"pushButton_ImageLink": "Reklama, link",
	"listView_youtubePopularSites": "Popularne witryny",
	"treeview_task_queue": "Pobrane filmy",
}
# Pola okna pobierania (po analizie filmu/serialu), które StreamFab nazywa po angielsku albo wcale.
# Te nazwy zastępują nazwę programu zawsze.
FORCE_NAMES = {
	"comboBox_Audio": "Język audio",
	"comboBox_Subtitle": "Napisy",
	"comboBox_Resolution": "Rozdzielczość",
	"comboBox_scheduleType": "Jak często sprawdzać nowe odcinki",
	"comboBox_dayofWeek": "Dzień tygodnia",
	"timeEdit_time": "Godzina",
}
# Qt dopisuje do nazw elementów list i drzew angielski stan ("Checked", "Collapsed, use Enter...").
# NVDA i tak podaje stan po polsku, więc te dopiski usuwamy.
_STATE_SUFFIX = re.compile(r",\s*(?:Checked|Not checked|Unchecked|Partially checked|Expanded|Collapsed)\b.*$", re.I | re.S)
_DURATION = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")
# Języki ścieżek audio i napisów na liście wyboru (StreamFab podaje je po angielsku).
LANGUAGES = {
	"Arabic": "arabski", "Bulgarian": "bułgarski", "Cantonese": "kantoński", "Catalan": "kataloński",
	"Chinese": "chiński", "Croatian": "chorwacki", "Czech": "czeski", "Danish": "duński", "Dutch": "niderlandzki",
	"English": "angielski", "Estonian": "estoński", "Finnish": "fiński", "Flemish": "flamandzki",
	"French": "francuski", "German": "niemiecki", "Greek": "grecki", "Hebrew": "hebrajski", "Hindi": "hindi",
	"Hungarian": "węgierski", "Icelandic": "islandzki", "Indonesian": "indonezyjski", "Italian": "włoski",
	"Japanese": "japoński", "Korean": "koreański", "Latvian": "łotewski", "Lithuanian": "litewski",
	"Malay": "malajski", "Mandarin": "mandaryński", "Norwegian": "norweski", "Polish": "polski",
	"Portuguese": "portugalski", "Romanian": "rumuński", "Russian": "rosyjski", "Serbian": "serbski",
	"Slovak": "słowacki", "Slovenian": "słoweński", "Spanish": "hiszpański", "Swedish": "szwedzki",
	"Tagalog": "tagalski", "Tamil": "tamilski", "Telugu": "telugu", "Thai": "tajski", "Turkish": "turecki",
	"Ukrainian": "ukraiński", "Vietnamese": "wietnamski",
	"Latin America": "Ameryka Łacińska", "Brazil": "Brazylia", "Portugal": "Portugalia", "Canada": "Kanada",
	"Spain": "Hiszpania", "France": "Francja", "Simplified": "uproszczony", "Traditional": "tradycyjny",
	"Taiwan": "Tajwan", "Hong Kong": "Hongkong", "Forced": "wymuszone", "Audio Description": "audiodeskrypcja",
}
_LANG_WORD = re.compile(r"\b(" + "|".join(sorted((re.escape(k) for k in LANGUAGES), key=len, reverse=True)) + r")\b")
# Klawisze przechwytywane, gdy otwarte jest okno StreamFab (gest: nazwa skryptu).
DIALOG_GESTURES = {
	"kb:tab": "passNavKey",
	"kb:shift+tab": "passNavKey",
	"kb:upArrow": "passNavKey",
	"kb:downArrow": "passNavKey",
	"kb:space": "toggleItem",
}
ITEM_ROLES = (
	controlTypes.Role.TREEVIEWITEM,
	controlTypes.Role.LISTITEM,
	controlTypes.Role.DATAITEM,
	controlTypes.Role.TABLECELL,
)
# Przyciski okien StreamFab często nie przyjmują fokusu (Tab ich pomija),
# dlatego dodatek naciska je sam. Ostatni człon AutomationId przycisków zatwierdzania i anulowania:
OK_BUTTONS = ("pushButton_ok", "pushButton_OK", "pushButton_confirm", "pushButton_yes", "btn_ok", "btnOk",
	"pushButtonOk", "StreamMessageBox_PrimaryButton")
CANCEL_BUTTONS = ("pushButton_cancel", "pushButton_Cancel", "pushButton_no", "btn_cancel", "btnCancel", "pushButtonCancel")
CLOSE_BUTTONS = ("pushButton_dialogClose", "pushButton_close", "pushButtonClose", "btn_close")
OK_NAMES = ("ok", "tak", "yes", "potwierdź", "confirm", "zapisz", "save")
CANCEL_NAMES = ("cancel", "anuluj", "nie", "no")
WINDOW_TYPE = 50032
TEXT_TYPE = 50020
EDIT_TYPE = 50004
BUTTON_TYPES = (50000, 50002, 50013, 50003)  # przycisk, pole wyboru, przycisk opcji, lista rozwijana
# Pole adresu ma ogólną nazwę obiektu "lineEdit", więc rozpoznajemy je też po klasie.
ADDRESS_CLASS = "WebNavigateLine"
# Poddrzewa przeglądarki CEF pomijamy przy przeszukiwaniu (tysiące elementów strony).
SKIP_CLASSES = ("CefBrowserWindow", "WebSiteView")
# Polskie tytuły okien, które StreamFab nazywa nazwą techniczną (klasa lub nazwa okna).
DIALOG_TITLES = {
	"MyAccountDlg": "Menu Moje konto. Tab przechodzi po pozycjach, Escape zamyka",
	"UniFabIntroduceDlg": "Okno reklamy UniFab. Uwaga: przycisk Instaluj w tle instaluje inny program",
}
POPUP_CLASSES = ("ComboBox", "QMenu", "Menu", "ToolTip", "TipLabel", "Popup", "QListView", "Completer")
# Okno dialogowe z większą liczbą tekstów (np. Ustawienia) czytamy tylko z tytułu.
MAX_AUTO_TEXTS = 6
NAMED_ROLES = (
	controlTypes.Role.BUTTON,
	controlTypes.Role.TOGGLEBUTTON,
	controlTypes.Role.CHECKBOX,
	controlTypes.Role.EDITABLETEXT,
	controlTypes.Role.COMBOBOX,
	controlTypes.Role.MENUBUTTON,
)
_PREFIX = re.compile(r"^(pushButton|toolButton|btn|button|comboBox|lineEdit|ledt|checkBox|radioButton)_?|^l_", re.I)


def humanize(objectName):
	"""Zamienia nazwę obiektu Qt (np. pushButton_learnMore) na czytelny tekst."""
	text = _PREFIX.sub("", objectName) or objectName
	text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text).replace("_", " ").strip()
	return text[:1].upper() + text[1:] if text else objectName


def say(text):
	queueHandler.queueFunction(queueHandler.eventQueue, ui.message, text)


# --- lista pobranych filmów (pliki localdata StreamFab, format QDataStream) ---
LOCALDATA = os.path.expandvars(r"%APPDATA%\StreamFab\StreamFab\localdata")
MEDIA_EXT = (".mp4", ".mkv", ".m4v", ".mov", ".webm", ".ts", ".avi", ".m4a", ".mp3", ".aac", ".flac", ".opus", ".wav")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def _qstrings(data):
	"""Wyszukuje w danych QDataStream napisy (długość uint32 BE + UTF-16BE)."""
	out = []
	i, n = 0, len(data)
	while i + 4 <= n:
		ln = struct.unpack(">I", data[i:i + 4])[0]
		if 2 <= ln <= 4000 and ln % 2 == 0 and i + 4 + ln <= n:
			try:
				s = data[i + 4:i + 4 + ln].decode("utf-16-be")
			except UnicodeDecodeError:
				s = None
			if s and all(c.isprintable() for c in s):
				out.append(s)
				i += 4 + ln
				continue
		i += 1
	return out


def readDownloadedFilms():
	"""Zwraca listę (tytuł, serwis, ścieżka pliku) w kolejności zapisu w plikach programu."""
	films = []
	try:
		with open(os.path.join(LOCALDATA, "local_index"), "r", encoding="utf-8", errors="replace") as f:
			sites = [s.strip() for s in f.read().splitlines() if s.strip()]
	except OSError:
		sites = []
	for site in sites:
		try:
			with open(os.path.join(LOCALDATA, site), "rb") as f:
				strings = _qstrings(f.read())
		except OSError:
			continue
		title = ""
		for s in strings:
			low = s.lower()
			if (":/" in s or ":\\" in s) and low.endswith(MEDIA_EXT):
				films.append((title or os.path.splitext(os.path.basename(s))[0], site, s.replace("/", "\\")))
				title = ""
			elif ":/" in s or ":\\" in s or _UUID.match(s) or s == site:
				continue
			else:
				title = s
	return films


class FilmsDialog(wx.Dialog):
	"""Dostępna lista pobranych filmów: odtwarzanie i pokazywanie pliku w folderze."""

	def __init__(self, parent, films):
		super().__init__(parent, title="StreamFab — pobrane filmy")
		self.films = films
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(wx.StaticText(self, label="&Pobrane filmy"), 0, wx.ALL, 5)
		items = []
		for title, site, path in films:
			missing = "" if os.path.exists(path) else " (brak pliku)"
			items.append("%s, %s%s" % (title, site, missing))
		self.list = wx.ListBox(self, choices=items or ["Brak pobranych filmów"], size=(600, 300))
		self.list.SetSelection(0)
		sizer.Add(self.list, 1, wx.ALL | wx.EXPAND, 5)
		btns = wx.BoxSizer(wx.HORIZONTAL)
		for label, handler in (("&Odtwórz", self.onPlay), ("Pokaż w &folderze", self.onFolder),
				("&Kopiuj ścieżkę", self.onCopy), ("Zamknij", self.onClose)):
			b = wx.Button(self, label=label)
			b.Bind(wx.EVT_BUTTON, handler)
			btns.Add(b, 0, wx.ALL, 5)
			b.Enable(bool(films) or label == "Zamknij")
		sizer.Add(btns)
		self.SetSizerAndFit(sizer)
		self.list.Bind(wx.EVT_LISTBOX_DCLICK, self.onPlay)
		self.Bind(wx.EVT_CHAR_HOOK, self.onKey)
		self.list.SetFocus()

	def current(self):
		i = self.list.GetSelection()
		return self.films[i][2] if 0 <= i < len(self.films) else None

	def onKey(self, evt):
		if evt.GetKeyCode() == wx.WXK_ESCAPE:
			self.onClose(None)
		elif evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and self.FindFocus() is self.list:
			self.onPlay(None)
		else:
			evt.Skip()

	def onPlay(self, evt):
		path = self.current()
		if path and os.path.exists(path):
			os.startfile(path)
			self.onClose(None)
		elif path:
			ui.message("Plik nie istnieje: " + path)

	def onFolder(self, evt):
		path = self.current()
		if path and os.path.exists(path):
			subprocess.Popen(["explorer", "/select,", path])
			self.onClose(None)
		elif path:
			folder = os.path.dirname(path)
			if os.path.isdir(folder):
				os.startfile(folder)
				self.onClose(None)
			else:
				ui.message("Folder nie istnieje")

	def onCopy(self, evt):
		path = self.current()
		if path and wx.TheClipboard.Open():
			wx.TheClipboard.SetData(wx.TextDataObject(path))
			wx.TheClipboard.Close()
			ui.message("Skopiowano ścieżkę")

	def onClose(self, evt):
		self.Destroy()


class Worker(threading.Thread):
	"""Wątek z własnym klientem UIA: wykonuje polecenia skrótów i co sekundę sprawdza stan pobierania.

	Wszystkie wywołania UIA odbywają się tutaj, więc zawieszony StreamFab nie blokuje NVDA.
	"""

	def __init__(self, pid):
		super().__init__(name="StreamFabDostep", daemon=True)
		self.pid = pid
		self.tasks = queue.Queue()
		self.running = True
		self.autoAnnounce = True
		self.uia = None
		self._labels = {}
		self._lastResolve = 0.0
		self._lastState = None
		self._loggedBar = False
		self._dialogKey = None
		self._cycle = None  # (identyfikator okna, indeks)
		self._lastCount = None  # ostatnio przeczytany licznik zaznaczonych odcinków
		self.onDialogChange = None  # wywoływane w głównym wątku NVDA: (czy jest otwarte okno)

	# --- pętla ---
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
					log.warning("StreamFab dostęp: błąd UIA", exc_info=True)
					self._labels.clear()
		except Exception:
			log.error("StreamFab dostęp: nie udało się uruchomić wątku UIA", exc_info=True)
		finally:
			self.uia = None
			comtypes.CoUninitialize()

	def stop(self):
		self.running = False
		self.tasks.put(None)

	# --- pomocnicze UIA ---
	def children(self, el):
		arr = el.FindAll(UIA.TreeScope_Children, self.true)
		return [arr.GetElement(i) for i in range(arr.Length)] if arr else []

	def topWindows(self):
		root = self.uia.GetRootElement()
		arr = root.FindAll(UIA.TreeScope_Children, self.pidCond)
		return [arr.GetElement(i) for i in range(arr.Length)] if arr else []

	def mainWindow(self):
		for w in self.topWindows():
			if w.CurrentAutomationId == "StreamMainWnd":
				return w
		return None

	def find(self, start, match, maxDepth=16):
		"""Przeszukiwanie wszerz widocznych elementów Qt (bez stron WWW)."""
		level = [start]
		for _ in range(maxDepth):
			nxt = []
			for el in level:
				for ch in self.children(el):
					try:
						if ch.CurrentIsOffscreen or ch.CurrentClassName in SKIP_CLASSES:
							continue
						if match(ch):
							return ch
					except comtypes.COMError:
						continue
					nxt.append(ch)
			if not nxt:
				break
			level = nxt
		return None

	def collect(self, start, match, maxDepth=12):
		"""Wszystkie widoczne elementy spełniające warunek, w kolejności czytania."""
		found = []
		level = [start]
		for _ in range(maxDepth):
			nxt = []
			for el in level:
				for ch in self.children(el):
					try:
						if ch.CurrentIsOffscreen or ch.CurrentClassName in SKIP_CLASSES:
							continue
						if match(ch):
							found.append(ch)
					except comtypes.COMError:
						continue
					nxt.append(ch)
			if not nxt:
				break
			level = nxt

		def pos(e):
			try:
				r = e.CurrentBoundingRectangle
				return (r.top // 10, r.left)
			except comtypes.COMError:
				return (0, 0)
		found.sort(key=pos)
		return found

	@staticmethod
	def last(el):
		return (el.CurrentAutomationId or "").rsplit(".", 1)[-1]

	def operateButton(self):
		for w in self.topWindows():
			try:
				if w.CurrentAutomationId.endswith(".pushButton_operate") and not w.CurrentIsOffscreen:
					return w
			except comtypes.COMError:
				pass
		return None

	def resolveLabels(self):
		self._labels.clear()
		main = self.mainWindow()
		if not main:
			return
		bar = self.find(main, lambda e: self.last(e) == "widget_bottomOperate")
		if not bar:
			return
		for key in ("label_statusText", "label_downloadQueueText"):
			el = self.find(bar, lambda e, k=key: self.last(e) == k, maxDepth=3)
			if el:
				self._labels[key] = el
		if not self._loggedBar:
			self._loggedBar = True
			log.info("StreamFab dostęp: znaleziono pasek stanu pobierania (%d etykiet)" % len(self._labels))

	def labelText(self, key):
		el = self._labels.get(key)
		if not el:
			return ""
		try:
			if el.CurrentIsOffscreen:
				self._labels.clear()
				return ""
			return el.CurrentName or ""
		except comtypes.COMError:
			self._labels.clear()
			return ""

	def readState(self, force=False):
		now = time.monotonic()
		if not self._labels and (force or now - self._lastResolve > 3.0):
			self._lastResolve = now
			self.resolveLabels()
		btn = self.operateButton()
		enabled = None
		if btn:
			try:
				enabled = bool(btn.CurrentIsEnabled)
			except comtypes.COMError:
				enabled = None
		return (self.labelText("label_statusText"), self.labelText("label_downloadQueueText"), enabled)

	def isForeground(self):
		hwnd = winUser.getForegroundWindow()
		pid = ctypes.c_ulong()
		ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
		return pid.value == self.pid

	# --- okresowe sprawdzanie ---
	def poll(self):
		if not self.isForeground():
			return
		self.checkDialog()
		state = self.readState()
		prev, self._lastState = self._lastState, state
		if prev is None or not self.autoAnnounce:
			return
		status, queueText, enabled = state
		msgs = []
		if status and status != prev[0]:
			msgs.append(status)
		if queueText and queueText != prev[1]:
			msgs.append(queueText)
		if enabled and prev[2] is not True:
			msgs.append("Przycisk Pobierz wideo jest aktywny, Ctrl+Shift+D")
		if msgs:
			say(". ".join(msgs))

	def checkDialog(self):
		"""Gdy pojawi się nowe okno: przenosi do niego fokus (jeśli został poza nim) i czyta jego treść."""
		dlg = self.activeDialog()
		key = None
		if dlg:
			try:
				key = (dlg.CurrentAutomationId, dlg.CurrentName, dlg.CurrentClassName)
			except comtypes.COMError:
				return
		if key == self._dialogKey:
			return
		self._dialogKey = key
		self._cycle = None
		self._lastCount = None
		if self.onDialogChange:
			queueHandler.queueFunction(queueHandler.eventQueue, self.onDialogChange, bool(dlg))
		if not dlg or not self.autoAnnounce:
			return
		time.sleep(0.4)  # niech okno się dorysuje
		self.taskReadDialog(dlg, auto=True)
		self.taskHiddenFocus(dlg, delay=0)

	def taskHiddenFocus(self, dlg=None, delay=0.15):
		"""Niektóre okna StreamFab (np. menu My Account) przyjmują klawiaturę, ale nie zgłaszają fokusu.
		Wtedy sami znajdujemy element z fokusem klawiatury i go czytamy."""
		if delay:
			time.sleep(delay)
		dlg = dlg or self.activeDialog()
		if not dlg:
			return
		try:
			focus = self.uia.GetFocusedElement()
			if focus and (focus.CurrentProcessId != self.pid or self.isInside(focus, dlg) or self.inPopup(focus)):
				return  # fokus zgłoszony poprawnie (także w rozwiniętej liście) — NVDA przeczyta go sam
			el = self.find(dlg, lambda e: e.CurrentHasKeyboardFocus, maxDepth=12)
		except comtypes.COMError:
			return
		if el:
			say(self.describe(el))

	def describe(self, el):
		t = el.CurrentControlType
		text = self.buttonName(el) if t in BUTTON_TYPES else (el.CurrentName or "")
		role = {50000: "przycisk", 50002: "pole wyboru", 50013: "przycisk opcji", 50003: "lista rozwijana",
			50004: "pole edycji", 50007: "element listy", 50008: "lista", 50024: "element drzewa"}.get(t, "")
		extra = ""
		try:
			if t in (50002, 50013):
				pat = el.GetCurrentPattern(UIA.UIA_TogglePatternId)
				if pat:
					extra = "zaznaczone" if pat.QueryInterface(UIA.IUIAutomationTogglePattern).CurrentToggleState == 1 else "niezaznaczone"
			elif t in (50003, 50004):
				pat = el.GetCurrentPattern(UIA.UIA_ValuePatternId)
				if pat:
					extra = pat.QueryInterface(UIA.IUIAutomationValuePattern).CurrentValue or ""
			if not el.CurrentIsEnabled:
				extra = (extra + " niedostępny").strip()
		except comtypes.COMError:
			pass
		return " ".join(p for p in (text, role, extra) if p)

	def inPopup(self, el):
		"""Czy element leży w rozwiniętej liście / menu (osobne okno najwyższego poziomu)."""
		walker = self.uia.ControlViewWalker
		root = self.uia.GetRootElement()
		for _ in range(30):
			parent = walker.GetParentElement(el)
			if not parent or self.uia.CompareElements(parent, root):
				return self.isPopup(el)
			el = parent
		return False

	def taskSelectionCount(self):
		"""Po zaznaczeniu odcinka czyta licznik okna pobierania („Wybrano 2 z 19”), jeśli się zmienił."""
		dlg = self.activeDialog()
		if not dlg:
			return
		el = self.find(dlg, lambda e: (e.CurrentAutomationId or "").endswith("widget_downloadText.label_artist"))
		if not el:
			return
		text = (el.CurrentName or "").strip()
		if text and text != self._lastCount:
			self._lastCount = text
			say(text)

	def isInside(self, el, ancestor):
		walker = self.uia.ControlViewWalker
		for _ in range(30):
			if not el:
				return False
			if self.uia.CompareElements(el, ancestor):
				return True
			el = walker.GetParentElement(el)
		return False

	# --- polecenia ze skrótów ---
	def taskStatus(self):
		status, queueText, enabled = self.readState(force=True)
		parts = [p for p in (status, queueText) if p]
		if enabled is True:
			parts.append("przycisk Pobierz wideo aktywny")
		elif enabled is False:
			parts.append("przycisk Pobierz wideo nieaktywny")
		say(". ".join(parts) if parts else "Brak paska stanu pobierania na tym ekranie. Otwórz stronę główną i stronę z filmem.")

	def taskDownload(self):
		btn = self.operateButton()
		if not btn:
			say("Przycisk Pobierz wideo jest niedostępny. Otwórz w przeglądarce StreamFab stronę z filmem.")
			return
		if not btn.CurrentIsEnabled:
			status = self.readState(force=True)[0]
			say("Przycisk Pobierz wideo nieaktywny. " + (status or ""))
			return
		self.press(btn)
		say("Pobierz wideo")

	def press(self, el):
		"""Naciska element. Invoke wykonujemy w osobnym wątku, bo Qt nie wraca z niego,
		dopóki otwarte przez przycisk okno modalne jest otwarte."""
		try:
			pat = el.GetCurrentPattern(UIA.UIA_InvokePatternId)
			inv = pat.QueryInterface(UIA.IUIAutomationInvokePattern) if pat else None
		except comtypes.COMError:
			inv = None
		if not inv:
			self.click(el)
			return

		def run():
			comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
			try:
				inv.Invoke()
			except comtypes.COMError:
				pass  # przekroczony czas oczekiwania przy oknie modalnym — kliknięcie i tak zadziałało
			finally:
				comtypes.CoUninitialize()
		threading.Thread(target=run, daemon=True).start()
		time.sleep(0.3)

	def click(self, el):
		r = el.CurrentBoundingRectangle
		x, y = (r.left + r.right) // 2, (r.top + r.bottom) // 2
		user32 = ctypes.windll.user32
		old = ctypes.wintypes.POINT()
		user32.GetCursorPos(ctypes.byref(old))
		user32.SetCursorPos(x, y)
		user32.mouse_event(0x0002, 0, 0, 0, 0)  # lewy w dół
		user32.mouse_event(0x0004, 0, 0, 0, 0)  # lewy w górę
		time.sleep(0.05)
		user32.SetCursorPos(old.x, old.y)

	def taskAddress(self):
		main = self.mainWindow()
		edit = main and self.find(main, lambda e: e.CurrentClassName == ADDRESS_CLASS)
		if not edit:
			say("Pole adresu jest niedostępne. Przejdź do strony głównej StreamFab.")
			return
		edit.SetFocus()

	# --- okna dialogowe ---
	def activeDialog(self):
		"""Najwyżej położone widoczne okno dialogowe StreamFab (bez okna głównego i przycisku pobierania)."""
		found = None
		for w in self.topWindows():
			try:
				aid = w.CurrentAutomationId or ""
				if w.CurrentIsOffscreen or aid.endswith(".pushButton_operate") or self.isPopup(w):
					continue
				if aid == "StreamMainWnd":
					for ch in self.children(w):
						if ch.CurrentControlType == WINDOW_TYPE and not ch.CurrentIsOffscreen \
								and not (ch.CurrentAutomationId or "").endswith(".pushButton_operate") \
								and not self.isPopup(ch):
							found = ch
				else:
					found = w
			except comtypes.COMError:
				continue
		return found

	@staticmethod
	def isPopup(el):
		"""Rozwinięte listy, menu kontekstowe i podpowiedzi to nie okna dialogowe."""
		cls = el.CurrentClassName or ""
		return any(p in cls for p in POPUP_CLASSES)

	def dialogButtons(self, dlg):
		return self.collect(dlg, lambda e: e.CurrentControlType in BUTTON_TYPES and e.CurrentIsEnabled)

	def buttonName(self, el):
		name = el.CurrentName or ""
		if not name:
			last = self.last(el)
			name = NAMES.get(last) or humanize(last)
		return name

	def taskDialogButton(self, groups, names, label):
		dlg = self.activeDialog()
		if not dlg:
			say("Brak otwartego okna dialogowego")
			return
		buttons = self.dialogButtons(dlg)
		# grupy przeszukujemy po kolei: najpierw właściwe przyciski, potem zastępcze (np. Zamknij zamiast Anuluj)
		for ids in groups:
			for b in buttons:
				if self.last(b) in ids or (ids is groups[0] and (b.CurrentName or "").strip().lower() in names):
					nm = self.buttonName(b)
					self.press(b)
					say(nm)
					return
		say("W tym oknie nie ma przycisku " + label + ". Użyj Ctrl+Shift+strzałek, żeby przejrzeć przyciski.")

	def taskCycle(self, step):
		dlg = self.activeDialog()
		if not dlg:
			say("Brak otwartego okna dialogowego")
			return
		buttons = self.dialogButtons(dlg)
		if not buttons:
			say("Brak przycisków w oknie")
			return
		key = (dlg.CurrentAutomationId, dlg.CurrentName, len(buttons))
		idx = self._cycle[1] if self._cycle and self._cycle[0] == key else (-1 if step > 0 else len(buttons))
		idx = (idx + step) % len(buttons)
		self._cycle = (key, idx)
		say("%s, %d z %d" % (self.buttonName(buttons[idx]), idx + 1, len(buttons)))

	def taskPressCurrent(self):
		dlg = self.activeDialog()
		if not dlg or not self._cycle:
			say("Najpierw wybierz przycisk Ctrl+Shift+strzałką")
			return
		buttons = self.dialogButtons(dlg)
		key = (dlg.CurrentAutomationId, dlg.CurrentName, len(buttons))
		if self._cycle[0] != key or self._cycle[1] >= len(buttons):
			say("Okno się zmieniło. Wybierz przycisk ponownie Ctrl+Shift+strzałką")
			self._cycle = None
			return
		b = buttons[self._cycle[1]]
		nm = self.buttonName(b)
		self.press(b)
		say(nm)

	def taskReadDialog(self, dlg=None, auto=False):
		dlg = dlg or self.activeDialog()
		if not dlg:
			say("Brak otwartego okna dialogowego")
			return
		elements = self.collect(dlg, lambda e: e.CurrentControlType in (TEXT_TYPE, EDIT_TYPE))
		if not elements:
			time.sleep(0.6)  # okno jeszcze się rozwija (animacja) — próbujemy raz jeszcze
			elements = self.collect(dlg, lambda e: e.CurrentControlType in (TEXT_TYPE, EDIT_TYPE))
		texts = []
		for el in elements:
			try:
				if el.CurrentControlType == TEXT_TYPE:
					t = (el.CurrentName or "").strip()
				else:
					v = el.GetCurrentPattern(UIA.UIA_ValuePatternId).QueryInterface(UIA.IUIAutomationValuePattern).CurrentValue
					t = "pole %s: %s" % (el.CurrentName or NAMES.get(self.last(el), ""), v or "puste")
			except comtypes.COMError:
				continue
			if t and t not in texts:
				texts.append(t)
		title = (dlg.CurrentName or "").strip()
		texts = [t for t in texts if t != title]
		title = DIALOG_TITLES.get(dlg.CurrentClassName) or DIALOG_TITLES.get(title) or ("Okno " + (title or "bez nazwy"))
		if auto and len(texts) > MAX_AUTO_TEXTS:
			say("%s. Ctrl+Shift+R czyta jego treść." % title)
			return
		say(". ".join([title] + texts))


class AppModule(appModuleHandler.AppModule):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.worker = Worker(self.processID)
		self.worker.onDialogChange = self._setDialogGestures
		self.worker.start()
		self._dialogGestures = False
		self._lastStateEvent = 0.0
		self._films = []
		self._filmsStamp = None

	def terminate(self):
		self.worker.stop()
		super().terminate()

	# Klawisze nawigacji przechwytujemy tylko wtedy, gdy otwarte jest okno StreamFab,
	# żeby nie przeszkadzać trybowi przeglądania na stronach WWW.
	def _setDialogGestures(self, on):
		if on == self._dialogGestures:
			return
		self._dialogGestures = on
		for g, name in DIALOG_GESTURES.items():
			if on:
				self.bindGesture(g, name)
			else:
				try:
					self.removeGestureBinding(g)
				except LookupError:
					pass

	def script_passNavKey(self, gesture):
		gesture.send()
		core.callLater(250, self._syncFocus)
		self.worker.tasks.put(self.worker.taskHiddenFocus)

	def _focusedItem(self):
		"""Element listy/drzewa, który naprawdę ma fokus klawiatury w StreamFab (świeżo z UIA)."""
		try:
			h = UIAHandler.handler
			el = h.clientObject.GetFocusedElementBuildCache(h.baseCacheRequest)
			obj = NVDAObjects.UIA.UIA(UIAElement=el) if el else None
		except Exception:
			return None
		if not obj or obj.processID != self.processID or obj.role not in ITEM_ROLES:
			return None
		return obj

	def _syncFocus(self):
		"""Qt w listach i drzewach (odcinki, języki) czasem nie zgłasza przejścia na nowy element,
		więc NVDA czyta stary albo nic. Wtedy sami podajemy NVDA właściwy element."""
		obj = self._focusedItem()
		if obj and obj != api.getFocusObject():
			eventHandler.queueEvent("gainFocus", obj)
		return obj

	@staticmethod
	def _checked(obj):
		try:
			states = obj.states
		except Exception:
			return None
		if controlTypes.State.CHECKABLE not in states and controlTypes.State.CHECKED not in states:
			return None
		return controlTypes.State.CHECKED in states

	def script_toggleItem(self, gesture):
		"""Spacja na odcinku lub języku: Qt zmienia zaznaczenie bez komunikatu, więc go dopowiadamy."""
		focus = api.getFocusObject()
		before = self._checked(focus) if focus.role in ITEM_ROLES else None
		pressed = time.monotonic()
		gesture.send()
		core.callLater(250, self._afterToggle, before, pressed)

	def _afterToggle(self, before, pressed):
		focus = api.getFocusObject()
		obj = self._focusedItem()
		if not obj:
			return
		if obj != focus:
			eventHandler.queueEvent("gainFocus", obj)  # NVDA przeczyta element razem ze stanem
		else:
			after = self._checked(obj)
			if after is not None and before is not None and after != before and self._lastStateEvent < pressed:
				ui.message("zaznaczone" if after else "niezaznaczone")
		if obj.role == controlTypes.Role.TREEVIEWITEM:
			self.worker.tasks.put(self.worker.taskSelectionCount)

	def event_stateChange(self, obj, nextHandler):
		if obj == api.getFocusObject():
			self._lastStateEvent = time.monotonic()
		nextHandler()

	def films(self):
		"""Lista pobranych filmów, wczytywana ponownie, gdy pliki programu się zmienią."""
		try:
			stamp = tuple(sorted((e.name, e.stat().st_mtime) for e in os.scandir(LOCALDATA) if e.is_file()))
		except OSError:
			stamp = None
		if stamp != self._filmsStamp:
			self._filmsStamp = stamp
			try:
				self._films = readDownloadedFilms()
			except Exception:
				log.debugWarning("StreamFab dostęp: nie udało się odczytać listy pobranych", exc_info=True)
				self._films = []
		return self._films

	def event_NVDAObject_init(self, obj):
		aid = getattr(obj, "UIAAutomationId", None)
		if aid is None:
			return
		role = obj.role
		if role in ITEM_ROLES and obj.name:
			self._cleanItem(obj)
			return
		if not aid:
			if obj.name:
				return
			if role == controlTypes.Role.TAB:
				# Ostatnia, pusta karta w pasku kart przeglądarki to przycisk nowej karty.
				obj.name = "Nowa karta"
			elif role == controlTypes.Role.TREEVIEWITEM:
				self._nameFilmRow(obj)
			elif role in (controlTypes.Role.COMBOBOX, controlTypes.Role.EDITABLETEXT):
				self._nameFromLabel(obj)
			return
		if not aid.startswith("StreamMainWnd"):
			return
		last = aid.rsplit(".", 1)[-1]
		if last in FORCE_NAMES:
			obj.name = FORCE_NAMES[last]
			return
		if last == "treeView" and ".pageTreeView." in aid:
			obj.name = "Lista odcinków. Spacja zaznacza, strzałka w prawo rozwija sezon"
			return
		if last == "pushButton_operate":
			obj.name = NAMES[last]
			obj.role = controlTypes.Role.BUTTON
			return
		if obj.name:
			return
		if last in NAMES:
			obj.name = NAMES[last]
		elif last == "lineEdit" and aid.endswith(".widgetEdit.lineEdit"):
			obj.name = "Adres strony"
		elif role in (controlTypes.Role.COMBOBOX, controlTypes.Role.EDITABLETEXT):
			if not self._nameFromLabel(obj):
				obj.name = humanize(last)
		elif role in NAMED_ROLES:
			obj.name = humanize(last)

	@staticmethod
	def _cleanItem(obj):
		"""Odcinki i języki: bez angielskich dopisków stanu, z czasem trwania i polską nazwą języka."""
		name = _STATE_SUFFIX.sub("", obj.name).strip()
		if obj.role == controlTypes.Role.TREEVIEWITEM:
			if _DURATION.match(name):
				name = "czas trwania " + name
			else:
				try:
					nxt = obj.next
					if nxt and nxt.role == controlTypes.Role.TREEVIEWITEM and _DURATION.match((nxt.name or "").strip()):
						name = "%s, %s" % (name, nxt.name.strip())
				except Exception:
					pass
		elif obj.role == controlTypes.Role.LISTITEM:
			name = _LANG_WORD.sub(lambda m: LANGUAGES[m.group(1)], name)
		if name != obj.name:
			obj.name = name

	@staticmethod
	def _nameFromLabel(obj):
		"""Nazwa pola z tekstu stojącego tuż przed nim (np. „Po każdych”)."""
		try:
			prev = obj.previous
			if prev and prev.role == controlTypes.Role.STATICTEXT and prev.name and prev.name.strip():
				obj.name = prev.name.strip()
				return True
		except Exception:
			pass
		return False

	def _nameFilmRow(self, obj):
		"""Wiersze listy pobranych są rysowane bez tekstu — nazwę bierzemy z plików danych programu."""
		try:
			parentId = getattr(obj.parent, "UIAAutomationId", "") or ""
		except Exception:
			return
		if not parentId.endswith("treeview_task_queue"):
			return
		try:
			row = obj._getUIACacheablePropertyValue(UIA.UIA_GridItemRowPropertyId)
		except Exception:
			row = 0
		films = self.films()
		if isinstance(row, int) and 0 <= row < len(films):
			title, site, path = films[row]
			obj.name = "%s, %s" % (title, site)
			obj.description = "Ctrl+Shift+L: odtwarzanie i folder"
		else:
			obj.name = "Pobrany film %s. Ctrl+Shift+L: lista pobranych" % ((row + 1) if isinstance(row, int) else "")

	@script(description="Naciska przycisk Pobierz wideo", category=CATEGORY, gesture="kb:control+shift+d")
	def script_download(self, gesture):
		self.worker.tasks.put(self.worker.taskDownload)

	@script(description="Czyta stan pobierania i kolejkę zadań", category=CATEGORY, gesture="kb:control+shift+s")
	def script_status(self, gesture):
		self.worker.tasks.put(self.worker.taskStatus)

	@script(description="Przenosi fokus do pola adresu przeglądarki StreamFab", category=CATEGORY, gesture="kb:control+l")
	def script_address(self, gesture):
		self.worker.tasks.put(self.worker.taskAddress)

	@script(description="Włącza lub wyłącza ogłaszanie zmian stanu i nowych okien", category=CATEGORY, gesture="kb:control+shift+a")
	def script_toggleAnnounce(self, gesture):
		self.worker.autoAnnounce = not self.worker.autoAnnounce
		ui.message("Ogłaszanie włączone" if self.worker.autoAnnounce else "Ogłaszanie wyłączone")

	@script(description="Otwiera listę pobranych filmów (odtwarzanie, folder)", category=CATEGORY, gesture="kb:control+shift+l")
	def script_films(self, gesture):
		self._filmsStamp = None
		films = self.films()
		gui.mainFrame.prePopup()
		d = FilmsDialog(gui.mainFrame, films)
		d.Show()
		d.Raise()
		gui.mainFrame.postPopup()

	@script(description="Naciska OK w otwartym oknie dialogowym", category=CATEGORY, gesture="kb:control+shift+o")
	def script_dialogOk(self, gesture):
		self.worker.tasks.put(lambda: self.worker.taskDialogButton((OK_BUTTONS,), OK_NAMES, "OK"))

	@script(description="Naciska Anuluj (lub Zamknij) w otwartym oknie dialogowym", category=CATEGORY, gesture="kb:control+shift+c")
	def script_dialogCancel(self, gesture):
		self.worker.tasks.put(lambda: self.worker.taskDialogButton((CANCEL_BUTTONS, CLOSE_BUTTONS), CANCEL_NAMES, "Anuluj"))

	@script(description="Następny przycisk w oknie dialogowym", category=CATEGORY, gesture="kb:control+shift+rightArrow")
	def script_nextButton(self, gesture):
		self.worker.tasks.put(lambda: self.worker.taskCycle(1))

	@script(description="Poprzedni przycisk w oknie dialogowym", category=CATEGORY, gesture="kb:control+shift+leftArrow")
	def script_prevButton(self, gesture):
		self.worker.tasks.put(lambda: self.worker.taskCycle(-1))

	@script(description="Naciska wybrany przycisk okna dialogowego", category=CATEGORY, gesture="kb:control+shift+enter")
	def script_pressButton(self, gesture):
		self.worker.tasks.put(self.worker.taskPressCurrent)

	@script(description="Czyta treść otwartego okna dialogowego", category=CATEGORY, gesture="kb:control+shift+r")
	def script_readDialog(self, gesture):
		self.worker.tasks.put(self.worker.taskReadDialog)

	@script(description="Czyta listę skrótów dodatku StreamFab dostęp", category=CATEGORY, gesture="kb:control+shift+h")
	def script_help(self, gesture):
		ui.message(
			"Ctrl+Shift+D: pobierz wideo. Ctrl+Shift+S: stan pobierania. Ctrl+L: pole adresu. "
			"Ctrl+Shift+L: lista pobranych filmów. Ctrl+Shift+A: ogłaszanie zmian i nowych okien. "
			"W oknach dialogowych: Ctrl+Shift+O: OK. Ctrl+Shift+C: Anuluj lub Zamknij. "
			"Ctrl+Shift+strzałka w prawo lub w lewo: przeglądanie przycisków. Ctrl+Shift+Enter: naciśnij wybrany. "
			"Ctrl+Shift+R: przeczytaj okno. W oknie pobierania serialu Spacja zaznacza odcinek lub język. "
			"Ctrl+Shift+H: ta pomoc."
		)

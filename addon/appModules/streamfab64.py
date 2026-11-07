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
from html import escape

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
	"m_lineEditEmail": "E-mail",
	"m_lineEditPassword": "Hasło",
	"pushButtonLeftClose": "Zamknij",
	"tableWidgetLicense": "Tabela licencji",
}
# Angielskie napisy okna logowania.
TRANSLATE = {
	"LOGIN": "Zaloguj",
	"SIGN UP": "Zarejestruj",
	"Sign in with Google": "Zaloguj przez Google",
	"or": "lub",
}
# Napisy okna logowania, które działają jak linki (to zwykłe etykiety, więc dodatek klika je myszą).
LINK_LABELS = {
	"label_googleText": "Zaloguj przez Google",
	"labelNoAccount": "Nie masz konta? Zarejestruj tutaj",
	"labelForgot": "Zapomniane hasło?",
}
# Etykiety z komunikatem stanu w oknach (np. „Weryfikowanie informacji o koncie”) — ich zmiany ogłaszamy.
MESSAGE_LABELS = ("m_labelMessage", "labelMessage", "label_message", "label_errorTip", "label_tip")
# Okna, które zostają pod spodem, gdy StreamFab otworzy kolejne (np. Licencję po zalogowaniu).
# Okno o niższej wadze ustępuje każdemu innemu.
BACKGROUND_RANK = {"WebSitePopupDlg": 0, "QRegister": 1}
# Początki AutomationId okien StreamFab, w których nadajemy nazwy elementom.
OWN_PREFIXES = ("StreamMainWnd", "CFabDialogClass")
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
# Kody języków, którymi lista wyboru pokazuje wybrane ścieżki (np. "en,pl").
LANG_CODES = {
	"ar": "arabski", "bg": "bułgarski", "ca": "kataloński", "cs": "czeski", "da": "duński", "de": "niemiecki",
	"el": "grecki", "en": "angielski", "es": "hiszpański", "et": "estoński", "fi": "fiński", "fil": "filipiński",
	"fr": "francuski", "he": "hebrajski", "hi": "hindi", "hr": "chorwacki", "hu": "węgierski", "id": "indonezyjski",
	"is": "islandzki", "it": "włoski", "ja": "japoński", "ko": "koreański", "lt": "litewski", "lv": "łotewski",
	"ms": "malajski", "nb": "norweski", "no": "norweski", "nl": "niderlandzki", "pl": "polski", "pt": "portugalski",
	"ro": "rumuński", "ru": "rosyjski", "sk": "słowacki", "sl": "słoweński", "sr": "serbski", "sv": "szwedzki",
	"ta": "tamilski", "te": "telugu", "th": "tajski", "tl": "tagalski", "tr": "turecki", "uk": "ukraiński",
	"vi": "wietnamski", "yue": "kantoński", "zh": "chiński", "cmn": "mandaryński",
}


def langValue(value):
	"""„en,pl,pl” → „angielski, polski (2)”; nieznane kody zostają bez zmian."""
	order, counts = [], {}
	for code in (value or "").split(","):
		code = code.strip()
		if not code:
			continue
		base = code.replace("_", "-").split("-")[0].lower()
		name = LANG_CODES.get(base, code)
		if name not in counts:
			order.append(name)
			counts[name] = 0
		counts[name] += 1
	if not order:
		return "nic nie wybrano"
	return ", ".join(n if counts[n] == 1 else "%s (%d)" % (n, counts[n]) for n in order)


_LANG_WORD = re.compile(r"\b(" + "|".join(sorted((re.escape(k) for k in LANGUAGES), key=len, reverse=True)) + r")\b")
# Klawisze przechwytywane, gdy otwarte jest okno StreamFab (gest: nazwa skryptu).
DIALOG_GESTURES = {
	"kb:tab": "passNavKey",
	"kb:shift+tab": "passNavKey",
	"kb:upArrow": "passNavKey",
	"kb:downArrow": "passNavKey",
	"kb:space": "toggleItem",
	"kb:escape": "escape",
}
# Dodatkowe klawisze przechwytywane tylko w oknie Licencja (Tab i Spację obsługują skrypty z DIALOG_GESTURES).
LICENSE_GESTURES = ("kb:enter", "kb:numpadEnter")
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
CLOSE_BUTTONS = ("pushButtonLeftClose", "pushButton_dialogClose", "pushButton_close", "pushButtonClose", "btn_close")
OK_NAMES = ("ok", "tak", "yes", "potwierdź", "confirm", "zapisz", "save")
CANCEL_NAMES = ("cancel", "anuluj", "nie", "no")
WINDOW_TYPE = 50032
DATAITEM_TYPE = 50029
HEADER_TYPE = 50034
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
	"QRegister": "Okno logowania StreamFab",
	"WebSitePopupDlg": "Okno reklamy StreamFab, Ctrl+Shift+C zamyka",
	"LicenseInfoOptionsDlg": "Okno Licencja",
}
# --- okno Licencja (LicenseInfoOptionsDlg) ---
LICENSE_CLASS = "LicenseInfoOptionsDlg"
# Własny cykl Tab: (ostatni człon AutomationId, rodzaj, polska nazwa, rola mówiona).
LICENSE_TAB = (
	("tableWidgetLicense", "table", "Tabela licencji", ""),
	("labelprivilege", "offer", "Oferta Fab365", ""),
	("pushButton_upgrade", "buy", "Subskrybuj teraz", "przycisk, otwiera stronę zakupu"),
	("checkBoxShowAgain", "check", "Nie pokazuj ponownie", "pole wyboru"),
	("pushButtonStart", "button", "Rozpocznij StreamFab", "przycisk, Ctrl+Shift+O"),
	("pushButtonClose", "button", "Zamknij", "przycisk, Ctrl+Shift+C"),
)
# Przyciski, które otwierają stronę zakupu — naciskamy je dopiero po potwierdzeniu.
BUY_BUTTONS = ("pushButton_upgrade",)
BUY_CONFIRM_SECONDS = 4.0
LICENSE_HINT = ("Tab i Shift+Tab przechodzą po elementach okna, Enter lub Spacja wykonuje akcję; "
	"na tabeli licencji Enter otwiera pełną listę do czytania strzałkami. "
	"Ctrl+Shift+O: Rozpocznij StreamFab. Ctrl+Shift+C: Zamknij. Ctrl+Shift+R: przeczytaj okno. Ctrl+Shift+H: pomoc.")
# Tekst oferty Fab365 (StreamFab pokazuje go po angielsku), tłumaczony wiersz po wierszu.
OFFER_TRANSLATE = {
	"Subscribe to Fab365 for all StreamFab software and services!":
		"Subskrybuj Fab365, aby mieć wszystkie programy i usługi StreamFab.",
	"Unlock future products & Dual-OS.": "Odblokowanie przyszłych produktów i obu systemów, Windows i Mac.",
	"Enjoy multi-device support & Extended Download Services.":
		"Obsługa wielu urządzeń i rozszerzone usługi pobierania.",
}
# Plik rejestracji StreamFab: RegInfo="1|310:8260744964|308:...|VP:-1|..." (numer opcji : koniec licencji, czas uniksowy).
REG_RECORD = os.path.expandvars(r"%APPDATA%\StreamFab\StreamFab\regRecord\localuse.rec")
# Ikona „ptaszka” przed stanem licencji OCR czyta jako osobny znak.
_OCR_ICON = ("@", "©", "®", "O", "o", "0", "Q", "G", "e", "•", "*", "V", "v", "✓", "✔", "√", "(v)")
_OCR_FIXES = ((re.compile(r"Down[il1|]oad"), "Download"), (re.compile(r"\s+([,.:;])"), r"\1"))
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


def showText(lines, title):
	"""Okno do czytania strzałkami (w głównym wątku NVDA); każda linia osobnym akapitem."""
	html = "".join("<p>%s</p>" % escape(ln) for ln in lines)
	try:
		ui.browseableMessage(html, title, isHtml=True, closeButton=True, copyButton=True)
	except TypeError:  # NVDA starsze niż 2025.1 nie mają przycisków
		ui.browseableMessage(html, title, True)


def plural(n, one, few, many):
	if n == 1:
		return "%d %s" % (n, one)
	if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
		return "%d %s" % (n, few)
	return "%d %s" % (n, many)


def readRegLicenses():
	"""Opis licencji z pliku rejestracji StreamFab („70 opcji z licencją, bezterminowo”) albo pusty tekst."""
	try:
		with open(REG_RECORD, "r", encoding="utf-8", errors="replace") as f:
			data = f.read()
	except OSError:
		return ""
	m = re.search(r'RegInfo="([^"]*)"', data)
	if not m:
		return ""
	stamps = []
	for part in m.group(1).split("|"):
		key, _, val = part.partition(":")
		if key.isdigit() and val.isdigit():
			stamps.append(int(val))
	if not stamps:
		return ""
	try:
		end = time.gmtime(min(stamps))
		when = "bezterminowo" if end.tm_year >= 2100 else "do %02d.%02d.%d" % (end.tm_mday, end.tm_mon, end.tm_year)
	except (OverflowError, OSError, ValueError):
		when = ""
	text = "według pliku rejestracji %s z licencją" % plural(len(stamps), "opcja", "opcje", "opcji")
	return text + (", " + when if when else "")


def translateOffer(text):
	"""Tekst oferty Fab365 po polsku (nieznane wiersze zostają bez zmian)."""
	out = []
	for line in (text or "").splitlines():
		line = line.strip().lstrip("-•").strip()
		if line:
			out.append(OFFER_TRANSLATE.get(line, line))
	return " ".join(out)


def priceText(text):
	"""„$129.99” → „129,99 USD”."""
	return re.sub(r"\$\s*(\d+)[.,](\d+)", r"\1,\2 USD", (text or "").strip())


class _MONITORINFO(ctypes.Structure):
	_fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", ctypes.wintypes.RECT),
		("rcWork", ctypes.wintypes.RECT), ("dwFlags", ctypes.c_ulong)]


# Własne wskaźniki funkcji user32 (z typami dla 64 bitów), żeby nie zmieniać ustawień innych dodatków.
_user32 = ctypes.WinDLL("user32")
_user32.MonitorFromWindow.restype = ctypes.c_void_p
_user32.MonitorFromWindow.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
_user32.GetMonitorInfoW.argtypes = (ctypes.c_void_p, ctypes.POINTER(_MONITORINFO))
_user32.GetAncestor.restype = ctypes.c_void_p
_user32.GetAncestor.argtypes = (ctypes.c_void_p, ctypes.c_uint)
_user32.GetWindowRect.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.wintypes.RECT))
_user32.SetWindowPos.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
	ctypes.c_int, ctypes.c_int, ctypes.c_uint)


def rootWindow(hwnd):
	return _user32.GetAncestor(hwnd, 2) or hwnd  # GA_ROOT


def workArea(hwnd):
	"""Obszar roboczy monitora z oknem (bez paska zadań): (lewo, góra, prawo, dół)."""
	mi = _MONITORINFO()
	mi.cbSize = ctypes.sizeof(mi)
	mon = _user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
	if not mon or not _user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
		return None
	r = mi.rcWork
	return (r.left, r.top, r.right, r.bottom)


def callMain(func, timeout=5.0):
	"""Wykonuje funkcję w głównym wątku NVDA i czeka na wynik (z wątku workera)."""
	done = threading.Event()
	box = {}

	def run():
		try:
			box["r"] = func()
		except Exception as e:
			box["e"] = e
		finally:
			done.set()
	queueHandler.queueFunction(queueHandler.eventQueue, run)
	if not done.wait(timeout):
		raise RuntimeError("NVDA nie odpowiada")
	if "e" in box:
		raise box["e"]
	return box.get("r")


def ocrWords(left, top, width, height, timeout=10.0):
	"""Rozpoznaje tekst prostokąta ekranu wbudowanym OCR Windows w NVDA.
	Zwraca listę słów (lewo, góra, prawo, dół, tekst) we współrzędnych ekranu."""
	from contentRecog import RecogImageInfo, recogUi, uwpOcr
	ocr = uwpOcr.UwpOcr()
	info = RecogImageInfo.createFromRecognizer(left, top, width, height, ocr)
	# recogUi._captureImage obsługuje też kurtynę ekranową (przechwytywanie Windows Graphics Capture)
	pixels = callMain(lambda: recogUi._captureImage(info))
	done = threading.Event()
	box = {}

	def onResult(result):
		box["r"] = result
		done.set()
	callMain(lambda: ocr.recognize(pixels, info, onResult))
	if not done.wait(timeout):
		raise RuntimeError("OCR nie odpowiedział")
	result = box.get("r")
	if isinstance(result, Exception):
		raise result
	words = []
	for line in getattr(result, "data", None) or []:
		for w in line:
			try:
				x = info.convertXToScreen(w["x"])
				y = info.convertYToScreen(w["y"])
				words.append((x, y, x + info.convertWidthToScreen(w["width"]),
					y + info.convertHeightToScreen(w["height"]), w["text"]))
			except (KeyError, TypeError):
				continue
	return words


def cleanCell(text, stateColumn=False):
	"""Poprawia typowe błędy OCR w komórce tabeli licencji."""
	parts = text.split()
	if stateColumn and len(parts) > 1 and parts[0] in _OCR_ICON:
		parts = parts[1:]
	text = " ".join(parts)
	for rx, rep in _OCR_FIXES:
		text = rx.sub(rep, text)
	return text.strip()


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


# --- kolejka pobierania (taskdata: obiekty JSON jeden po drugim) i log StreamFab ---
TASKDATA = os.path.expandvars(r"%APPDATA%\StreamFab\StreamFab\taskdata")
SF_LOG = os.path.expanduser(r"~\Documents\StreamFab\StreamFab\Log\StreamFab.log")
_RE_BEGIN = re.compile(r"beginDownloadItem.*?strID: \"([0-9a-f-]{36})\"")
_RE_FINISH = re.compile(r"emit sig_downloadFinished: success :(\d), .*?strID :([0-9a-f-]{36}), nErrorCode :(-?\d+), "
	r"strErrorTextForTaskQueue :(.*?), strOutPath :(.*?)\"\s*$")


def readQueueTasks():
	"""Zwraca listę słowników zadań (id, tytuł, sezon, czas, serwis) z plików kolejki StreamFab."""
	import json
	tasks = []
	try:
		with open(os.path.join(TASKDATA, "task_index"), "r", encoding="utf-8", errors="replace") as f:
			sites = [s.strip() for s in f.read().splitlines() if s.strip()]
	except OSError:
		sites = []
	dec = json.JSONDecoder()
	for site in sites:
		try:
			with open(os.path.join(TASKDATA, site), "r", encoding="utf-8", errors="replace") as f:
				data = f.read()
		except OSError:
			continue
		i, n = 0, len(data)
		while i < n:
			while i < n and data[i] in " \r\n\t,":
				i += 1
			if i >= n:
				break
			try:
				obj, i = dec.raw_decode(data, i)
			except ValueError:
				break
			if isinstance(obj, dict) and obj.get("strID"):
				tasks.append({
					"id": obj.get("strID", ""),
					"title": obj.get("strTitle") or obj.get("strSeasonTitle") or "bez tytułu",
					"time": obj.get("strTotaltime", ""),
					"site": site,
				})
	return tasks


def _fileTitle(path):
	return os.path.splitext(os.path.basename(path.replace("\\", "/")))[0].replace("_", " ") if path else ""


class QueueDialog(wx.Dialog):
	"""Dostępna lista kolejki pobierania z tytułami i stanem (z plików i logu StreamFab)."""

	def __init__(self, parent, header, items):
		super().__init__(parent, title="StreamFab — kolejka pobierania")
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(wx.StaticText(self, label=header or "Brak informacji o stanie"), 0, wx.ALL, 5)
		sizer.Add(wx.StaticText(self, label="&Zadania"), 0, wx.ALL, 5)
		self.list = wx.ListBox(self, choices=items or ["Kolejka jest pusta"], size=(700, 300))
		self.list.SetSelection(0)
		sizer.Add(self.list, 1, wx.ALL | wx.EXPAND, 5)
		b = wx.Button(self, wx.ID_CLOSE, "Zamknij")
		b.Bind(wx.EVT_BUTTON, lambda e: self.Destroy())
		sizer.Add(b, 0, wx.ALL, 5)
		self.SetSizerAndFit(sizer)
		self.Bind(wx.EVT_CHAR_HOOK, self.onKey)
		self.list.SetFocus()

	def onKey(self, evt):
		if evt.GetKeyCode() == wx.WXK_ESCAPE:
			self.Destroy()
		else:
			evt.Skip()


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
		self._message = None  # ostatni komunikat stanu okna (np. logowania)
		self.licCur = None  # bieżący element własnego cyklu Tab w oknie Licencja
		self.licRows = None  # odczytane wiersze tabeli licencji: {numer wiersza: tekst}
		self._buyArmed = 0.0  # czas pierwszego naciśnięcia przycisku zakupu (potwierdzenie)
		self.onDialogChange = None  # wywoływane w głównym wątku NVDA: (czy jest otwarte okno, klasa okna)
		self.busyName = None  # diagnostyka: co wątek właśnie robi
		self.busySince = None
		# śledzenie pobierania z logu StreamFab
		self.logPos = None
		self.titles = {}  # id zadania -> tytuł
		self.taskStamp = None
		self.results = {}  # id -> (sukces, tekst, tytuł)
		self.finished = []  # ostatnio zakończone w tej sesji: (sukces, tytuł, tekst)
		self.current = None  # (id, czas rozpoczęcia)
		self.tasksCache = []

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
			threading.Thread(target=self.logLoop, name="StreamFabDostepLog", daemon=True).start()
			while self.running:
				try:
					task = self.tasks.get(timeout=1.0)
				except queue.Empty:
					task = None
				self.busyName = getattr(task, "__name__", "?") if task else "poll"
				self.busySince = time.monotonic()
				try:
					if task:
						task()
					else:
						self.poll()
				except Exception:
					log.warning("StreamFab dostęp: błąd UIA", exc_info=True)
					self._labels.clear()
				finally:
					self.busySince = None
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
		# poza stroną główną paska nie ma, a każde szukanie trwa ok. 2,5 s — nie ponawiamy częściej niż co 10 s
		if not self._labels and now - self._lastResolve > (5.0 if force else 10.0):
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
	def refreshTitles(self):
		try:
			stamp = tuple(os.path.getmtime(os.path.join(TASKDATA, f)) for f in os.listdir(TASKDATA) if os.path.isfile(os.path.join(TASKDATA, f)))
		except OSError:
			stamp = None
		if stamp == self.taskStamp:
			return
		self.taskStamp = stamp
		self.tasksCache = readQueueTasks()
		for t in self.tasksCache:
			self.titles[t["id"]] = t["title"]

	def watchLog(self):
		"""Czyta nowe wiersze logu StreamFab i ogłasza początek i koniec pobierania każdego filmu."""
		try:
			size = os.path.getsize(SF_LOG)
		except OSError:
			return
		first = self.logPos is None
		if first:
			self.logPos = max(0, size - 10 * 1024 * 1024)  # historia: ostatnie 10 MB, bez ogłaszania
		elif size < self.logPos:
			self.logPos = 0  # nowy plik logu
		if size == self.logPos:
			return
		self.refreshTitles()
		try:
			with open(SF_LOG, "rb") as f:
				f.seek(self.logPos)
				data = f.read(size - self.logPos)
		except OSError:
			return
		cut = data.rfind(b"\n")
		if cut < 0:
			return
		self.logPos += cut + 1
		for line in data[:cut].decode("utf-8", "replace").splitlines():
			if "beginDownloadItem" not in line and "sig_downloadFinished" not in line:
				continue
			m = _RE_BEGIN.search(line)
			if m:
				tid = m.group(1)
				try:
					started = time.mktime(time.strptime(line[:19], "%Y:%m:%d-%H:%M:%S"))
				except (ValueError, OverflowError):
					started = time.time()
				self.current = (tid, started)
				if not first and self.autoAnnounce:
					say("Pobieranie: " + self.titles.get(tid, "nowy film"))
				continue
			m = _RE_FINISH.search(line)
			if m:
				ok, tid, code, text, path = m.group(1) == "1", m.group(2), m.group(3), m.group(4), m.group(5)
				title = self.titles.get(tid) or _fileTitle(path) or "film"
				self.results[tid] = (ok, text, title)
				if self.current and self.current[0] == tid:
					self.current = None
				if not first:
					self.finished.append((ok, title, text))
					del self.finished[:-30]
					if self.autoAnnounce:
						say(("Pobrano: " + title) if ok else ("Błąd pobierania: %s. %s" % (title, text)))

	def currentProgress(self):
		"""Opis trwającego pobierania: tytuł, czas i megabajty w folderze tymczasowym (outputTemp)."""
		if not self.current:
			return ""
		tid, started = self.current
		self.refreshTitles()
		parts = ["Pobieranie: " + self.titles.get(tid, "film bez znanego tytułu")]
		mins = int(max(0, time.time() - started) // 60)
		parts.append("trwa od %d min" % mins if mins else "trwa od niecałej minuty")
		tmp = None
		try:
			with open(os.path.expandvars(r"%APPDATA%\StreamFab\StreamFab\StreamFab.ini"), "r", encoding="utf-8", errors="replace") as f:
				for line in f:
					if line.startswith("DVDFabTmpDir="):
						tmp = line.split("=", 1)[1].strip()
						break
		except OSError:
			pass
		if tmp:
			base = os.path.join(tmp, "outputTemp")
			total = 0
			try:
				for site in os.listdir(base):
					sd = os.path.join(base, site)
					if not os.path.isdir(sd):
						continue
					for d in os.listdir(sd):
						if d.endswith(tid):
							for root, dirs, files in os.walk(os.path.join(sd, d)):
								for fn in files:
									try:
										total += os.path.getsize(os.path.join(root, fn))
									except OSError:
										pass
			except OSError:
				pass
			if total:
				parts.append("pobrano %d MB" % (total // (1024 * 1024)))
		return ", ".join(parts)

	def logLoop(self):
		"""Osobny wątek: log i pliki kolejki czytamy bez UIA, więc zawieszony StreamFab ich nie blokuje."""
		while self.running:
			try:
				self.watchLog()
			except Exception:
				log.warning("StreamFab dostęp: błąd czytania logu", exc_info=True)
			time.sleep(1.0)

	def taskState(self, t):
		res = self.results.get(t["id"])
		if self.current and self.current[0] == t["id"]:
			return "pobieranie trwa"
		if res:
			return "pobrano" if res[0] else "błąd: " + res[1]
		return "czeka"

	def fileStatus(self):
		"""Stan pobierania tylko z plików i logu StreamFab (bez UIA)."""
		self.refreshTitles()
		parts = []
		prog = self.currentProgress()
		if prog:
			parts.append(prog)
		else:
			parts.append("Nic się teraz nie pobiera")
		states = [self.taskState(t) for t in self.tasksCache]
		if states:
			err = sum(1 for s in states if s.startswith("błąd"))
			wait = sum(1 for s in states if s == "czeka")
			parts.append("W kolejce %d zadań: czeka %d, z błędem %d" % (len(states), wait, err))
		else:
			parts.append("Kolejka pusta")
		if self.finished:
			ok, title, text = self.finished[-1]
			parts.append(("Ostatnio pobrano: " + title) if ok else ("Ostatni błąd: %s. %s" % (title, text)))
		return ". ".join(parts)

	def queueSummary(self):
		"""Nagłówek i wiersze dla okna kolejki pobierania (tylko pliki, bez UIA)."""
		self.taskStamp = None
		header = self.fileStatus()
		items = []
		for t in self.tasksCache:
			stan = self.taskState(t)
			items.append("%s, %s, %s, %s" % (t["title"], t["time"] or "czas nieznany", t["site"], stan))
		for ok, title, text in reversed(self.finished):
			if ok:
				items.append("Zakończone w tej sesji: pobrano %s" % title)
		return header, items

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
			self.watchMessage(dlg)
			return
		self._dialogKey = key
		self._cycle = None
		self._lastCount = None
		self._message = None
		self.licCur = None
		self.licRows = None
		self._buyArmed = 0.0
		cls = key[2] if key else ""
		if self.onDialogChange:
			queueHandler.queueFunction(queueHandler.eventQueue, self.onDialogChange, bool(dlg), cls)
		if not dlg:
			return
		time.sleep(0.4)  # niech okno się dorysuje
		# Nowe okno otwarte pod innym (np. Licencja pod oknem logowania): klawiatura została
		# w starym oknie, więc przenosimy ją do nowego — bez tego nie da się przejść dalej.
		moved = self.bringToFront(dlg, onlyFromBackground=True)
		self.watchMessage(dlg, announce=False)
		if not self.autoAnnounce:
			return
		self.taskReadDialog(dlg, auto=True)
		if moved:
			say("Logowanie czeka na zamknięcie tego okna" if self.hasBackground("QRegister") else "Przeniesiono do tego okna")
		if cls == LICENSE_CLASS:
			return  # fokus stoi w pustej komórce tabeli — nie czytamy jej
		self.taskHiddenFocus(dlg, delay=0)

	def watchMessage(self, dlg, announce=True):
		"""Ogłasza zmiany komunikatu stanu w oknie (np. „Weryfikowanie informacji o koncie”, błąd hasła)."""
		if not dlg:
			return
		try:
			el = self.find(dlg, lambda e: e.CurrentControlType == TEXT_TYPE and self.last(e) in MESSAGE_LABELS)
			text = (el.CurrentName or "").strip().rstrip(".") if el else ""
		except comtypes.COMError:
			return
		prev, self._message = self._message, text
		if announce and text and text != prev and self.autoAnnounce:
			say(text)

	def nativeHandle(self, el):
		try:
			return el.CurrentNativeWindowHandle or 0
		except comtypes.COMError:
			return 0

	def hasBackground(self, cls):
		return any(self.className(d) == cls for d in self.allDialogs())

	@staticmethod
	def className(el):
		try:
			return el.CurrentClassName or ""
		except comtypes.COMError:
			return ""

	def bringToFront(self, dlg, onlyFromBackground=False):
		"""Ustawia okno na wierzchu i daje fokus jego pierwszemu przyciskowi.
		onlyFromBackground: tylko gdy klawiatura jest w oknie, które zostaje pod spodem (logowanie, reklama)."""
		hwnd = self.nativeHandle(dlg)
		fg = winUser.getForegroundWindow()
		if not hwnd or fg == hwnd:
			return False
		if onlyFromBackground:
			try:
				fgEl = self.uia.ElementFromHandle(fg)
			except comtypes.COMError:
				return False
			if not fgEl or fgEl.CurrentProcessId != self.pid or self.className(fgEl) not in BACKGROUND_RANK:
				return False
		user32 = ctypes.windll.user32
		user32.ShowWindow(hwnd, 5)  # SW_SHOW
		user32.SetForegroundWindow(hwnd)
		time.sleep(0.2)
		try:
			target = None
			for b in self.dialogButtons(dlg):
				if b.CurrentIsKeyboardFocusable and b.CurrentControlType in BUTTON_TYPES:
					target = b
					if self.last(b) in CLOSE_BUTTONS or self.last(b) in OK_BUTTONS:
						break
			(target or dlg).SetFocus()
		except comtypes.COMError:
			pass
		return True

	def taskSwitchWindow(self):
		"""Przechodzi do kolejnego otwartego okna StreamFab (np. gdy jedno zasłania drugie)."""
		dialogs = self.allDialogs()
		main = self.mainWindow()
		if main:
			dialogs.insert(0, main)
		if not dialogs:
			say("Brak okien StreamFab")
			return
		fg = winUser.getForegroundWindow()
		handles = [self.nativeHandle(d) for d in dialogs]
		idx = (handles.index(fg) + 1) % len(dialogs) if fg in handles else len(dialogs) - 1
		dlg = dialogs[idx]
		self.bringToFront(dlg)
		if dlg is main:
			say("Okno główne StreamFab, %d z %d" % (idx + 1, len(dialogs)))
		else:
			self.taskReadDialog(dlg, auto=True)
			say("%d z %d" % (idx + 1, len(dialogs)))

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
		log.info("StreamFab dostęp: taskStatus start, etykiety=%d" % len(self._labels))
		status, queueText, enabled = self.readState(force=True)
		log.info("StreamFab dostęp: taskStatus stan=%r kolejka=%r przycisk=%r" % (status, queueText, enabled))
		parts = [p for p in (status, queueText) if p]
		if enabled is True:
			parts.append("przycisk Pobierz wideo aktywny")
		elif enabled is False:
			parts.append("przycisk Pobierz wideo nieaktywny")
		parts.append(self.fileStatus())
		say(". ".join(parts))

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
		if self.last(el) in LINK_LABELS:
			self.click(el)  # etykieta Qt reaguje tylko na kliknięcie myszą
			return
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
	def allDialogs(self):
		"""Widoczne okna dialogowe StreamFab (bez okna głównego i przycisku pobierania), w kolejności drzewa UIA.
		Okno otwarte z innego okna (np. logowanie z reklamy) jest jego dzieckiem i trafia na listę zaraz po nim."""
		found = []

		def usable(el):
			aid = el.CurrentAutomationId or ""
			return el.CurrentControlType == WINDOW_TYPE and not el.CurrentIsOffscreen \
				and not aid.endswith(".pushButton_operate") and not self.isPopup(el)

		for w in self.topWindows():
			try:
				if not usable(w):
					continue
				if w.CurrentAutomationId != "StreamMainWnd":
					found.append(w)
				found.extend(ch for ch in self.children(w) if usable(ch))
			except comtypes.COMError:
				continue
		return found

	def activeDialog(self):
		"""Okno, które teraz czeka na użytkownika: ostatnie z listy, ale okna zostające pod spodem
		(reklama, logowanie w trakcie weryfikacji) ustępują każdemu innemu."""
		found = None
		best = -1
		for d in self.allDialogs():
			rank = BACKGROUND_RANK.get(self.className(d), 9)
			if rank >= best:
				best, found = rank, d
		return found

	@staticmethod
	def isPopup(el):
		"""Rozwinięte listy, menu kontekstowe i podpowiedzi to nie okna dialogowe."""
		cls = el.CurrentClassName or ""
		return any(p in cls for p in POPUP_CLASSES)

	def dialogButtons(self, dlg):
		return self.collect(dlg, lambda e: e.CurrentIsEnabled and (e.CurrentControlType in BUTTON_TYPES
			or (e.CurrentControlType == TEXT_TYPE and self.last(e) in LINK_LABELS)))

	def buttonName(self, el):
		last = self.last(el)
		if last in LINK_LABELS:
			return LINK_LABELS[last] + ", link"
		name = (el.CurrentName or "").strip()
		if not name:
			name = NAMES.get(last) or humanize(last)
		return TRANSLATE.get(name, name)

	def taskDialogButton(self, groups, names, label):
		dlg = self.activeDialog()
		if not dlg:
			say("Brak otwartego okna dialogowego")
			return
		if self.className(dlg) == LICENSE_CLASS:
			# okno Licencja: OK = Rozpocznij StreamFab, Anuluj = Zamknij (bez szukania po nazwach)
			groups = (("pushButtonStart",),) if label == "OK" else (("pushButtonClose",),)
			names = ()
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
		extra = ", otwiera stronę zakupu" if self.last(buttons[idx]) in BUY_BUTTONS else ""
		say("%s%s, %d z %d" % (self.buttonName(buttons[idx]), extra, idx + 1, len(buttons)))

	def confirmBuy(self, key):
		"""Przycisk zakupu naciskamy dopiero przy drugim naciśnięciu w ciągu kilku sekund."""
		now = time.monotonic()
		if self._buyArmed and now - self._buyArmed < BUY_CONFIRM_SECONDS:
			self._buyArmed = 0.0
			return True
		self._buyArmed = now
		say("Uwaga: Subskrybuj teraz otwiera stronę zakupu w przeglądarce. "
			"Naciśnij %s ponownie w ciągu %d sekund, żeby kontynuować." % (key, int(BUY_CONFIRM_SECONDS)))
		return False

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
		if self.last(b) in BUY_BUTTONS and not self.confirmBuy("Ctrl+Shift+Enter"):
			return
		nm = self.buttonName(b)
		self.press(b)
		say(nm)

	def taskReadDialog(self, dlg=None, auto=False):
		dlg = dlg or self.activeDialog()
		if not dlg:
			say("Brak otwartego okna dialogowego")
			return
		if self.className(dlg) == LICENSE_CLASS:
			say(self.licenseSummary(dlg, full=not auto))
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

	# --- okno Licencja ---
	def licenseDialog(self):
		dlg = self.activeDialog()
		return dlg if dlg and self.className(dlg) == LICENSE_CLASS else None

	def licenseElements(self, dlg):
		"""Elementy okna Licencja według ostatniego członu AutomationId."""
		wanted = {k[0] for k in LICENSE_TAB} | {"label_product", "label_license", "label_email",
			"labelNowPrice", "labelOriginPrice", "licenseInfoOverlayScrollBar"}
		out = {}
		for el in self.collect(dlg, lambda e: self.last(e) in wanted):
			out.setdefault(self.last(el), el)
		return out

	@staticmethod
	def elName(els, key):
		el = els.get(key)
		try:
			return (el.CurrentName or "").strip() if el else ""
		except comtypes.COMError:
			return ""

	def licenseRowCount(self, table):
		try:
			pat = table.GetCurrentPattern(UIA.UIA_GridPatternId).QueryInterface(UIA.IUIAutomationGridPattern)
			return int(pat.CurrentRowCount)
		except (comtypes.COMError, AttributeError, ValueError, TypeError):
			return 0

	def toggleText(self, el):
		try:
			pat = el.GetCurrentPattern(UIA.UIA_TogglePatternId).QueryInterface(UIA.IUIAutomationTogglePattern)
			return "zaznaczone" if pat.CurrentToggleState == 1 else "niezaznaczone"
		except (comtypes.COMError, AttributeError, ValueError):
			return "stan nieznany"

	def offerText(self, els):
		text = translateOffer(self.elName(els, "labelprivilege"))
		price = " ".join(p for p in (priceText(self.elName(els, "labelNowPrice")), self.elName(els, "labelOriginPrice")) if p)
		if price:
			text = (text + " Cena: " + price).strip()
		return ("Oferta Fab365: " + text) if text else ""

	def licenseStates(self):
		"""„Dożywotni: 68, Darmowe: 1” z odczytanej tabeli."""
		counts = {}
		for cells in (self.licRows or {}).values():
			st = cells.get(2)
			if st:
				counts[st] = counts.get(st, 0) + 1
		return ", ".join("%s: %d" % (k, v) for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))

	def licenseSummary(self, dlg, full=False):
		els = self.licenseElements(dlg)
		parts = ["Okno Licencja"]
		head = ", ".join(p for p in (self.elName(els, "label_product"), self.elName(els, "label_license"),
			self.elName(els, "label_email")) if p)
		if head:
			parts.append(head)
		table = els.get("tableWidgetLicense")
		n = self.licenseRowCount(table) if table else 0
		if n:
			parts.append("Tabela licencji: " + plural(n, "wiersz", "wiersze", "wierszy"))
		states = self.licenseStates()
		if states:
			parts.append("Stany licencji: " + states)
		reg = readRegLicenses()
		if reg:
			parts.append(reg[:1].upper() + reg[1:])
		if full:
			offer = self.offerText(els)
			if offer:
				parts.append(offer)
			chk = els.get("checkBoxShowAgain")
			if chk:
				parts.append("Nie pokazuj ponownie: " + self.toggleText(chk))
		parts.append(LICENSE_HINT)
		return ". ".join(p.rstrip(". ") for p in parts if p) + "."

	def licenseTabItems(self, dlg):
		els = self.licenseElements(dlg)
		out = []
		for key, kind, label, role in LICENSE_TAB:
			el = els.get(key)
			if not el:
				continue
			try:
				if not el.CurrentIsEnabled:
					continue
			except comtypes.COMError:
				continue
			out.append((key, kind, label, role, el))
		return out, els

	def taskLicenseTab(self, step):
		dlg = self.licenseDialog()
		if not dlg:
			say("Okno Licencja nie jest otwarte")
			return
		seq, els = self.licenseTabItems(dlg)
		if not seq:
			say("Brak elementów do przejścia")
			return
		keys = [k[0] for k in seq]
		if self.licCur in keys:
			idx = (keys.index(self.licCur) + step) % len(seq)
		else:
			idx = 0 if step > 0 else len(seq) - 1
		key, kind, label, role, el = seq[idx]
		self.licCur = key
		self._buyArmed = 0.0
		if kind == "table":
			n = self.licenseRowCount(el)
			text = "Tabela licencji, " + plural(n, "wiersz", "wiersze", "wierszy") if n else "Tabela licencji"
			if self.licRows:
				states = self.licenseStates()
				text += (", " + states) if states else ""
			say(text + ". Enter lub Spacja otwiera pełną listę")
		elif kind == "offer":
			say(self.offerText(els) or label)
		elif kind == "check":
			say("%s, %s, %s" % (label, role, self.toggleText(el)))
		else:
			say("%s, %s" % (label, role))

	def taskLicenseActivate(self):
		dlg = self.licenseDialog()
		if not dlg:
			say("Okno Licencja nie jest otwarte")
			return
		seq, els = self.licenseTabItems(dlg)
		entry = next((k for k in seq if k[0] == self.licCur), None)
		if not entry:
			say("Element jest niedostępny. Naciśnij Tab.")
			return
		key, kind, label, role, el = entry
		if kind == "table":
			self.taskLicenseTable(dlg, els)
		elif kind == "offer":
			say(self.offerText(els) or label)
		elif kind == "buy":
			if self.confirmBuy("Enter lub Spację"):
				self.press(el)
				say("Subskrybuj teraz, otwieram stronę zakupu")
		elif kind == "check":
			try:
				pat = el.GetCurrentPattern(UIA.UIA_TogglePatternId).QueryInterface(UIA.IUIAutomationTogglePattern)
				pat.Toggle()
			except (comtypes.COMError, AttributeError, ValueError):
				self.press(el)
			time.sleep(0.2)
			say("%s: %s" % (label, self.toggleText(el)))
		else:
			self.press(el)
			say(label)

	def licenseCells(self, table):
		"""Widoczne komórki tabeli: (wiersz, kolumna, lewo, góra, prawo, dół)."""
		out = []
		for ch in self.children(table):
			try:
				if ch.CurrentControlType != DATAITEM_TYPE:
					continue
				r = ch.CurrentBoundingRectangle
				if r.right <= r.left or r.bottom <= r.top:
					continue  # ukryta kolumna (np. Licencja)
				row = int(ch.GetCurrentPropertyValue(UIA.UIA_GridItemRowPropertyId))
				col = int(ch.GetCurrentPropertyValue(UIA.UIA_GridItemColumnPropertyId))
			except (comtypes.COMError, TypeError, ValueError):
				continue
			out.append((row, col, r.left, r.top, r.right, r.bottom))
		return out

	def licenseHeaders(self, table):
		"""Nazwy kolumn i dolna krawędź nagłówka tabeli."""
		names, bottom = [], None
		for ch in self.children(table):
			try:
				if ch.CurrentControlType != HEADER_TYPE:
					continue
				names.append((ch.CurrentName or "").strip())
				r = ch.CurrentBoundingRectangle
				if r.bottom > r.top:
					bottom = max(bottom or r.bottom, r.bottom)
			except comtypes.COMError:
				continue
		return names, bottom

	def licenseMakeVisible(self, hwnd, table):
		"""StreamFab otwiera okno Licencja częściowo pod paskiem zadań — przesuwa je tak, by tabela była cała na ekranie."""
		wa = workArea(hwnd)
		if not wa:
			return
		r = table.CurrentBoundingRectangle
		dy = 0
		if r.bottom > wa[3]:
			dy = wa[3] - r.bottom
		if r.top + dy < wa[1]:
			dy = wa[1] - r.top
		if not dy:
			return
		wr = ctypes.wintypes.RECT()
		if not _user32.GetWindowRect(hwnd, ctypes.byref(wr)):
			return
		_user32.SetWindowPos(hwnd, None, wr.left, wr.top + dy, 0, 0, 0x0001 | 0x0004 | 0x0010)  # bez zmiany rozmiaru, kolejności i aktywacji
		time.sleep(0.4)

	def licenseScan(self, dlg, table, bar, total):
		"""Komórki tabeli licencji StreamFab rysuje bez tekstu (UIA podaje puste nazwy), więc
		przewijamy tabelę paskiem przewijania i rozpoznajemy widoczne wiersze OCR Windows.
		Wiersz i kolumnę każdego słowa wyznaczają prostokąty komórek z UIA. Zwraca {wiersz: {kolumna: tekst}}."""
		hwnd = rootWindow(self.nativeHandle(dlg))
		if hwnd:
			if winUser.getForegroundWindow() != hwnd:
				ctypes.windll.user32.SetForegroundWindow(hwnd)
				time.sleep(0.2)
			self.licenseMakeVisible(hwnd, table)
		rv = None
		if bar:
			try:
				rv = bar.GetCurrentPattern(UIA.UIA_RangeValuePatternId).QueryInterface(UIA.IUIAutomationRangeValuePattern)
				orig, maxv = rv.CurrentValue, int(rv.CurrentMaximum)
			except (comtypes.COMError, AttributeError, ValueError):
				rv = None
		# readings[wiersz][kolumna] = [(tekst, pozycja wiersza w widoku)]; przebiegi zachodzą na siebie o jeden wiersz,
		# więc wiersz zasłonięty u góry (np. przez pływające okienko innego programu) odczytujemy drugi raz niżej.
		readings = {}
		v = 0
		try:
			for _ in range(max(total, 1) + 10):
				if rv:
					rv.SetValue(float(v))
					time.sleep(0.25)
				tr = table.CurrentBoundingRectangle
				_, headBottom = self.licenseHeaders(table)
				wa = (workArea(hwnd) if hwnd else None) or (tr.left, tr.top, tr.right, tr.bottom)
				clip = (max(tr.left, wa[0]), max(headBottom or tr.top, tr.top, wa[1]),
					min(tr.right, wa[2]), min(tr.bottom, wa[3]))
				cells = [c for c in self.licenseCells(table) if c[3] >= clip[1] - 2 and c[5] <= clip[3] + 2]
				visible = sorted({c[0] for c in cells})
				if cells and clip[2] - clip[0] > 20 and clip[3] - clip[1] > 20:
					words = ocrWords(clip[0], clip[1], clip[2] - clip[0], clip[3] - clip[1])
					for row, col, l, t, r, b in cells:
						ws = [w for w in words if l <= (w[0] + w[2]) / 2 <= r and t <= (w[1] + w[3]) / 2 <= b]
						ws.sort(key=lambda w: (w[1] // 8, w[0]))
						text = cleanCell(" ".join(w[4] for w in ws), stateColumn=(col == 2))
						cols = readings.setdefault(row, {})
						if text:
							cols.setdefault(col, []).append((text, visible.index(row)))
				if not rv or v >= maxv:
					break
				v = min(maxv, v + max(1, len(visible) - 1))
		finally:
			if rv:
				try:
					rv.SetValue(float(orig))
				except comtypes.COMError:
					pass
		# Z kilku odczytów komórki wybieramy tekst najczęstszy w całej kolumnie (np. „Dożywotni”),
		# potem odczyt spoza górnego wiersza widoku, potem dłuższy.
		freq = {}
		for cols in readings.values():
			for col, lst in cols.items():
				for text, _ in lst:
					freq[(col, text)] = freq.get((col, text), 0) + 1
		rows = {}
		for row, cols in readings.items():
			rows[row] = {col: max(lst, key=lambda x: (freq[(col, x[0])], x[1] > 0, len(x[0])))[0]
				for col, lst in cols.items()}
		return rows

	def taskLicenseTable(self, dlg=None, els=None):
		dlg = dlg or self.licenseDialog()
		if not dlg:
			say("Okno Licencja nie jest otwarte")
			return
		els = els or self.licenseElements(dlg)
		table = els.get("tableWidgetLicense")
		if not table:
			say("Tabela licencji jest niedostępna")
			return
		heads, _ = self.licenseHeaders(table)
		if not self.licRows:
			total = self.licenseRowCount(table)
			say("Odczytuję tabelę licencji, %s. To potrwa kilka sekund." % plural(total, "wiersz", "wiersze", "wierszy"))
			try:
				rows = self.licenseScan(dlg, table, els.get("licenseInfoOverlayScrollBar"), total)
			except Exception as e:
				log.warning("StreamFab dostęp: OCR tabeli licencji nie powiódł się", exc_info=True)
				say("Nie udało się odczytać tabeli licencji: %s. Jeśli włączona jest kurtyna ekranowa, wyłącz ją "
					"(NVDA+Ctrl+Escape) i spróbuj ponownie." % e)
				return
			if not any(rows.values()):
				say("Nie udało się odczytać tabeli licencji. Okno StreamFab musi być widoczne na ekranie.")
				return
			self.licRows = rows
		labels = {0: "Opcja", 1: "Licencja", 2: "Stan", 3: "Akcja"}
		for i, h in enumerate(heads):
			if h and h != "Stan licencji":
				labels[i] = h
		lines = []
		for r in sorted(self.licRows):
			cells = self.licRows[r]
			parts = ["%s: %s" % (labels.get(c, "Kolumna %d" % (c + 1)), t) for c, t in sorted(cells.items())]
			lines.append(", ".join(parts) if parts else "Wiersz %d: nie udało się odczytać" % (r + 1))
		head = ["Licencje StreamFab: " + plural(len(lines), "wiersz", "wiersze", "wierszy") + "."]
		states = self.licenseStates()
		if states:
			head.append("Stany licencji: " + states + ".")
		reg = readRegLicenses()
		if reg:
			head.append(reg[:1].upper() + reg[1:] + ".")
		head.append("Tekst odczytany z ekranu (OCR), możliwe drobne błędy w nazwach. Escape zamyka to okno.")
		say("Otwieram listę licencji. Escape zamyka okno.")
		queueHandler.queueFunction(queueHandler.eventQueue, showText, head + lines, "StreamFab — licencje")


def uiaClass(obj):
	el = obj.UIAElement
	try:
		return el.cachedClassName or ""
	except Exception:
		pass
	try:
		return el.CurrentClassName or ""
	except Exception:
		return ""


class MultiSelCombo(NVDAObjects.UIA.UIA):
	"""Lista wyboru języków (MuliSelCombox). Fokus dostaje jej wewnętrzne pole tekstowe
	tylko do odczytu, więc NVDA mówiło „edycja tylko do odczytu, en,pl”.
	Przedstawiamy całość jako listę rozwijaną z polskimi nazwami języków."""

	role = controlTypes.Role.COMBOBOX

	def _get_comboObj(self):
		if uiaClass(self) == "MuliSelCombox":
			return self
		return self.parent or self

	def _get_name(self):
		combo = self.comboObj
		aid = getattr(combo, "UIAAutomationId", "") or ""
		last = aid.rsplit(".", 1)[-1]
		if last in FORCE_NAMES:
			return FORCE_NAMES[last]
		return (combo.name if combo is not self else super()._get_name()) or "Wybór języków"

	def _get_value(self):
		try:
			raw = self._getUIACacheablePropertyValue(UIA.UIA_ValueValuePropertyId)
		except Exception:
			raw = ""
		return langValue(raw if isinstance(raw, str) else "")

	def _get_description(self):
		return "Alt+strzałka w dół lub Enter otwiera listę języków, Spacja zaznacza język, Enter lub Escape zamyka listę"

	def _get_states(self):
		states = set(super()._get_states())
		for s in (controlTypes.State.READONLY, controlTypes.State.EDITABLE, controlTypes.State.MULTILINE):
			states.discard(s)
		states.add(controlTypes.State.HASPOPUP)
		return states

	def expandPattern(self):
		el = self.comboObj.UIAElement
		return el.GetCurrentPattern(UIA.UIA_ExpandCollapsePatternId).QueryInterface(UIA.IUIAutomationExpandCollapsePattern)

	def expand(self):
		"""Otwiera listę języków przez UIA; gdy się nie da, wysyła Alt+strzałkę w dół."""
		try:
			self.appModule._lastCombo = self
		except Exception:
			pass
		try:
			self.expandPattern().Expand()
			return
		except Exception:
			log.debugWarning("StreamFab dostęp: Expand listy języków nie zadziałał", exc_info=True)
		import keyboardHandler
		keyboardHandler.KeyboardInputGesture.fromName("alt+downArrow").send()

	@script(description="Na liście Język audio lub Napisy: otwiera listę języków (Enter, Alt+strzałka w dół lub F4)",
		category=CATEGORY)
	def script_expand(self, gesture):
		self.expand()

	__gestures = {
		"kb:enter": "expand",
		"kb:alt+downArrow": "expand",
		"kb:f4": "expand",
	}


class AppModule(appModuleHandler.AppModule):

	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		if not isinstance(obj, NVDAObjects.UIA.UIA):
			return
		cls = uiaClass(obj)
		if cls == "MuliSelCombox":
			clsList.insert(0, MultiSelCombo)
		elif cls == "ClickedLineEdit":
			try:
				walker = UIAHandler.handler.clientObject.RawViewWalker
				parentEl = walker.GetParentElement(obj.UIAElement)
				if parentEl and parentEl.CurrentClassName == "MuliSelCombox":
					clsList.insert(0, MultiSelCombo)
			except Exception:
				pass

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.worker = Worker(self.processID)
		self.worker.onDialogChange = self._setDialogGestures
		self.worker.start()
		self._dialogGestures = False
		self._licenseMode = False  # otwarte okno Licencja: własny Tab, Enter i Spacja
		self._lastCombo = None
		self._lastStateEvent = 0.0
		self._films = []
		self._filmsStamp = None

	def terminate(self):
		self.worker.stop()
		super().terminate()

	# Klawisze nawigacji przechwytujemy tylko wtedy, gdy otwarte jest okno StreamFab,
	# żeby nie przeszkadzać trybowi przeglądania na stronach WWW.
	def _setDialogGestures(self, on, cls=""):
		lic = bool(on) and cls == LICENSE_CLASS
		if lic != self._licenseMode:
			self._licenseMode = lic
			for g in LICENSE_GESTURES:
				if lic:
					self.bindGesture(g, "licenseActivate")
				else:
					try:
						self.removeGestureBinding(g)
					except LookupError:
						pass
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

	# Skrypty poniżej są wiązane z klawiszami tylko przy otwartym oknie StreamFab (_setDialogGestures).
	@script(description="W otwartym oknie StreamFab: Tab, Shift+Tab, strzałka w górę lub w dół — "
		"przekazuje klawisz i czyta element, który naprawdę ma fokus", category=CATEGORY)
	def script_passNavKey(self, gesture):
		if self._licenseMode and getattr(gesture, "mainKeyName", "") == "tab":
			# okno Licencja: Tab utyka w tabeli, więc prowadzimy własny cykl po elementach okna
			step = -1 if "shift" in (getattr(gesture, "modifierNames", None) or ()) else 1
			self.worker.tasks.put(lambda: self.worker.taskLicenseTab(step))
			return
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

	@script(description="Spacja w otwartym oknie StreamFab: zaznacza lub odznacza odcinek albo język i ogłasza "
		"nowy stan; na liście Język audio lub Napisy otwiera listę", category=CATEGORY)
	def script_toggleItem(self, gesture):
		# Spacja na odcinku lub języku: Qt zmienia zaznaczenie bez komunikatu, więc go dopowiadamy.
		if self._licenseMode and self.worker.licCur:
			self.worker.tasks.put(self.worker.taskLicenseActivate)
			return
		focus = api.getFocusObject()
		if isinstance(focus, MultiSelCombo):
			focus.expand()
			return
		before = self._checked(focus) if focus.role in ITEM_ROLES else None
		pressed = time.monotonic()
		gesture.send()
		core.callLater(250, self._afterToggle, before, pressed)

	@script(description="Escape w otwartym oknie StreamFab: zamyka rozwiniętą listę języków bez zawieszania okna; "
		"poza listą działa zwykły Escape", category=CATEGORY)
	def script_escape(self, gesture):
		# Escape w otwartej liście języków: StreamFab jej nie zamyka, więc zwijamy ją
		# i oddajemy fokus polu Język audio / Napisy.
		combo = self._lastCombo
		expanded = False
		if combo is not None:
			try:
				expanded = combo.expandPattern().CurrentExpandCollapseState != 0  # 0 = zwinięta
			except Exception:
				self._lastCombo = None
		if not expanded:
			gesture.send()
			return
		# Escape (i Alt+strzałka w górę) zawieszały okno — Tab przestawał działać.
		# Enter zamyka listę czysto, więc Escape w otwartej liście wysyła Enter.
		import keyboardHandler
		self._lastCombo = None
		keyboardHandler.KeyboardInputGesture.fromName("enter").send()
		core.callLater(300, self._syncAfterClose)

	@script(description="Enter w oknie Licencja: wykonuje akcję elementu wybranego Tabem (otwiera listę licencji, "
		"przełącza pole, naciska przycisk; Subskrybuj teraz dopiero po potwierdzeniu)", category=CATEGORY)
	def script_licenseActivate(self, gesture):
		if not self._licenseMode or not self.worker.licCur:
			gesture.send()
			return
		self.worker.tasks.put(self.worker.taskLicenseActivate)

	def _syncAfterClose(self):
		"""Tylko czytamy to, co Qt naprawdę ma w fokusie — niczego nie przestawiamy."""
		try:
			h = UIAHandler.handler
			el = h.clientObject.GetFocusedElementBuildCache(h.baseCacheRequest)
			obj = NVDAObjects.UIA.UIA(UIAElement=el) if el else None
		except Exception:
			return
		if obj and obj.processID == self.processID and obj != api.getFocusObject():
			eventHandler.queueEvent("gainFocus", obj)

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
		if aid is None or isinstance(obj, MultiSelCombo):
			return
		role = obj.role
		if role in ITEM_ROLES and obj.name:
			self._cleanItem(obj)
			return
		if self._licenseMode and role == controlTypes.Role.DATAITEM and not obj.name:
			self._nameLicenseCell(obj)
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
		if not aid.startswith(OWN_PREFIXES):
			return
		last = aid.rsplit(".", 1)[-1]
		if last in LINK_LABELS:
			obj.name = LINK_LABELS[last]
			obj.description = "link, Ctrl+Shift+strzałki i Ctrl+Shift+Enter"
			return
		if obj.name and obj.name.strip() in TRANSLATE:
			obj.name = TRANSLATE[obj.name.strip()]
			return
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

	def _nameLicenseCell(self, obj):
		"""Komórki tabeli licencji są rysowane bez tekstu — po odczycie tabeli (OCR) podajemy treść wiersza."""
		try:
			row = obj._getUIACacheablePropertyValue(UIA.UIA_GridItemRowPropertyId)
		except Exception:
			return
		if not isinstance(row, int):
			return
		cells = (self.worker.licRows or {}).get(row)
		if cells:
			obj.name = ", ".join(t for c, t in sorted(cells.items()))
		else:
			obj.name = "Wiersz %d tabeli licencji" % (row + 1)
			obj.description = "Tab do tabeli, potem Enter: pełna lista licencji"

	def _nameFilmRow(self, obj):
		"""Wiersze listy pobranych są rysowane bez tekstu — nazwę bierzemy z plików danych programu."""
		try:
			parentId = getattr(obj.parent, "UIAAutomationId", "") or ""
		except Exception:
			return
		if not parentId.endswith("treeview_task_queue"):
			return
		if "pageDownloading" in parentId:
			# ta sama lista na karcie Downloading pokazuje kolejkę, nie pobrane filmy
			obj.name = "Wiersz kolejki pobierania. Ctrl+Shift+K: lista kolejki z tytułami i stanem"
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
		w = self.worker
		since = w.busySince
		busy = (time.monotonic() - since) if since else 0.0
		log.info("StreamFab dostęp: Ctrl+Shift+S, wątek żywy=%s, zajęty %.1f s (%s), w kolejce=%d" % (w.is_alive(), busy, w.busyName, w.tasks.qsize()))
		if not w.is_alive():
			ui.message("Wątek dodatku nie działa. Przeładuj NVDA klawiszami NVDA+Ctrl+F3.")
			return
		if busy > 2.0 or w.tasks.qsize() > 0:
			# StreamFab nie odpowiada na UIA (np. przy starcie pobierania) — odpowiadamy z plików, bez kolejkowania
			ui.message("StreamFab jest zajęty. " + w.fileStatus())
			return
		w.tasks.put(w.taskStatus)

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

	@script(description="Otwiera kolejkę pobierania z tytułami i stanem (czeka, trwa, błąd)", category=CATEGORY, gesture="kb:control+shift+k")
	def script_queue(self, gesture):
		header, items = self.worker.queueSummary()  # tylko pliki — działa także, gdy StreamFab nie odpowiada
		gui.mainFrame.prePopup()
		d = QueueDialog(gui.mainFrame, header, items)
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

	@script(description="Przechodzi do kolejnego otwartego okna StreamFab", category=CATEGORY, gesture="kb:control+shift+w")
	def script_switchWindow(self, gesture):
		self.worker.tasks.put(self.worker.taskSwitchWindow)

	@script(description="Czyta listę skrótów dodatku StreamFab dostęp", category=CATEGORY, gesture="kb:control+shift+h")
	def script_help(self, gesture):
		ui.message(
			"Ctrl+Shift+D: pobierz wideo. Ctrl+Shift+S: stan pobierania. Ctrl+L: pole adresu. "
			"Ctrl+Shift+L: lista pobranych filmów. Ctrl+Shift+K: kolejka pobierania. Ctrl+Shift+A: ogłaszanie zmian i nowych okien. "
			"W oknach dialogowych: Ctrl+Shift+O: OK. Ctrl+Shift+C: Anuluj lub Zamknij. "
			"Ctrl+Shift+strzałka w prawo lub w lewo: przeglądanie przycisków. Ctrl+Shift+Enter: naciśnij wybrany. "
			"Ctrl+Shift+R: przeczytaj okno. Ctrl+Shift+W: przejdź do kolejnego okna StreamFab. "
			"Gdy w StreamFab jest otwarte okno: Tab, Shift+Tab, strzałka w górę i w dół czytają element, który naprawdę ma fokus; "
			"Spacja zaznacza lub odznacza odcinek albo język i mówi nowy stan; Escape zamyka rozwiniętą listę języków. "
			"Na liście Język audio lub Napisy: Enter, Alt+strzałka w dół, F4 lub Spacja otwiera listę, Spacja zaznacza język, Enter lub Escape zamyka listę. "
			"W oknie pobranych filmów: Enter lub Alt+O odtwarza, Alt+F pokazuje w folderze, Alt+K kopiuje ścieżkę, Escape zamyka. "
			"W oknie kolejki pobierania Escape zamyka. "
			"W oknie Licencja: Tab i Shift+Tab przechodzą po elementach: tabela licencji, oferta Fab365, Subskrybuj teraz, "
			"Nie pokazuj ponownie, Rozpocznij StreamFab, Zamknij; Enter lub Spacja wykonuje akcję: na tabeli otwiera pełną listę "
			"licencji do czytania strzałkami, Escape zamyka listę; pole Nie pokazuj ponownie przełącza; "
			"Subskrybuj teraz otwiera stronę zakupu dopiero po drugim naciśnięciu. "
			"Ctrl+Shift+O: Rozpocznij StreamFab. Ctrl+Shift+C: Zamknij. Ctrl+Shift+R: przeczytaj okno Licencja. "
			"Ctrl+Shift+H: ta pomoc. Skróty zmienisz w NVDA, Ustawienia, Zdarzenia wejścia, kategoria StreamFab dostęp, "
			"otwierając to okno przy aktywnym StreamFab."
		)

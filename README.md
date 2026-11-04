# StreamFab dostęp

Dodatek do czytnika ekranu [NVDA](https://www.nvaccess.org/), który poprawia dostępność programu **StreamFab** (StreamFab64.exe) dla osób niewidomych.

## Pobieranie i instalacja

1. Pobierz najnowszą wersję: [streamfabaccess.nvda-addon](https://github.com/Matius1024/streamfabaccess/releases/latest/download/streamfabaccess.nvda-addon) (link zawsze prowadzi do najnowszego wydania; wcześniejsze wersje są w zakładce [Releases](../../releases)).
2. Otwórz go (Enter w Eksploratorze), potwierdź instalację i uruchom ponownie NVDA.

Wymagany NVDA 2024.1 lub nowszy (testowano z NVDA 2026.3 i StreamFab 7.0.5.6 na Windows 11).

## Co robi

- Nadaje polskie nazwy nieopisanym przyciskom: Wstecz, Dalej, Odśwież, Adres strony, Nowa karta, Zamknij, Wybierz folder i inne.
- Ogłasza stan pobierania („Gotowe do pobrania”, kolejka zadań) i nowe okna (komunikaty, ostrzeżenia, menu).
- Pozwala nacisnąć przycisk pobierania wideo, który nie jest dostępny klawiszem Tab.
- Pozwala nacisnąć przyciski okien (OK, Anuluj, Zamknij), których Tab nie widzi.
- Czyta fokus w menu My Account, które nie zgłasza go czytnikowi ekranu.
- Pokazuje listę pobranych filmów (wiersze w programie nie mają tekstu): odtwarzanie, folder, kopiowanie ścieżki.
- Ostrzega przed przyciskiem „Instaluj w tle” w oknie reklamy UniFab.

## Skróty (działają w oknie StreamFab)

| Skrót | Działanie |
|---|---|
| Ctrl+Shift+D | Naciśnij przycisk Pobierz wideo |
| Ctrl+Shift+S | Przeczytaj stan pobierania i kolejkę |
| Ctrl+L | Przejdź do pola adresu przeglądarki StreamFab |
| Ctrl+Shift+L | Lista pobranych filmów |
| Ctrl+Shift+O | OK w otwartym oknie |
| Ctrl+Shift+C | Anuluj (lub Zamknij) w otwartym oknie |
| Ctrl+Shift+Strzałka w prawo / w lewo | Przeglądaj wszystkie przyciski okna |
| Ctrl+Shift+Enter | Naciśnij wybrany przycisk |
| Ctrl+Shift+R | Przeczytaj treść okna |
| Ctrl+Shift+A | Włącz / wyłącz ogłaszanie zmian |
| Ctrl+Shift+H | Lista skrótów |

Skróty można zmienić w NVDA: Ustawienia → Zdarzenia wejścia → kategoria „StreamFab dostęp”.

Pełna dokumentacja: [addon/doc/pl/readme.html](addon/doc/pl/readme.html) (dostępna też w Menedżerze dodatków NVDA).

## Budowanie paczki

Paczka `.nvda-addon` to archiwum ZIP z zawartością folderu `addon`:

```powershell
Compress-Archive -Path addon\* -DestinationPath streamFabDostep.zip
Rename-Item streamFabDostep.zip streamFabDostep.nvda-addon
```

## Struktura

- `addon/manifest.ini` — opis dodatku dla NVDA
- `addon/appModules/streamfab64.py` — moduł aplikacji dla StreamFab64.exe (UI Automation, wątek roboczy)
- `addon/doc/pl/readme.html` — dokumentacja

## Znane ograniczenia

Opisane w dokumentacji, w rozdziale „Znane ograniczenia”.

Autor: Matius1024. Dodatek nie jest powiązany z firmą produkującą StreamFab.

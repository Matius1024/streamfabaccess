# StreamFab dostęp

Dodatek do czytnika ekranu [NVDA](https://www.nvaccess.org/), który poprawia dostępność programu **StreamFab** (StreamFab64.exe) dla osób niewidomych.

Aktualna wersja: **0.6.5**.

## Pobieranie i instalacja

1. Pobierz najnowszą wersję (0.6.5): [streamfabaccess.nvda-addon](https://github.com/Matius1024/streamfabaccess/releases/latest/download/streamfabaccess.nvda-addon) (link zawsze prowadzi do najnowszego wydania; wcześniejsze wersje są w zakładce [Releases](../../releases)).
2. Otwórz go (Enter w Eksploratorze), potwierdź instalację i uruchom ponownie NVDA.

Wymagany NVDA 2024.1 lub nowszy (testowano z NVDA 2026.3 i StreamFab 7.0.5.7 na Windows 11).

## Co robi

- Nadaje polskie nazwy nieopisanym przyciskom: Wstecz, Dalej, Odśwież, Adres strony, Nowa karta, Zamknij, Wybierz folder i inne.
- Ogłasza stan pobierania („Gotowe do pobrania”, kolejka zadań) i nowe okna (komunikaty, ostrzeżenia, menu).
- Pozwala nacisnąć przycisk pobierania wideo, który nie jest dostępny klawiszem Tab.
- Pozwala nacisnąć przyciski okien (OK, Anuluj, Zamknij), których Tab nie widzi.
- Czyta fokus w menu My Account, które nie zgłasza go czytnikowi ekranu.
- Pokazuje listę pobranych filmów (wiersze w programie nie mają tekstu): odtwarzanie, folder, kopiowanie ścieżki.
- Ostrzega przed przyciskiem „Instaluj w tle” w oknie reklamy UniFab.
- W oknie pobierania serialu czyta odcinki bez angielskich dopisków („Checked”, „Collapsed”), z czasem trwania, i pilnuje, żeby NVDA czytało odcinek, na którym naprawdę jest fokus.
- Po Spacji na odcinku lub języku mówi „zaznaczone” / „niezaznaczone” i licznik, np. „Wybrano 2 z 19”.
- Obsługuje logowanie (autoryzację komputera): nazywa pola E-mail i Hasło, ogłasza komunikaty („Weryfikowanie informacji o koncie”, błędy), pozwala kliknąć napisy-linki (Zaloguj przez Google, Zarejestruj, Zapomniane hasło). Gdy po zalogowaniu okno Licencja otworzy się pod oknem logowania, dodatek sam przenosi do niego klawiaturę — trzeba je zamknąć (Ctrl+Shift+C), żeby logowanie się zakończyło.
- Udostępnia okno Licencja: czyta je po pojawieniu się, ma własny cykl Tab (Tab utykał w tabeli z pustymi komórkami), a tabelę licencji (rysowaną bez tekstu) odczytuje na żądanie przez OCR Windows i pokazuje jako listę do czytania strzałkami.
- Nadaje polskie nazwy listom Język audio, Napisy, Rozdzielczość i tłumaczy nazwy języków na liście (np. „polski EAC3 5.1”).
- Listy Język audio i Napisy są czytane jako listy rozwijane z wybranymi językami po polsku (np. „angielski, polski”), a nie jako „edycja tylko do odczytu, en,pl”. Otwiera je Alt+strzałka w dół, Enter, F4 albo Spacja, a zamyka Enter lub Escape (dodatek zamienia Escape na Enter, bo sam Escape zawieszał okno i Tab przestawał działać). Powtórzony język ma licznik, np. „polski (4)”.

## Skróty (działają w oknie StreamFab)

| Skrót | Działanie |
|---|---|
| Ctrl+Shift+D | Naciśnij przycisk Pobierz wideo |
| Ctrl+Shift+S | Przeczytaj stan pobierania i kolejkę |
| Ctrl+L | Przejdź do pola adresu przeglądarki StreamFab |
| Ctrl+Shift+L | Lista pobranych filmów |
| Ctrl+Shift+K | Kolejka pobierania: tytuły, czas trwania i stan (czeka, trwa, błąd) |
| Ctrl+Shift+O | OK w otwartym oknie |
| Ctrl+Shift+C | Anuluj (lub Zamknij) w otwartym oknie |
| Ctrl+Shift+Strzałka w prawo / w lewo | Przeglądaj wszystkie przyciski okna |
| Ctrl+Shift+Enter | Naciśnij wybrany przycisk |
| Ctrl+Shift+R | Przeczytaj treść okna |
| Ctrl+Shift+W | Przejdź do kolejnego otwartego okna StreamFab (gdy jedno zasłania drugie) |
| Ctrl+Shift+A | Włącz / wyłącz ogłaszanie zmian |
| Ctrl+Shift+H | Wszystkie skróty dodatku w StreamFab |

Klawisze przechwytywane tylko wtedy, gdy w StreamFab jest otwarte okno (na stronach WWW działają normalnie):

| Klawisz | Działanie |
|---|---|
| Tab, Shift+Tab, Strzałka w górę / w dół | Działają zwykle, a dodatek czyta element, który naprawdę ma fokus (np. menu My Account, odcinki) |
| Spacja | Zaznacz / odznacz odcinek lub język i usłysz nowy stan; na liście Język audio lub Napisy otwiera listę |
| Escape | W rozwiniętej liście języków zamyka ją poprawnie (wysyła Enter); poza nią zwykły Escape |

Listy Język audio i Napisy: Enter, Alt+Strzałka w dół, F4 lub Spacja otwiera listę, Spacja zaznacza język, Enter lub Escape zamyka listę.

Okno pobranych filmów (Ctrl+Shift+L): Enter lub Alt+O odtwórz, Alt+F pokaż w folderze, Alt+K kopiuj ścieżkę, Escape zamknij. Okno kolejki (Ctrl+Shift+K): Escape zamyka.

### Okno Licencja

Okno pojawia się po uruchomieniu StreamFab (i po zalogowaniu). Dodatek czyta je automatycznie: „Okno Licencja. StreamFab, Autoryzowany, adres e-mail. Tabela licencji: 72 wiersze”, liczbę opcji z licencją i datę ważności z pliku rejestracji StreamFab oraz podpowiedź: najpierw jak przejść dalej, potem skróty.

#### Jak przejść dalej

Okno Licencja blokuje StreamFab, dopóki go nie zamkniesz. Żeby przejść dalej do programu:

1. (Opcjonalnie, żeby okno nie pojawiało się przy każdym starcie) naciśnij Tab 4 razy — NVDA powie „Nie pokazuj ponownie, pole wyboru, niezaznaczone” — i naciśnij Spację (lub Enter); NVDA powie „Nie pokazuj ponownie: zaznaczone”. Gdy któryś element okna jest nieaktywny, naciśnięć może być mniej — słuchaj nazwy pola. Od końca: 3 razy Shift+Tab.
2. Naciśnij Ctrl+Shift+O — przycisk Rozpocznij StreamFab (zalecane). Okno się zamyka i można korzystać z programu.
3. Zamiast tego możesz nacisnąć Ctrl+Shift+C — przycisk Zamknij, który również zamyka okno Licencja (tak kończy się logowanie, gdy okno pojawi się po zalogowaniu).

Komórki tabeli licencji StreamFab rysuje bez tekstu (czytnik słyszy tylko puste komórki), dlatego Enter na tabeli przewija ją i rozpoznaje widoczne wiersze wbudowanym w NVDA OCR Windows (trwa to kilka–kilkanaście sekund, okno StreamFab musi być widoczne na ekranie; przy włączonej kurtynie ekranowej NVDA próbuje przechwytywania Windows Graphics Capture). Wynik to lista do czytania strzałkami, jeden wiersz na linię, np. „Opcja: Netflix Downloader, Stan: Dożywotni”. Po odczycie komórki tabeli mają nazwy z treścią wiersza. Jeśli tabela wystaje pod pasek zadań, dodatek przesuwa okno w górę.

| Klawisz | Działanie |
|---|---|
| Tab / Shift+Tab | Następny / poprzedni element: tabela licencji, oferta Fab365 (po polsku, z ceną), Subskrybuj teraz, Nie pokazuj ponownie, Rozpocznij StreamFab, Zamknij |
| Enter, Enter numeryczny lub Spacja | Akcja bieżącego elementu: tabela — pełna lista licencji (Escape zamyka listę); oferta — przeczytaj; pole — przełącz; przycisk — naciśnij |
| Ctrl+Shift+O | Rozpocznij StreamFab |
| Ctrl+Shift+C | Zamknij okno |
| Ctrl+Shift+R | Przeczytaj okno (z ofertą i stanem pola Nie pokazuj ponownie) |

„Subskrybuj teraz” otwiera stronę zakupu, więc dodatek naciska go dopiero po drugim naciśnięciu Enter lub Spacji w ciągu 4 sekund (tak samo przy Ctrl+Shift+Enter w przeglądaniu przycisków). Nie ma on własnego skrótu.

### Okno aktualizacji StreamFab (StreamUpdate.exe)

Osobny moduł `streamupdate.py`: okno jest czytane automatycznie po polsku, przyciski i pole beta mają polskie nazwy, a postęp aktualizacji jest ogłaszany co kilka procent.

Okno aktualizacji nie przepuszcza Tab do przycisków, dlatego działa w nim własny Tab / Shift+Tab (tabela wersji, Co nowego, Historia zmian, pole beta, Pomiń tę wersję, Uaktualnij teraz, Anuluj, Minimalizuj, Zamknij); Enter, Enter numeryczny lub Spacja wykonują akcję bieżącego elementu. Gdy okna aktualizacji nie ma, te klawisze działają zwykle.

| Skrót | Działanie |
|---|---|
| Ctrl+Shift+R | Przeczytaj okno ponownie |
| Ctrl+Shift+U lub Ctrl+Shift+O | Uaktualnij teraz |
| Ctrl+Shift+P | Pomiń tę wersję |
| Ctrl+Shift+C | Anuluj (lub Zamknij) |
| Ctrl+Shift+I | Otwórz „Co nowego” w oknie do czytania strzałkami (zaznaczanie i kopiowanie, Escape zamyka); to samo Enter/Spacja na polu „Co nowego” w cyklu Tab |
| Ctrl+Shift+M | Otwórz historię zmian |
| Ctrl+Shift+B | Przełącz aktualizacje beta |
| Ctrl+Shift+A | Włącz / wyłącz ogłaszanie zmian |
| Tab / Shift+Tab | Następny / poprzedni element własnego cyklu Tab |
| Enter, Enter numeryczny lub Spacja | Akcja bieżącego elementu: naciśnij przycisk, przełącz pole beta, otwórz historię zmian, przeczytaj tabelę; na polu „Co nowego” otwiera okno do czytania (jak Ctrl+Shift+I) |
| Ctrl+Shift+H | Wszystkie skróty okna aktualizacji |

### Zmiana skrótów

Każdy skrót obu modułów ma polski opis i można go zmienić w NVDA: Ustawienia → Zdarzenia wejścia → kategoria „StreamFab dostęp” (wspólna dla obu modułów). Skróty modułu widać tam tylko wtedy, gdy okno Zdarzeń wejścia otworzysz przy aktywnym StreamFab (skróty StreamFab) albo przy aktywnym oknie aktualizacji (skróty okna aktualizacji). Tab, Shift+Tab, strzałki, Spacja i Escape (a w oknie Licencja także Enter) w StreamFab mają przypisany klawisz tylko wtedy, gdy w StreamFab jest otwarte okno, a otwieranie listy języków widać, gdy fokus jest na liście Język audio lub Napisy.

Pełna dokumentacja: [addon/doc/pl/readme.html](addon/doc/pl/readme.html) (dostępna też w Menedżerze dodatków NVDA).

## Co nowego w 0.6.5

- Dostępne okno Licencja: czytane automatycznie po pojawieniu się, z własnym cyklem Tab / Shift+Tab (tabela licencji, oferta Fab365, Subskrybuj teraz, Nie pokazuj ponownie, Rozpocznij StreamFab, Zamknij) i akcją Enter / Spacja.
- Tabela licencji (komórki bez tekstu) odczytywana na żądanie przez OCR Windows w NVDA i pokazywana w oknie do czytania strzałkami („Opcja: …, Stan: …”).
- W oknie Licencja Ctrl+Shift+O naciska Rozpocznij StreamFab, Ctrl+Shift+C zamyka okno, Ctrl+Shift+R czyta okno.
- Jak przejść dalej: podpowiedź po otwarciu okna, Ctrl+Shift+R i pomoc Ctrl+Shift+H zaczynają się od informacji o Ctrl+Shift+O / Ctrl+Shift+C i polu Nie pokazuj ponownie (4 razy Tab, Spacja).
- Przycisk zakupu „Subskrybuj teraz” jest naciskany dopiero po drugim naciśnięciu w ciągu 4 sekund.

Pełna historia zmian: rozdział „Historia zmian” w [addon/doc/pl/readme.html](addon/doc/pl/readme.html).

## Budowanie paczki

Paczka `.nvda-addon` to archiwum ZIP z zawartością folderu `addon`:

```powershell
Compress-Archive -Path addon\* -DestinationPath streamFabDostep.zip
Rename-Item streamFabDostep.zip streamFabDostep.nvda-addon
```

## Struktura

- `addon/manifest.ini` — opis dodatku dla NVDA
- `addon/appModules/streamfab64.py` — moduł aplikacji dla StreamFab64.exe (UI Automation, wątek roboczy)
- `addon/appModules/streamupdate.py` — moduł aplikacji dla StreamUpdate.exe (okno aktualizacji)
- `addon/doc/pl/readme.html` — dokumentacja (`addon/doc/en/readme.html` ma tę samą treść po polsku)

## Znane ograniczenia

Opisane w dokumentacji, w rozdziale „Znane ograniczenia”.

Autor: Matius1024. Dodatek nie jest powiązany z firmą produkującą StreamFab.

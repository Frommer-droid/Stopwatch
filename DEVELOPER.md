# Руководство разработчика Stopwatch

## Назначение и устройство

`Stopwatch.pyw` — PySide6-интерфейс и точка входа. `call_session.py` содержит независимый автомат состояний звонка и Hold; его поведение покрывают тесты в `tests/`. Версия берётся из `VERSION` при запуске из исходников и из `FROZEN_VERSION` в `version.py` в собранном приложении.

Локальные настройки находятся в `settings.json` рядом с приложением. Они не являются частью исходного кода или дистрибутива: файл хранит положение окна, выбранный масштаб, координаты Softphone и независимые пороги предупреждений одновременного и общего Hold. Нулевой порог отключает соответствующее предупреждение.

## Окружение и проверки

Проект использует Python 3.12+ и зависимости из `requirements.txt`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m py_compile Stopwatch.pyw call_session.py version.py Build_Tools\post_build.py
```

Тесты запускают Qt в режиме `offscreen`; готовое GUI-приложение во время автоматических проверок не запускается.

## Сборка

Перед релизной сборкой синхронизируйте `VERSION`, `version.py`, `RELEASE_NOTES.md` и пользовательскую документацию. Сборка создаётся из spec-файла:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller .\Build_Tools\Stopwatch.spec --noconfirm --clean
.\.venv\Scripts\python.exe .\Build_Tools\post_build.py
```

Для Windows-сборки используйте минимальный доверенный `PATH`: окружение проекта, его Python и `DLLs`, а также `%SystemRoot%\System32`. Не наследуйте пути IDE, Conda, MSYS или посторонних runtime-инструментов. `Build_Tools/Stopwatch.spec` останавливает сборку, если `Analysis.binaries` содержит DLL вне корня проекта, текущего Python-окружения или Windows.

После PyInstaller, до очистки служебных каталогов, проверьте `build/Stopwatch/COLLECT-00.toc` (либо фактический `--workpath`): все источники нативных бинарников должны быть доверенными. Затем убедитесь, что в корневой папке `Stopwatch/` есть `Stopwatch.exe`, `_internal`, `VERSION` и необходимые звуки. `post_build.py` намеренно не копирует локальный `settings.json`.

Собранный EXE, установщик и portable-артефакты не запускаются автоматически в процессе сборки. Перед публикацией отдельно проверьте неинтерактивный frozen import/runtime smoke с перехваченными stdout, stderr и кодом завершения.

## Установщик

`Build_Tools/Stopwatch.iss` создаёт x64‑совместимый Windows installer из готовой папки `Stopwatch/`. `Build_Tools/Build-Installer.ps1` находит Inno Setup 6 в стандартной машинной или пользовательской установке, считывает версию и помещает выпускной installer на фактический рабочий стол пользователя:

```powershell
.\Build_Tools\Build-Installer.ps1
```

Шаблон использует per-user установку, включает ярлык по желанию и оставляет пользователю отмеченную по умолчанию опцию запустить приложение после установки. Сам установщик в процессе релиза не запускается.

## Релиз

Локальный release commit получает tag вида `vX.Y.Z` и отдельный следующий числовой tag. GitHub-публикация использует только release tag; не применяйте `git push --tags`. В GitHub Release размещаются полные `RELEASE_NOTES.md` и проверенный installer-asset; не включайте в публичный артефакт персональные настройки, логи или секреты.

Публичный README существует на русском (`README.md`) и английском (`README.en.md`). Для каталога ShareMyApp после подтверждённой публикации синхронизируйте версию, прямую ссылку на asset и фактическую иконку приложения.

## Компилятор установщика

Для нестандартного расположения Inno Setup задайте INNO_SETUP_ISCC полным путём к ISCC.exe. Иначе используются стандартные каталоги установки и доступный компилятор из PATH.

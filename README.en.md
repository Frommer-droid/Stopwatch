<p align="center">
  <img src="logo.ico" width="112" height="112" alt="Stopwatch">
</p>

<h1 align="center">Stopwatch</h1>

<p align="center"><strong>A call and Hold timer that stays above every window.</strong></p>

<p align="center"><a href="README.md">Русская версия</a> · <a href="https://github.com/Frommer-droid/Stopwatch/releases/latest">Download the latest version</a></p>

A compact Windows call timer for operators: it shows the current Hold, total Hold time, and total call duration while staying above other windows.

## Features

- Control a call with **Ё** and Hold with **Insert**; these keys are suppressed so their normal input is not passed to other apps.
- Three counters: the current Hold, total Hold for the call, and total call duration.
- Independent current-Hold and total-Hold alerts: 3:30 and 3:40 by default; each threshold uses MM:SS and can be disabled with `0:00`. Blinking and sound can be disabled in Settings.
- Click a configured position in a Softphone window whenever Hold is toggled.
- Always-on-top mode, three interface sizes, and a system-tray mode.

## Install

Ready-to-use builds are published on the [latest release page](https://github.com/Frommer-droid/Stopwatch/releases/latest). Download the installer, install the application, and start `Stopwatch`.

## Use

Press **Ё** to start a call; press it again to end the call and reset all counters. During an active call, press **Insert** to start or end Hold. The left and right counters also support mouse control, and a right click on either resets all values.

Double-click the right counter to open general settings, including independent current-Hold and total-Hold thresholds. Double-click the window handle to configure the Softphone target and click coordinates. `settings.json` is created beside the application when preferences are saved and stores local preferences only.

## Requirements and running from source

The application is intended for Windows 10/11. Running from source requires Python 3.12+ and the dependencies in `requirements.txt`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\Start-Stopwatch.ps1
```

To verify the hotkey and call-state logic:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Build instructions are in [DEVELOPER.md](DEVELOPER.md). The project is licensed under the [MIT License](LICENSE).

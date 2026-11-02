# Fella Desktop Companion

## Warning, this program makes no sense if you dont watch or follow the [Exploring Lost Wads Doom ARG](https://www.youtube.com/@ExploringLostWads)

Wanted by some people in the community, i made a simple (totally not janky) desktop pet like program that displays like a little fella (thanks micha for not having fella have legs which would have implied making an actual walking cycle). It moves around on its own (prefers diagonals, although sometimes it moves straight in a direction, again jankyness), you can drag it around and it turns pink after petted (clicked) a few times, it also changes color on its own.

I also made it so when you have a Doom Sourceport open (**IMPORTANT: it needs to be either windowed or NOT exclusive fullscreen**, from my tests and how i have configured my doom sourceports, it seems to only work in the fullscreen mode of DOOM Retro, but i am sure that with some finnagling in the settings menu of UZDoom it would be possible to use), in fullscreen it will move around your game (optional toggle) like an overlay (DVD-logo esque).

It also works in video players (i tested youtube on my browser, LibreWolf, but it should work on basically everything that isnt exclusive fullscreen)

Settings menu in the system tray (little up arrow on windows, linux varies from DE to DE). As a fallback if there is no tray available, right click the fella to access the menu. the icon changes dynamically depending on the fella's color, also it has no taskbar icon

In the Settings menu you can disable/enable some things, as well as change different values

## Compatibility

On Linux, it only supports X11 sessions or running through XWayland (XWayland has limited functions). Wayland does not allow programs to position their windows by themselves or move on their own.
Also on Linux, if you launch Fella with XWayland, it will only be able to see Doom Sourceports that were ALSO launched with XWayland. it cannot see programs opened outside of XWayland (say, normally on the Wayland session)
Wayland has not been tested as much as pretty much all of my computers still use X11, although it was tested a little on a VM

## Run from source

Create a venv to run this, you could also use uv or pipx probably. if your distro already ships the required packages, then you may just install those and run the main.py file. the main issue is PySide6 and Qt6 which only ship on a few distros. I daily drive Arch Linux, so i can say that you can install this module from pacman directly (no AUR)

```bash
pip install -r requirements.txt
python main.py
```

This repo also has a .spec file for PyInstaller, which makes distribution easier (40~MB on Windows, 70~ on Linux), it builds as a onefile

## Controls

- Drag with the left mouse button to move the Fella.
- Click 5 times within 2 seconds (default, can be changed) to pet the Fella and make them pink for 6 seconds (configurable).
- Right-click fella to open the settings menu, pause its movements or exit the program.
- Double-click the tray icon to open the Settings menu directly.

## Configuration

Settings are stored in a JSON file managed by the Settings dialog:

- Windows: `%LOCALAPPDATA%\fella\config.json`
- Linux: `~/.config/fella/config.json`

Logs are written to the platform log directory, for example `%LOCALAPPDATA%\fella\Logs\fella.log` on Windows.

The default Doom process list includes `uzdoom.exe`, `chocolate-doom.exe`, `crispy-doom.exe`, `dsda-doom.exe`, `prboom-plus.exe`, and `gzdoom.exe` it can be edited in Settings. On Linux you need to remove '.exe', i use these defaults as the majority of the community uses windows (although little by little linux is more prevalent)
In here you put only the **Process Name**, not the absolute path to the executable (AKA, how Task Manager shows it)

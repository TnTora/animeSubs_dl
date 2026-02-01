# animeSubs_dl

mpv script to download japanese subtitles for anime. Both filename and title are parsed to obtain anime title and episode, this information is used to find subtitles on [jimaku](https://jimaku.cc/) (or [kitsunekko](https://kitsunekko.net/dirlist.php?dir=subtitles%2Fjapanese%2F) as a fallback). If the file chosen is compressed, the script will try to extract its contents. Once the subtitle file is downloaded, it will be automatically loaded on mpv for the current file to use.

### Demo

https://github.com/user-attachments/assets/424f4235-b425-48fa-9c29-9186c8a79cf6

## Installation

Locate your mpv config folder. It is typically found at `~/.config/mpv/` on Linux/MacOS and `C:\users\USERNAME\AppData\Roaming\mpv\` on Windows.  [Files section](https://mpv.io/manual/master/#files) in mpv's manual for more info. I will refer to the path of this folder as `<mpv config directory>` for the rest of this file.

To install the mpv script you can either use the precompiled binaries without having to install anything else. Otherwise you can setup a python environent to run the script. Binaries have not been thoroughly tested, open an Issue if you encounter any problem.

### Setup mpv script using compiled binaries

- Download the build version matching your system from the Release page and extract its contents
  
- Place the `animeSubs_dl` folder inside the `scripts` folder in `<mpv config directory>`. If it doesn't exist you should create it.

- If you are on macOS you may need to run the following command in Terminal to allow the system to run the sctipt since it is not signed:
  ```
  xattr -dr com.apple.quarantine ~/.config/mpv/scripts/animeSubs_dl/bin
  ```
Running the script for the first time might take a while so if nothing seems to happen just wait. Afterwards it should start almost instantly.

### Setup mpv script using python script

- Download the source code from Release section.

- Place the `animeSubs_dl` folder inside the `scripts` folder in `<mpv config directory>`. If it doesn't exist you should create it.

If you don't already have python 3.10 or above installed on your machine, install it. On Windows make sure python is added to PATH.

>**Optional:** Create and activate a [virtual environment](https://docs.python.org/3/library/venv.html) named `.mpv_venv` in `<mpv config directory>`. While optional, it is highly reccomended to keep the script isolated from the system python.
>
> If you chose a different name for the virtual environment or you want to use a different version of pyhton, open `main.lua` in a text editor and set the `custom_python_cmd` variable to a string containing your preferred command or path to binary.

Install dependencies (substitute `/` with `\` if you are on Windows)

```
cd <mpv config directory>
cd scripts/animeSubs_dl
pip install -r requirement.txt
```

## Usage

On mpv, use the keybinding `CTRL+SHIFT+j` to start the script and then follow the instruction on screen to select the correct file.

If you are playing a local file, the subtitles file will be placed in a folder named after the parsed anime title and placed in the same directory as your local file. If you are streaming a file, the subtitles will be downloaded into the `mpv_subs` folder automatically created in your `HOME` directory.

To change the keybinding add the following line to your `input.conf` file after replacing `CTRL+J` with whatever you prefer

```
# animeSubs_dl
Ctrl+J             script-binding animeSubs_dl/auto_download_subs
```

> **NOTE: If you are not using the [standard mpv build](https://mpv.io/installation/), your player might ignore the `input.conf` file (e.g. [mpv.net](https://github.com/mpvnet-player/mpv.net), [IINA](https://iina.io/)) so you might need to use the in-app options to set the keybindings.**

## Dependencies

| Name | LICENSE |
|------|---------|
| [aniparse](https://github.com/MeGaNeKoS/aniparse) | Mozilla Public License 2.0 (MPL 2.0) |
| [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/bs4/) | MIT License |
| [py7zr](https://github.com/miurahr/py7zr) | LGPL-2.1-or-later |
| [python-mpv-jsonipc](https://github.com/TnTora/python-mpv-jsonipc) (TnTora) <br> forked from [python-mpv-jsonipc](https://github.com/iwalton3/python-mpv-jsonipc) (iwalton3) | Apache-2.0|
| [requests](https://github.com/psf/requests) | Apache-2.0 |

Binaries are compiled using [Nuitka](https://github.com/Nuitka/Nuitka).

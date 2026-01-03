import sys
import os
import platform
from pathlib import Path
import json
import difflib
from urllib.request import urlretrieve
from urllib.parse import quote, unquote, urlparse
from subprocess import Popen
import zipfile
import aniparse
import requests
from bs4 import BeautifulSoup
from python_mpv_jsonipc import MPV
from scrollList import ScrollList

try:
    import py7zr
except ImportError:
    seven_zip_support = False
else:
    seven_zip_support = True

if platform.system() == "Darwin":       # macOS
    def open_file(filepath: str) -> None:
        Popen(["open", filepath])
elif platform.system() == "Windows":    # Windows
    def open_file(filepath: str) -> None:
        os.startfile(filepath)
else:                                   # linux variants
    def open_file(filepath: str) -> None:
        Popen(["xdg-open", filepath])

# Get directory of current file
directory = Path(__file__).parent
SOCKET = sys.argv[1]

download_in_folder = True
download_dir_default: os.PathLike = Path.home() / "mpv_subs"
download_dir_custom: os.PathLike | None = None
download_dir: os.PathLike = download_dir_custom or download_dir_default
download_dir.mkdir(parents=True, exist_ok=True)

mpv = MPV(start_mpv=False, ipc_socket=SOCKET)

with open(Path(directory) / "db.json") as f:
    db = json.load(f)


provider = "jimaku"
linkDictionary = {}

base_url = {
    "jimaku": "https://jimaku.cc",
    "kitsunekko": "https://kitsunekko.net/"
}

list_url = {
    "jimaku": "https://jimaku.cc",
    "kitsunekko": "https://kitsunekko.net/dirlist.php?dir=subtitles%2Fjapanese%2F"
}

css_selector = {
    "jimaku": ".table-data.file-name",
    "kitsunekko": "a:has(>strong)"
}


def get_list(url):
    global provider
    try:
        mpv.show_text(f"Fetching data from: {url}")
        response = requests.get(url, timeout=10)
    except requests.exceptions.Timeout as e:
        if provider == "kitsunekko" or (url not in list_url.values()):
            print(e, flush=True)
            mpv.terminate()
            sys.exit()
        provider = "kitsunekko"
        mpv.show_text("Connection timed out. Trying different provider")
        return get_list(list_url[provider])
    except Exception as e:  # noqa: BLE001
        print(e, flush=True)
        mpv.show_text("Something went wrong. Check console for details.")
        mpv.terminate()
        sys.exit()
        # raise SystemExit(e)

    soup = BeautifulSoup(response.content, "html.parser")
    entry_list = soup.select(css_selector[provider])
    result_list = {}
    for entry in entry_list:
        entry_tmp = entry.text.strip()
        # anime_list.append(anime_tmp)
        result_list[entry_tmp.lower()] = entry_tmp
        linkDictionary[entry_tmp] = entry["href"]
    return result_list


def get_episode(s):
    try:
        result = aniparse.parse(s)["episode_number"]
    except KeyError:
        result = None
    return result


def get_title(s):
    try:
        temp_result = aniparse.parse(s)
        result = temp_result["anime_title"]
        try:
            season = temp_result["anime_season"]
            if season > 1:
                result += f" {season}"
        except KeyError:
            pass
    except KeyError:
        result = None
    return result


def get_list_selection(header, list_data, comment=""):
    temp_list = ScrollList(mpv, header, list_data, comment=comment)
    selection = temp_list.get_selection()
    if selection is None:
        mpv.terminate()
        sys.exit()
    return selection


def get_mp_input(prompt="Type: "):
    while True:
        temp_result = mpv.get_input(prompt)
        if temp_result:
            return temp_result
        if temp_result is None:
            mpv.terminate()
            sys.exit()


def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def anilist_search(title):
    variables = {"page": 1, "perPage": 5, "search": title}

    url = "https://graphql.anilist.co"

    query = """
        query ($page: Int, $perPage: Int, $search: String) {
            Page (page: $page, perPage: $perPage) {
                pageInfo{
                    total
                    currentPage
                    lastPage
                    hasNextPage
                }
                media(search:$search, type:ANIME){
                    title{
                        romaji
                        english
                        native
                    }
                }
            }
        }
    """

    # mpv.show_text(f"Anilist search for {title}", 1000)
    try:
        response = requests.post(url, json={"query": query, "variables": variables}, timeout=5)
    except requests.exceptions.Timeout:
        msg = "Anilist: request timed out"
        print(msg, flush=True)
        mpv.show_text(msg, 1000)
        sys.exit()

    response_json = response.json()
    response_data = response_json["data"]["Page"]["media"]

    if not response_data:
        mpv.show_text(f"Anilist: no matches for {title}", 1000)
        return []

    # mpv.show_text("", 1000)
    titles_list = [response_data[i]["title"]["romaji"] for i in range(len(response_data))]

    if titles_list:
        db[title] = titles_list[0]
        with open(Path(directory) / "db.json", "w") as f:
            json.dump(db, f, indent=2)

    return titles_list


def handlezip(zip_path, dir_path, filename_no_ext, *, seven_zip=False):
    file_handler = py7zr.SevenZipFile if seven_zip else zipfile.ZipFile

    with file_handler(zip_path, "r") as zfile:
        test = zfile.testzip()
        if test is not None:
            mpv.show_text("File failed testzip, check console for details")
            print(f"first failed file: {test}", flush=True)
            return

        filelist = zfile.namelist()
        filelist.append("Extract All")
        file_id = get_list_selection("Select file from zip file", filelist)
        selected = filelist[file_id]
        filelist = filelist[:-1]

        selected = [selected] if selected != "Extract All" else filelist

        final_path = dir_path
        dirs = list({Path(x).parent for x in zfile.namelist()})
        # print(f"dirs: {dirs}", flush=True)

        if len(selected) > 1 and "" in dirs:
            final_path = Path(dir_path) / filename_no_ext.replace(os.path.sep, " ")
            # print(f"final_path: {final_path}", flush=True)
            try:
                Path.mkdir(final_path)
            except FileExistsError:
                print(f"Directory '{final_path}' already exists.")
            except Exception as e:
                print(f"An error occurred: {e}")
                mpv.show_text("An error occurred. Check console for more details")
                mpv.terminate()
                sys.exit()

        mpv.show_text("Extracting...", 60000)

        if seven_zip:
            zfile.reset()
            zfile.extract(path=final_path, targets=selected)
        else:
            zfile.extractall(path=final_path, members=selected)

        mpv.show_text("Finished Extracting")

        if len(selected) == 1:
            mpv.command("sub-add", Path(final_path) / selected[0])
            return

        # filelist = os.listdir(final_path)
        filelist = [x for x in selected if Path(final_path, x).is_file()]
        file_id = get_list_selection("Select file to load as sub", filelist)
        selected = filelist[file_id]
        mpv.command("sub-add", Path(final_path, selected))


def main() -> None:
    videoFilePath = None

    if is_valid_url(mpv.path):
        videoFilePath = download_dir
        filename = mpv.filename
    else:
        tempPath = Path(mpv.working_directory) / mpv.path
        if tempPath.is_file():
            videoFilePath = tempPath.parent
            filename = tempPath.name

    if videoFilePath is None:
        mpv.show_text(f"invalid input: '{mpv.path}'", 1000)
        mpv.terminate()
        sys.exit()

    anime_list = get_list(list_url[provider])

    title_options = set()
    episode_options = set()

    parsedFilename = get_title(filename)
    parsedFilenameEp = get_episode(filename)

    if parsedFilename:
        title_options.add(parsedFilename)

    if parsedFilenameEp:
        episode_options.add(parsedFilenameEp)

    parsedMediaTitle = get_title(mpv.media_title)
    parsedMediaTitleEp = get_episode(mpv.media_title)

    if parsedMediaTitle:
        title_options.add(parsedMediaTitle)

    if parsedMediaTitleEp:
        episode_options.add(parsedMediaTitleEp)

    title_options = list(title_options)
    parsedTitle = None
    if title_options:
        parsedTitle = title_options[0]
    if len(title_options) > 1:
        title_select_id = get_list_selection("Multiple possible titles parsed, select best match", title_options)
        parsedTitle = title_options[title_select_id]

    episode_options = list(episode_options)
    anime_ep = None
    if episode_options:
        anime_ep = episode_options[0]
    if len(episode_options) > 1:
        episode_select_id = get_list_selection("Multiple possible episodes parsed, select best match", episode_options)
        anime_ep = episode_options[episode_select_id]

    # mpv.show_text(f"parsing: {anime}", 1000)
    # parsedTitle = None
    # anime_ep = None
    if not parsedTitle:
        parsedTitle = get_mp_input("Type Title: ")
    if not anime_ep:
        anime_ep = get_mp_input("Type Episode Number: ")

    old_parsedTitle = parsedTitle
    anilist_results = None

    if parsedTitle in db:
        parsedTitle = db[parsedTitle]
    else:
        anilist_results = anilist_search(old_parsedTitle)
        if anilist_results:
            parsedTitle = anilist_results[0]

    mpv.show_text("", 1000)
    anime = parsedTitle
    while True:
        confirm_options = ["yes", "Change Title", "Change episode", "Change both"]
        confirmation_id = get_list_selection("Use parsed/guessed data?", confirm_options, f"Title: {anime}\\NEp: {anime_ep}")
        confirmation = confirm_options[confirmation_id]

        if confirmation == "yes":
            break
        if confirmation in {"Change Title", "Change both"}:
            if old_parsedTitle:
                if not anilist_results:
                    anilist_results = anilist_search(old_parsedTitle)
                anilist_results.append(old_parsedTitle)
                anilist_results.append("Other")
                anime = anilist_results[get_list_selection(f"Anilist results for {old_parsedTitle}: ", anilist_results)]
                if anime == "Other":
                    anime = get_mp_input("Type correct Title: ")
            else:
                anime = get_mp_input("Type correct Title: ")
            anilist_results = anilist_search(anime)
        if confirmation in {"Change episode", "Change both"}:
            anime_ep = get_mp_input("Type episode number: ")

    # print(f"anime: {anime}")

    matches = [anime_list[r] for r in difflib.get_close_matches(anime.lower(), anime_list, 20, 0.3)]

    # print(matches)

    while not matches:
        retry_id = get_list_selection("No Results yet. Manually type the title again?", ["yes", "no"], f"Last typed Title: {anime}")
        retry = ["yes", "no"][retry_id]
        if retry == "yes":
            anime = get_mp_input("Type the title: ")
            matches = [anime_list[r] for r in difflib.get_close_matches(anime.lower(), anime_list, 10, 0.3)]
            if matches:
                break
        elif retry == "no":
            mpv.terminate()
            sys.exit()

    # if old_parsedTitle and db[old_parsedTitle] != anime:
    if old_parsedTitle and db.get(old_parsedTitle) != anime:
        db[old_parsedTitle] = anime
        with open(Path(directory) / "db.json", "w") as f:
            json.dump(db, f, indent=2)

    selected = get_list_selection("Select Show", matches)
    selected_show = matches[selected]

    best_match = linkDictionary[matches[selected]]

    url2 = base_url[provider] + best_match
    ep_list = list(get_list(url2).values())
    ep_list.sort()

    compressed = ("zip", "7z", "rar")


    if anime_ep is not None:
        files = [(s) for s in ep_list if anime_ep == get_episode(s)]
        compressedFiles = [(s) for s in ep_list if s.endswith(compressed)]
        finalList = files + compressedFiles
    else:
        # files = [(s) for s in ep_list if not s.endswith(compressed)]
        compressedFiles = [(s) for s in ep_list if s.endswith(compressed)]
        files = [(s) for s in ep_list if s not in compressedFiles]
        finalList = compressedFiles + files

    if not finalList:
        confirmation_id = get_list_selection(
            "No matching sub found. Show all files for this show?",
            ["yes", "no"]
        )
        confirmation = ["yes", "no"][confirmation_id]
        if confirmation == "yes":
            # files = [(s) for s in ep_list if not s.endswith(compressed)]
            compressedFiles = [(s) for s in ep_list if s.endswith(compressed)]
            files = [(s) for s in ep_list if s not in compressedFiles]
            finalList = compressedFiles + files
        else:
            mpv.terminate()
            sys.exit()
    else:
        finalList.append("Show all files")


    selected = get_list_selection("Select file", finalList)

    if finalList[selected] == "Show all files":
        files = [(s) for s in ep_list if not s.endswith(compressed)]
        compressedFiles = [(s) for s in ep_list if s.endswith(compressed)]
        finalList = compressedFiles + files
        selected = get_list_selection("Select file", finalList)


    best_file = quote(unquote(linkDictionary[finalList[selected]].encode("utf-8")))
    full_filename = Path(finalList[selected])
    base_filename, ext = full_filename.stem, full_filename.suffix
    print(f"base: {base_filename}, ext: {ext}")

    if download_in_folder:
        videoFilePath = videoFilePath / selected_show.replace(os.path.sep, " ")
        if not Path(videoFilePath).is_dir():
            Path.mkdir(videoFilePath)

    full_path = Path(videoFilePath) / finalList[selected]
    mpv.show_text(f"Downloading file: {full_path}", 1000)


    url3 = base_url[provider] + best_file
    # print(url3)
    download = True
    if Path(full_path).is_file():
        download_options = ["Use existing file", "Download and overwrite file"]
        download = bool(get_list_selection("This file already exists", download_options))

    if download:

        try:
            if not url3.startswith(("http:", "https:")):
                raise ValueError("URL must start with 'http:' or 'https:'")

            urlretrieve(url3, full_path)
        except Exception as e:
            print(e, flush=True)
            mpv.show_text("Something went wrong. Check console for details.")
            mpv.terminate()
            sys.exit()
            # raise SystemExit(e)


    if full_path.suffix in compressed:
        mpv.show_text("Downloaded file is a compressed file", 1000)

        if zipfile.is_zipfile(full_path):
            handlezip(full_path, videoFilePath, base_filename)
        elif seven_zip_support and py7zr.is_7zfile(full_path):
            handlezip(full_path, videoFilePath, base_filename, seven_zip=True)
        else:
            try:
                open_file(str(full_path))
            except Exception:  # noqa: BLE001
                mpv.show_text(f"Failed to open downloaded file: {full_path}", 1000)
    else:
        mpv.command("sub-add", str(full_path))

    mpv.terminate()

if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        mpv.terminate()

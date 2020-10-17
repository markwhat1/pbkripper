#!/usr/bin/env python3
import logging
import os
import re
import shutil
import string
import sys

import requests
import tvdb_api
from youtube_dl import YoutubeDL

# DOWNLOAD_ROOT = 'C:/Users/markw/Downloads/pbs_tv_shows'
DOWNLOAD_ROOT = "."
DOWNLOAD_SUBTITLES = False
SUBTITLE_TYPE = "SRT"

# Source:
# https://github.com/ytdl-org/youtube-dl/blob/718393c632df5106df92c60c650f52d86a9a3510/youtube_dl/YoutubeDL.py#L137-L312
ydl_opts = {
    # "verbose": True,
    "quiet": True,
    "no_warnings": True,
    "outtmpl": "%(title)s.%(ext)s",
    "download_archive": "download_archive.txt",
    "ignoreerrors": True,  # ignore errors
    "writethumbnail": True,
    "writesubtitles": True,
    "allsubtitles": True,
    "min_sleep_interval": 5,
    "max_sleep_interval": 15,
    "addmetadata": True,
    # 'listformats': True,  # print a list of the formats to stdout and exit
    # "forcejson": True,
}

ydl = YoutubeDL(ydl_opts)
ydl.add_default_info_extractors()

headers = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 7.1.2; SM-G610M) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/71.0.3578.99 Mobile Safari/537.36"
}

PUNCT_TO_REMOVE = re.sub('[/-]', '', string.punctuation)  # Keep dashes and forward slashes
translator = str.maketrans("", "", PUNCT_TO_REMOVE)

tvdb_key = '1DE5C9B35180B706'
t = tvdb_api.Tvdb(apikey=tvdb_key)

logging.basicConfig(level=logging.INFO, format=" %(asctime)s - %(levelname)s - %(message)s")
# logging.disable(logging.DEBUG)
logging.debug("Start of program")


class Episode:
    """All show episode attributes"""

    def __init__(self, episode):
        """
        episode: downloaded json dictionary
        """
        self.mp4_url = episode["mp4"]
        self.subtitle_url = self.set_subtitles(
            closed_captions=episode["closedCaptions"]
        )
        self.subtitle_type = SUBTITLE_TYPE.lower()
        self.id = episode["id"]
        self.series_id = ''
        self.slug = episode["program"]["slug"]
        self.show_name = episode["program"]["title"].strip()
        self.episode_title = self.format_episode_title(title=episode["title"])
        self.episode_number = ''
        if DOWNLOAD_ROOT == ".":
            self.full_file_path = os.path.join(
                os.getcwd(), self.show_name, self.episode_title
            )
        else:
            self.full_file_path = os.path.join(
                DOWNLOAD_ROOT, self.show_name, self.episode_title
            )
        self.file_path_mp4 = f"{self.full_file_path}.mp4"
        self.file_path_sub = f"{self.full_file_path}.{self.subtitle_type}"
        self.file_dir = os.path.dirname(self.file_path_mp4)

    def create_output_files(self):
        os.makedirs(self.file_dir, exist_ok=True)
        if os.path.exists(self.file_path_mp4):
            logging.info(f"{self.episode_title} file exists, not downloading.")
        else:
            try:
                logging.info(f"Downloading: {self.episode_title}")
                # ydl.download function takes a list of URLs
                video_url_as_list = [self.mp4_url]
                ydl.download(video_url_as_list)
                dl_info = ydl.extract_info(self.mp4_url, download=False)
                orig_filename = dl_info["webpage_url_basename"]
                shutil.move(orig_filename, self.file_path_mp4)
                logging.info(
                    f"Downloaded file as {orig_filename}, renamed to {self.file_path_mp4}."
                )
                return True
            except FileNotFoundError:
                return False
                pass

        if self.subtitle_url and not os.path.exists(self.file_path_sub):
            caption_dl = requests.get(self.subtitle_url, headers=headers, stream=True)
            caption_dl.raise_for_status()
            logging.info(f"Writing subtitles to: {self.file_path_sub}.")
            with open(self.file_path_sub, "wb") as f:
                for block in caption_dl.iter_content(1024):
                    f.write(block)

    def format_episode_title(self, title):
        title_translated = title.translate(translator)
        if "/" in title:
            titles = title.split('/')
        else:
            titles = [title]

        # Search tvdb for tv_show slug
        show_tvdb = t[self.slug]
        episode_numbers = list()
        season_numbers = list()
        for x in titles:
            x_tvdb = show_tvdb.search(rf'{x}', key='episodeName')
            if len(x_tvdb) == 1:
                x_tvdb = x_tvdb[0]
                season_numbers.append(x_tvdb['airedSeason'])
                episode_numbers.append(x_tvdb['airedEpisodeNumber'])
            elif len(x_tvdb) == 0:
                x = x.split(' ')[-1]
                x_tvdb = show_tvdb.search(rf'{x}', key='episodeName')
                if len(x_tvdb) == 1:
                    x_tvdb = x_tvdb[0]
                    season_numbers.append(x_tvdb['airedSeason'])
                    episode_numbers.append(x_tvdb['airedEpisodeNumber'])
                else:
                    logging.info(f'No matching EPISODE results for: {x} in {self.show_name}')
                    self.episode_number = 'S00E00'
                    title_translated = title_translated.replace('/', '')
                    self.episode_title = f'{self.show_name} -{self.episode_number}- {title_translated}'
                    return self.episode_title
            else:
                logging.info(f'Too many EPISODE results for: {x} in {self.show_name}')
                self.episode_number = 'S00E00'
                title_translated = title_translated.replace('/', '')
                self.episode_title = f'{self.show_name} -{self.episode_number}- {title_translated}'

        self.set_episode_number(season_list=season_numbers, episode_list=episode_numbers)

        # Translator removes all punctuation except '/' to allow for dual episode renaming
        # Replacing the '/' with a '-' for dual episodes
        title = title.translate(translator).replace('/', '-')

        # Form complete title
        self.episode_title = f'{self.show_name} - {self.episode_number} - {title}'
        return self.episode_title

    def set_episode_number(self, season_list, episode_list):
        # Use list(set()) to remove duplicates
        season_list = list(set(season_list))
        season_number = season_list[0]
        episode_list = list(set(episode_list))

        # Combine episode numbers if necessary
        if len(episode_list) == 2:
            episode_numbers = f'E{episode_list[0]:02}-E{episode_list[1]:02}'
        else:
            episode_numbers = f'E{episode_list[0]:02}'

        # Make full season/episode key
        self.episode_number = f'S{season_number:02}{episode_numbers}'

    def set_subtitles(self, closed_captions):
        if DOWNLOAD_SUBTITLES:
            for caption in closed_captions:
                if caption["format"].lower() == self.subtitle_type:
                    return caption["URI"]
        else:
            return ""


def get_url_json(url):
    try:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        raise SystemExit(e)
    return r.json()


def get_shows():
    pbs_full_show_list_url = "https://content.services.pbskids.org/v2/kidspbsorg/home"
    json = get_url_json(pbs_full_show_list_url)

    combined_show_list = []
    collections = json["collections"]
    show_dict_keys = [
        "kids-show-spotlight",
        "kids-programs-tier-1",
        "kids-programs-tier-2",
        "kids-programs-tier-3",
    ]
    for key in show_dict_keys:
        for show_json in collections[key]["content"]:
            combined_show_list.append(show_json)
    combined_show_list.sort()
    return combined_show_list


def get_show_slug_list():
    show_list = get_shows()
    slug_list = list()
    for x in show_list:
        x_title = x['title']
        x_slug = x['slug']
        slug_list.append(f"{x_title} = '{x_slug}'")
    sorted_slugs = sorted(slug_list, key=str.lower)
    for count, slug in enumerate(sorted_slugs, start=1):
        logging.info(f'{count}: {slug}')


def ask_which_show(index=None, show_name=None):
    show_list = get_shows()
    chosen_index = ''
    if show_name:
        chosen_show = show_name
        for x in show_list:
            if x['title'] == chosen_show:
                return show['slug']
    elif index:
        chosen_index = index
    else:
        logging.info(f"\nCurrent show list:\n===================")

        for show_index, x in enumerate(show_list, start=1):
            logging.info(f'[{show_index}]: {x["title"]}')
        chosen_index = input(f"Select a show: [1 - {len(show_list)}], E=exit: ")

    chosen_index = check_input(chosen_index, upper_limit=len(show_list))
    return show_list[chosen_index]["slug"]


def check_input(value, upper_limit):
    if str(value).isdigit():
        if 1 <= int(value) <= upper_limit:
            return int(value) - 1
        else:
            sys.exit("Number entered was out of range, please restart.")
    elif value.upper() == "A":  # Download all episodes of selected show
        return value.upper()
    elif value.upper() == "E":
        sys.exit(f"Script exited.")
    else:
        sys.exit(f"Incorrect value entered, exiting.")


def check_available_episodes(show_title):
    pbs_show_url = (
        f"https://content.services.pbskids.org/v2/kidspbsorg/programs/{show_title}"
    )
    json = get_url_json(pbs_show_url)
    episode_list = json["collections"]["episodes"]["content"]
    if not episode_list:
        sys.exit(
            f'No episodes available for series: "{show_title}". Try another show next time.'
        )
    return episode_list


def ask_which_episode(show_title, download_all=False):
    episodes = check_available_episodes(show_title)
    if download_all:
        logging.info(f'Downloading all available episodes of {show_title}')
        for count, episode in enumerate(episodes, start=1):
            show_episode = Episode(episode)
            logging.info(f"[Checking file {count} of {len(episodes)}.]")
            show_episode.create_output_files()
    else:
        logging.info(f"\nAvailable Episodes for {episodes[0]['program']['title']}:"
                     f"\n===============================")

        for count, episode in enumerate(episodes, start=1):
            logging.info(f'[{count}]: {episode["title"]}')
        chosen_index = input(
            f"Which episode do you want? [1-{len(episodes)}], A=All, E=exit: "
        )
        chosen_index = check_input(chosen_index, upper_limit=len(episodes))

        dl_count = 0
        if chosen_index == "A":  # Download all episodes of selected show
            for count, episode in enumerate(episodes, start=1):
                show_episode = Episode(episode)
                logging.info(f"[Starting download {count} of {len(episodes)}.]")
                dl_status = show_episode.create_output_files()
                if dl_status:
                    dl_count += 1
            logging.info(f"Downloaded {dl_count} new episodes of {show_title}.")
        else:
            show_episode = Episode(episodes[chosen_index])
            show_episode.create_output_files()


if __name__ == "__main__":
    # wanted_shows = 'slug' values
    # See list of available slug values
    # get_show_slug_list()

    # wanted_shows = ''
    wanted_shows = ['daniel-tigers-neighborhood', 'wild-kratts']
    if wanted_shows:
        for item in wanted_shows:
            ask_which_episode(item, download_all=True)
    else:
        show = ask_which_show()
        ask_which_episode(show)

    logging.info("\nScript has completed.")

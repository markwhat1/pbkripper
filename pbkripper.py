#!/usr/bin/env python3
import os
import sys

import requests
from youtube_dl import YoutubeDL

DOWNLOAD_ROOT = '.'
DOWNLOAD_SUBTITLES = False
SUBTITLE_TYPE = 'SRT'

ydl = YoutubeDL({'outtmpl': '%(id)s.mp4'})
ydl.add_default_info_extractors()

headers = requests.utils.default_headers()
headers.update({'User-Agent': 'Mozilla/5.0 (Linux; Android 7.1.2; SM-G610M) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/71.0.3578.99 Mobile Safari/537.36'})


class Episode:
    """All show episode attributes"""

    def __init__(self, episode):
        """
        episode: downloaded json dictionary
        """
        self.mp4_url = episode['mp4']
        self.id = episode['id']
        self.slug = episode['program']['slug']
        self.show_name = episode['program']['title'].strip()
        self.episode_title = self.format_episode_title(title=episode['title'])
        self.episode_number = self.format_episode_number(episode_num=episode['nola_episode'])
        self.base_file_name = self.format_base_file_name()
        self.full_file_path = os.path.join(DOWNLOAD_ROOT, self.show_name, self.base_file_name)
        self.file_path_mp4 = f'{self.full_file_path}.mp4'
        self.file_path_sub = f'{self.full_file_path}.{self.subtitle_type}'
        self.subtitle_type = SUBTITLE_TYPE.lower()
        self.subtitle_url = self.set_subtitles(closed_captions=episode['closedCaptions'])
        self.file_dir = os.path.dirname(self.file_path_mp4)

    def format_base_file_name(self):
        if self.episode_number:
            return f"{self.show_name}-{self.episode_number}-{self.episode_title}"
        else:
            return f"{self.show_name}-{self.episode_title}"

    def create_output_files(self):
        os.makedirs(self.file_dir, exist_ok=True)
        if os.path.exists(self.file_path_mp4):
            print(f"{self.episode_title} file exists, not downloading.")
        else:
            print(f"Downloading: {self.episode_number}")
            # ydl.download function takes a list of URLs
            video_url_as_list = [self.mp4_url]
            ydl.download(video_url_as_list)
            dl_info = ydl.extract_info(self.mp4_url, download=False)
            orig_filename = dl_info['webpage_url_basename']
            os.rename(orig_filename, self.file_path_mp4)
            print(f'Downloaded file as {orig_filename}, renamed to {self.file_path_mp4}.')

        if self.subtitle_url:
            if not os.path.exists(self.file_path_sub):
                caption_dl = requests.get(self.subtitle_url, headers=headers, stream=True)
                caption_dl.raise_for_status()
                print(f"Writing subtitles to: {self.file_path_sub}.")
                with open(self.file_path_sub, 'wb') as f:
                    for block in caption_dl.iter_content(1024):
                        f.write(block)

    @staticmethod
    def format_episode_number(episode_num):
        # A lot of episodes seem to not include a real number, so most of the time 'nola_episode'
        # is just an abbreviation of the show title
        if episode_num.isdigit():
            # If episode number is like 301, split so it becomes S3E01
            episode_number = episode_num[-2:]
            season_number = episode_num.replace(episode_number, '')
            if len(season_number) == 1:
                season_number = f'0{season_number}'
            return f'S{season_number}E{episode_number}'
        else:
            return ''

    @staticmethod
    def format_episode_title(title):
        return title.replace('/', '-').replace("’", "").replace("'", "").replace("&", "and")

    @staticmethod
    def set_subtitles(closed_captions):
        if DOWNLOAD_SUBTITLES:
            for caption in closed_captions:
                if caption['format'].lower() == SUBTITLE_TYPE.lower():
                    return caption['URI']
        else:
            return ''


def get_url_json(url):
    try:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        raise SystemExit(e)
    return r.json()


def get_shows():
    pbs_full_show_list_url = 'https://content.services.pbskids.org/v2/kidspbsorg/home'
    json = get_url_json(pbs_full_show_list_url)

    combined_show_list = []
    collections = json['collections']
    show_dict_keys = ['kids-show-spotlight', 'kids-programs-tier-1', 'kids-programs-tier-2',
                      'kids-programs-tier-3']
    for key in show_dict_keys:
        for show_json in collections[key]['content']:
            combined_show_list.append(show_json)
    return combined_show_list


def ask_which_show():
    show_list = get_shows()
    print(f"\nCurrent show list:\n===================")

    show_index = 1
    for x in show_list:
        print(f'[{show_index}]: {x["title"]}')
        show_index += 1
    chosen_index = input(f'Select a show: [1 - {len(show_list)}], E=exit: ')
    chosen_index = check_input(chosen_index, upper_limit=len(show_list))
    return show_list[chosen_index]['slug']


def check_input(value, upper_limit):
    if value.isdigit():
        if 1 <= int(value) <= upper_limit:
            return int(value) - 1
        else:
            sys.exit(f'Number entered was out of range, please restart.')
    elif value.upper() == "A":  # Download all episodes of selected show
        return value.upper()
    elif value.upper() == "E":
        sys.exit(f'Script exited.')
    else:
        sys.exit(f'Incorrect value entered, exiting.')


def check_available_episodes(show_title):
    pbs_show_url = f'https://content.services.pbskids.org/v2/kidspbsorg/programs/{show_title}'
    json = get_url_json(pbs_show_url)
    episode_list = json['collections']['episodes']['content']
    if not episode_list:
        sys.exit(f'No episodes available for series: "{show_title}". Try another show next time.')
    return episode_list


def ask_which_episode(show_title):
    episodes = check_available_episodes(show_title)
    print(f"\nAvailable Episodes for {episodes[0]['program']['title']}:\n===================")

    index = 1
    for episode in episodes:
        print(f'[{index}]: {episode["title"]} - {episode["description"]}')
        index += 1
    chosen_index = input(f'Which episode do you want? [1-{len(episodes)}], A=All, E=exit: ')
    chosen_index = check_input(chosen_index, upper_limit=len(episodes))

    if chosen_index == "A":  # Download all episodes of selected show
        for episode in episodes:
            show_episode = Episode(episode)
            show_episode.create_output_files()
    else:
        show_episode = Episode(episodes[chosen_index])
        show_episode.create_output_files()


if __name__ == '__main__':
    show = ask_which_show()
    ask_which_episode(show)

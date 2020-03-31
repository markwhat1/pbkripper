#!/usr/bin/env python3
import os
import sys

import requests
from youtube_dl import YoutubeDL

DOWNLOAD_ROOT = '.'
DOWNLOAD_SUBTITLES = True
SUBTITLE_TYPE = 'SRT'

ydl = YoutubeDL({'outtmpl': '%(id)s.mp4'})
ydl.add_default_info_extractors()

headers = requests.utils.default_headers()
headers.update({'User-Agent': 'Mozilla/5.0 (Linux; Android 7.1.2; SM-G610M) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/71.0.3578.99 Mobile Safari/537.36'})


def get_url_json(url):
    try:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        raise SystemExit(e)
    return r.json()


def get_shows():
    # pbs_full_show_list_url = 'https://pbskids.org/pbsk/video/api/getShows/'
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


def ask_which_show(show_list):
    show_index = 1
    for x in show_list:
        print(f'[{show_index}]: {x["title"]}')
        show_index += 1
    chosen_index = int(input(f'Select a show: [1 - {len(show_list)}]: '))
    chosen_index = int(chosen_index) - 1
    return show_list[chosen_index]['slug']


def check_available_episodes(show_title):
    pbs_show_url = f'https://content.services.pbskids.org/v2/kidspbsorg/programs/{show_title}'
    json = get_url_json(pbs_show_url)
    episode_list = json['collections']['episodes']['content']
    return episode_list


def ask_which_episode(episodes):
    # episodes = check_available_episodes(show_title)
    print(f"\n\nAvailable Episodes for {episodes[0]['program']['title']}:\n===================")

    index = 1
    for episode in episodes:
        print(f'[{index}]: {episode["title"]} - {episode["description"]}')
        index += 1

    chosen_index = input(f'Which episode do you want? [1 - {len(episodes)}], A=All: ')
    if chosen_index.isdigit():
        chosen_index = int(chosen_index) - 1
    return chosen_index


def get_video_info(video, subtitles=False):
    info = dict()
    info['mp4'] = video['mp4']
    info['id'] = video['id']
    info['slug'] = video['program']['slug']
    info['show_name'] = video['program']['title'].strip()
    info['episode_title'] = format_episode_title(video['title'])
    info['episode_number'] = format_episode_number(video['nola_episode'])
    if not info['episode_number']:
        info['base_file_name'] = f"{info['show_name']}-{info['episode_title']}"
    else:
        info[
            'base_file_name'] = f"{info['show_name']}-{info['episode_number']}-{info['episode_title']}"
    info['video_file'] = os.path.join(DOWNLOAD_ROOT, info['show_name'], info['base_file_name'])
    if subtitles:
        for caption in video['closedCaptions']:
            if caption['format'].lower() == SUBTITLE_TYPE.lower():
                info['subtitle_url'] = caption['URI']
    return info


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


def format_episode_title(episode_title):
    return episode_title.replace('/', ' and ').replace("’", "").replace("'", "").replace("&", "and")


def create_output_files(info_dict):
    video_dir = os.path.dirname(info_dict['video_file'] + ".mp4")
    print(f'video_dir: {video_dir}')
    os.makedirs(video_dir, exist_ok=True)
    mp4_file = f"{info_dict['video_file']}.mp4"
    if os.path.exists(mp4_file):
        print("Video file exists, not downloading.")
        d = {'slug': info_dict['slug'], 'videofile': mp4_file}
    else:
        print(f"Writing to: {mp4_file}.")
        # ydl.download function takes a list of URLs
        video_url_as_list = [info_dict['mp4']]
        ydl.download(video_url_as_list)
        dl_info = ydl.extract_info(info_dict['mp4'], download=False)
        orig_filename = dl_info['webpage_url_basename']
        os.rename(orig_filename, mp4_file)
        print(f'Downloaded file as {orig_filename}, renamed to {mp4_file}.')

    if 'subtitle_url' in info_dict:
        subtitle_extension = info_dict['subtitle_url'].split(".")[-1:]
        print(subtitle_extension)
        subtitle_extension = ''.join(subtitle_extension)
        print(subtitle_extension)
        subtitle_filename = info_dict['video_file'] + "." + subtitle_extension
        if not os.path.exists(subtitle_filename):
            caption_dl = requests.get(info_dict['subtitle_url'], headers=headers, stream=True)
            caption_dl.raise_for_status()
            print(f"Writing subtitles to: {subtitle_filename}.")
            with open(subtitle_filename, 'wb') as f:
                for block in caption_dl.iter_content(1024):
                    f.write(block)


if __name__ == '__main__':
    shows = get_shows()
    show = ask_which_show(shows)
    available_episodes = check_available_episodes(show)
    if not available_episodes:
        sys.exit(f'No episodes available for series: "{show}". Try another show next time.')

    # system('clear')
    index_to_get = ask_which_episode(available_episodes)
    if index_to_get.upper() == "A":  # Download all episodes of selected show
        for item in available_episodes:
            video_info = get_video_info(item, DOWNLOAD_SUBTITLES)
            create_output_files(video_info)
    else:  # Download only selected episode
        index_to_get = int(index_to_get)
        video_info = get_video_info(available_episodes[index_to_get], DOWNLOAD_SUBTITLES)
        create_output_files(video_info)

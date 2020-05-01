import logging
import os
import re
import string

from tvmaze.api import Api

logging.basicConfig(level=logging.DEBUG, format=' %(asctime)s - %(levelname)s- %(message)s')
# logging.disable(logging.CRITICAL)
logging.debug('Start of program')

api = Api()

translator = str.maketrans('', '', string.punctuation)


def get_episode_list(show_title):
    try:
        show = api.search.single_show(show_title)
        if show and show._links.get('self'):
            show_url = show._links['self']['href']  # 'http://api.tvmaze.com/shows/9188'
            show_id = show_url.split('/')[-1]  # 9188
        else:
            show_id = ''
            print('No matching show found.')

        episode_list = list()
        if show_id:
            show_episodes = api.show.episodes(show_id)
            for epi in show_episodes:
                if len(str(epi.season)) > 1:
                    epi_season = epi.season
                else:
                    epi_season = f'0{epi.season}'
                if len(str(epi.number)) > 1:
                    epi_episode = epi.number
                else:
                    epi_episode = f'0{epi.number}'

                epi_dict = dict()
                epi_dict['name'] = epi.name.translate(translator)
                epi_dict['episode_num'] = f'S{epi_season}E{epi_episode}'
                episode_list.append(epi_dict)
    except:
        episode_list = list()
        pass

    print(episode_list)
    return episode_list


def add_episode_num(file, episode_list):
    episode_name = file.split('--')[-1]
    episode_name_without_ext = episode_name.split('.')[0]
    episode_name_without_ext = episode_name_without_ext.translate(translator)
    logging.debug(f'File name without punctuation: {episode_name_without_ext}')
    episode_num = list()
    for episode in episode_list:
        if episode['name'].lower() in episode_name_without_ext.lower():
            logging.debug('Matched: [PBS] ' + episode[
                'name'].lower() + ' to [DL] ' + episode_name_without_ext.lower())
            episode_num.append(episode['episode_num'])
    if episode_num:
        episode_num = '-'.join(episode_num)
        logging.debug(episode_num + ' is being added to file name.')
        episode_num = re.sub(r'-S\d{2}', '-', episode_num)
        file = file.replace('--', f'-{episode_num}-')
        print(file)
    return file


def rename_files(path):
    show_dir = os.path.relpath(path)
    episode_list = get_episode_list(show_dir)
    for filename in os.listdir(path):
        if '--' in filename:
            new_filename = add_episode_num(filename, episode_list)
            os.rename(os.path.join(path, filename), os.path.join(path, new_filename))


cwd = os.getcwd()

for x in os.listdir(cwd):
    if os.path.isdir(x) and x[0] is not '.':
        show_path = os.path.join(cwd, x)
        print(show_path)
        rename_files(show_path)

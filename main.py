import os
import sys
import os.path

from bs4 import BeautifulSoup
import requests

import config


def do_auth(user, pwd): #login using user and pwd, returns logged in session
    sess = requests.Session()

    login_page = sess.get('https://teamtreehouse.com/signin')
    login_page_soup = BeautifulSoup(login_page.text)
    
    token_val = login_page_soup.find('input', {'name': 'authenticity_token'}).get('value')
    utf_val = login_page_soup.find('input', {'name': 'utf8'}).get('value')
    
    post_data = {'user_session[email]': user, 'user_session[password]': pwd, 'utf8': utf_val,
                 'authenticity_token': token_val}

    profile_page = sess.post('https://teamtreehouse.com/person_session', data=post_data)
    
    profile_page_soup = BeautifulSoup(profile_page.text)
    auth_sign = profile_page_soup.title.text
    if auth_sign:
        if auth_sign.lower().find('home') != -1:
            print('[!] Login success!')
        else:
            print('[!!] Not found login attribute\nExit...')
            sys.exit(0)
    else:
        raise Exception('Login failed!')

    return sess


def http_get(url): #returns text of url
    resp = sess.get(url)
    return resp.text

def get_msg(msg, path, kind): #returns success/error message based on the 'kind' variable
    kind = kind.lower()
    message = config.message
    indent = ''
    if kind == 'category':
        indent = ''
    if kind == 'theme':
        indent = ''
    if kind == 'part':
        indent = '\t|_'
    if kind == 'step':
        indent = '\t\t|\n\t\t|_'
    if kind == 'file':
        indent = '\t|_'

    return message[msg].format(path, kind.capitalize(), indent)


def get_themes(category_name):
# returns array of dictionaries including all courses from category 'category name'
    category_url = 'http://teamtreehouse.com/library/topic:' + category_name.lower()
    category_page = sess.get(category_url)
    category_page = BeautifulSoup(category_page.text)

    themes = category_page.select('li.card')

    themes_items = [
        {
            "theme_name": theme.find('h3').text,
            "theme_type": theme.find('strong').text.strip(),
            "theme_level": theme.select('.difficulty')[0].text.strip() if theme.select('.difficulty') else '' ,
            "theme_url": BASE_URL + theme.select('a.title')[0]['href']
        }
        for theme in themes]

    for key, theme in enumerate(themes_items):
        url = theme['theme_url']
        description = BeautifulSoup(http_get(url)).find('div', 'hero-meta')
        themes_items[key]['theme_description'] = description

    return themes_items


def get_themes_parts(themes):
    # for each theme adds an array with links to all individual sections it contains
    # returns modified 'themes' array of dictionaries
    for key, theme in enumerate(themes):
        url = theme['theme_url']
        parts = BeautifulSoup(http_get(url)).find_all('div', {'class': 'contained featurette',
                                                   'data-featurette': 'expandable-content-card'})
        themes[key]['theme_parts'] = parts
    return themes


def get_parts_steps(themes):
    # for each theme adds an array with links to all steps/videos it contains
    # returns modified 'themes' array of dictionaries
    for theme in themes:
        parts = theme['theme_parts']
        theme['theme_parts'] = []
        part_count = 1
        for part in parts:

            part_name = str(part_count) + '_' + part.find('a', {'class': 'toggle-steps'}).text
            part_count += 1
            part_desc = part.select('.achievement-meta')[0]
            video_steps = part.select('.icon.icon-video')
            step_videos = []
            if part.select('li.extra-credit'):
                step_extra = [i for i in part.select('li.extra-credit')[0].contents if i.find('markdown') != -1][2:][0]
            else:
                step_extra = None
            video_count = 1
            for video_step in video_steps:
                step_name = str(video_count) + '_' + video_step.find_next_sibling('strong').string
                video_count += 1
                step_duration = video_step.find_next_sibling('p').string
                step_link = video_step.find_parent('a')['href']
                step_videos.append({'step_name': str(step_name).replace('/', '-'), 'duration': step_duration,
                                    'link': BASE_URL + step_link})
            theme['theme_parts'].append(
                {'part_name': part_name, 'part_desc': part_desc, 'extra_step': step_extra, 'step_videos': step_videos})

    return themes


def get_video_attach(themes):
# add 'video_attach' key to the themes courses
# the key includes the urls (based on the parse_video_page function) for each step

    for theme in themes:
        for part in theme['theme_parts']:
            for video in part['step_videos']:
                link = video['link']
                video_links = parse_video_page(link)
                video['video_attach'] = video_links
    return themes


def parse_video_page(link):
# returns dictionary including links to the videos based on the 'link'
    print ("Opening link", link)
    video_page = BeautifulSoup(sess.get(link).text)
    video_meta = video_page.select('#video-meta')[0]
    download_tab = video_page.select('#downloads-tab-content')[0]
    links = download_tab.select('a')
    video_links = {}
    for link in links:
        title = str(link.select('strong')[1 == 10])
        if title.find('Files') != -1:
            video_links['files'] = link['href']
        if title.find('High Definition Video') != -1:
            video_links['video_url'] = BASE_URL + link['href']
        if (title.find('Standard Definition Video') != -1) and video_links.get('video_url', None) is None:
            video_links['video_url'] = BASE_URL + link['href']
        if title.find('Video Transcript') != -1:
            video_links['srt'] = link['href']
    video_links['meta'] = video_meta

    return video_links


def download(themes):
# downloads the videos for each theme in themes
# uses auxiliary functions to create the directory structure
# and to download the actual files based on the URLs
    for theme in themes:
        category = os.path.join(BASE_DIR, category_name)
        theme_path = os.path.join(category, theme['theme_name'] + '_' + str(theme['theme_type']) + ' (level: ' + str(
            theme['theme_level']) + ')')
        make_file(theme['theme_description'], theme_path, 'ThemeDescription.html')
        if str(theme['theme_type']) == 'Workshop':
            video_item = parse_video_page(theme['theme_url'])
            filepath = theme_path
            filename = theme['theme_name']
            _download_attach(video_item, filepath, filename)
        else:
            for part in theme['theme_parts']:
                part_path = os.path.join(theme_path, part['part_name'])
                make_file(part['part_desc'], part_path, 'PartDescription.html')
                if part['extra_step']:
                    make_file(part['extra_step'], part_path, 'Extra.html')
                for video in part['step_videos']:
                    video_item = video['video_attach']
                    filepath = part_path
                    filename = video['step_name']
                    _download_attach(video_item, filepath, filename)


def _download_file(url, path, name):
# Create and fill file based on the URL, overwrites existing file
# If the file does not exist it will create it as well as the path to reach it
    while True:
        try:
            r = sess.get(url, stream=True)
            break
        except Exception:
            continue
    if not os.path.exists(path):
        os.makedirs(path)
    filename = os.path.join(path, name)
    with open(filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=2048):
            if chunk:
                f.write(chunk)
                f.flush()
    print(get_msg('file', filename, 'file'))

    return name


def _download_attach(video_item, filepath, filename):
# Downloads files based on the extension, uses _download_file function to retrieve the file
    video_path = os.path.join(filepath, filename)
    for key in video_item.keys():
        if key is 'meta':
            make_file(video_item['meta'], video_path, 'Meta.html')
            continue
        if key is 'srt':
            ext = '.srt'
        if key is 'video_url':
            ext = '.mp4'
        if key is 'files':
            ext = '.zip'
        if not os.path.exists(os.path.join(video_path, filename + ext)):
            _download_file(video_item[key], video_path, filename + ext)
        else:
            print(get_msg('exist', os.path.join(video_path, filename + ext), 'file'))


def make_file(data, path, name):
# Creates an HTML file for each video item
    if not os.path.exists(path):
        os.makedirs(path)
    with open(os.path.join(path, name), 'w') as file:
        html_prefix = '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">' \
                      '<title>Document</title>' \
                      '<link href="{0}" rel="stylesheet"></link></head><body>'.format(
            os.path.dirname(os.path.realpath(__file__)) + '/assets/markdown.css'
        )
        html_postfix = '</body></html>'
        file.write(html_prefix + str(data).strip() + html_postfix)


def hello_dialog():
# Prints the initial dialog, lists all categories the user can choose to download
# Returns array with chosen categories
    hello = '''
      _____              _   _
     |_   _| __ ___  ___| | | | ___  _   _ ___  ___
       | || '__/ _ \/ _ \ |_| |/ _ \| | | / __|/ _ \\
       | || | |  __/  __/  _  | (_) | |_| \__ \  __/
      _|_||_|  \___|\___|_| |_|\___/ \__,_|___/\___|
     / ___|  __ ___   _____ _ __
     \___ \ / _` \ \ / / _ \ '__|
      ___) | (_| |\ V /  __/ |
     |____/ \__,_| \_/ \___|_|    v0.1
                                                    '''

    category_names = ['HTML', 'CSS', 'Design', 'JavaScript', 'Ruby', 'PHP', 'WordPress', 'iOS', 'Android',
                      'Development-Tools', 'Business', 'Python', 'Digital-Literacy', 'Java']
    cat_list = '\n'.join(['[' + str(key + 1) + '] - ' + val for key, val in enumerate(category_names)])
    hello += '\nAvailable categories:\n' + cat_list + '\n\nSpecify the numbers of categories through space (like this 1 3 6)\n'
    print(hello)

    while True:
        select_cats = input('Enter numbers:')
        try:
            select_cats = list(map(int, select_cats.split(' ')))
        except ValueError:
            continue
        cat_len = len(category_names)
        if len(select_cats) <= cat_len and max(select_cats) <= cat_len: break
    print('[!] You chose: ' + ','.join([category_names[i - 1] for i in select_cats]))

    return [category_names[i - 1] for i in select_cats]


if __name__ == '__main__':
    config = config.main_config
    _user = config.get('user')
    _pass = config.get('password')
    BASE_DIR = config.get('path')
    BASE_URL = config.get('base_url')


    sess = do_auth(_user, _pass)
    category_names = hello_dialog()
    for category_name in category_names:
        themes = get_themes(category_name)
        themes = get_themes_parts(themes)
        themes = get_parts_steps(themes)
        themes = get_video_attach(themes)
        download(themes)

    
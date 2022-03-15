import json
from time import sleep
from turtle import up
from pixivpy3 import AppPixivAPI
import os
import requests
import yaml

api = AppPixivAPI()


class config:
    chat_id = ''
    tg_bot_token = ''
    pixiv_refensh_token = ''


c = config()


# load config
def load_config(path):
    with open(path, 'r') as file:
        yaml_result = yaml.load(file, Loader=yaml.FullLoader)
        c.chat_id = yaml_result['tg_chat_id']
        c.tg_bot_token = yaml_result['tg_bot_token']
        c.pixiv_refensh_token = yaml_result['pixiv_refresh_token']


# replace some char to pass telegram api's restriction
def replace_char(str):
    char_to_replace = {'\\': '\\\\', '_': '\\_', '*': '\\*', '[': '\\[', ']': '\\]', '(': '\\(', ')': '\\)', '~': '\\~', '`': '\\`',
                       '>': '\\>', '#': '\\#', '+': '\\+', '-': '\\-', '=': '\\=', '|': '\\|', '{': '\\{', '}': '\\}', '.': '\\.', '!': '\\!'}
    for key, value in char_to_replace.items():
        str = str.replace(key, value)
    return str


# main method
def update(json_result):
    for illust in json_result.illusts:
        # check whether the pic is new
        if os.path.exists(os.path.join('tmp', '%d.jpg')%illust.id) == False:
            api.download(illust.image_urls['large'],
                        path='tmp', name='%s.jpg' % illust.id)
            # format tags
            tag_caption = str()
            for tag in illust.tags:
                tag_caption += '[\\#%s ](https://www.pixiv.net/tags/%s/artworks)' % (
                    tag.name, tag.name)
            caption = '[%s](https://ww.pixiv.net/artworks/%s)\n%s' % (replace_char(illust.title),
                                                                    illust.id, tag_caption)
            # print sending status
            print("Sending......title: %s id: %s" % (illust.title, illust.id))
            sendingstatus = True
            retrytime = 0
            sendingstatus = send_photo(os.path.join(
                'tmp', '%s.jpg' % illust.id), c.chat_id, caption=caption)
            # if sending failed, retry twice
            while sendingstatus == False and retrytime <= 1:
                retrytime += 1
                sleep(1)
                sendingstatus = send_photo(os.path.join(
                    'tmp', '%s.jpg' % illust.id), c.chat_id, caption=caption)
            if retrytime == 2:
                print('illust.id: %s sending failed after 2 retrys' % illust.id)
            sleep(1)


def send_photo(path, chat_id, caption=None):
    url = 'https://api.telegram.org/bot%s/sendPhoto' % (c.tg_bot_token)
    data = {
        'chat_id': chat_id,
        'caption': caption,
        'parse_mode': 'MarkdownV2'
    }
    with open(path, 'rb') as photo:
        response_text = str()
        try:
            response = requests.post(url, data=data, files={'photo': photo})
            response_text = response.text
            response.raise_for_status()
            if response.status_code == 200:
                return True
        except requests.RequestException as err:
            print('Send to telegram error! '+str(err))
            print(response_text)
            return False


if __name__ == '__main__':
    load_config('config.yaml')
    # login
    api.auth(refresh_token=c.pixiv_refensh_token)
    # create tmp dir if not exist
    if os.path.exists('tmp') == False:
        os.mkdir('tmp')
    # get followed artists new pics
    public = api.illust_follow(restrict='public')
    private = api.illust_follow(restrict='private')
    update(public)
    update(private)

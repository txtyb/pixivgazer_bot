#!/usr/bin/env python

import json
from time import sleep
from pixivpy3 import AppPixivAPI
import os
import requests
import yaml
import json

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


# preserving 60 pics in /tmp
def clean_tmp():
    pics = os.listdir('tmp')
    if len(pics) >=59:
        # sort pics with modified time
        pics = sorted(pics, key = lambda x:os.path.getmtime(os.path.join('tmp', x)))
    else:
        return
    pics_to_del = pics[0:len(pics)-59-1]
    for pic in pics_to_del:
        os.remove(os.path.join('tmp', pic))
    print('cleaned %d pics in tmp'%len(pics_to_del))
    return


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
        file_id = None
        # check whether the pic is new
        if os.path.exists(os.path.join('tmp', '%d.jpg')%illust.id) == False:
            api.download(illust.image_urls['large'],
                        path='tmp', name='%s.jpg' % illust.id)
            # format tags
            tag_caption = str()
            for tag in illust.tags:
                tag_caption += '[\\#%s ](https://www.pixiv.net/tags/%s/artworks)' % (
                    replace_char(tag.name), replace_char(tag.name))
            caption = '[%s](https://www.pixiv.net/artworks/%s)\n%s' % (replace_char(illust.title),
                                                                    illust.id, tag_caption)
            # print sending action
            print("Sending......title: %s id: %s" % (illust.title, illust.id))
            sendingstatus = True
            retrytime = 0
            # send to all the chats
            for per_chat_id in c.chat_id:
                # if file_id exist, then use it
                if file_id != None:
                    send_action = send_photo(os.path.join('tmp', '%s.jpg' % illust.id), per_chat_id, caption=caption, mode='with_id', file_id=file_id)
                    sendingstatus = send_action['status']
                    if sendingstatus:
                        file_id = send_action['file_id']
                    # if sending failed, retry twice
                    while sendingstatus == False and retrytime <= 1:
                        retrytime += 1
                        sleep(1)
                        send_action = send_photo(os.path.join('tmp', '%s.jpg' % illust.id), per_chat_id, caption=caption)
                        sendingstatus = send_action['status']
                        if sendingstatus:
                            file_id = send_action['file_id']
                    if retrytime == 2:
                        print('illust.id: %s sending failed after 2 retrys' % illust.id)
                    sleep(1)
                else:
                    send_action = send_photo(os.path.join('tmp', '%s.jpg' % illust.id), per_chat_id, caption=caption)
                    sendingstatus = send_action['status']
                    if sendingstatus:
                        file_id = send_action['file_id']
                    # if sending failed, retry twice
                    while sendingstatus == False and retrytime <= 1:
                        retrytime += 1
                        sleep(1)
                        send_action = send_photo(os.path.join('tmp', '%s.jpg' % illust.id), per_chat_id, caption=caption)
                        sendingstatus = send_action['status']
                        if sendingstatus:
                            file_id = send_action['file_id']
                    if retrytime == 2:
                        print('illust.id: %s sending failed after 2 retrys' % illust.id)
                    sleep(1)
    # after sending one image, clear file_id
    file_id = None


def get_file_id(jsonstr):
    json_rst = json.loads(jsonstr)
    file_id = json_rst['result']['photo'][0]['file_id']
    return file_id


def send_photo(path, chat_id, caption=None, mode='with_file', file_id=None):
    url = 'https://api.telegram.org/bot%s/sendPhoto' % (c.tg_bot_token)
    data = {
        'chat_id': chat_id,
        'caption': caption,
        'parse_mode': 'MarkdownV2'
    }
    # sending with file
    if mode == 'with_file':
        with open(path, 'rb') as photo:
            response_text = str()
            try:
                response = requests.post(url, data=data, files={'photo': photo})
                response_text = response.text
                response.raise_for_status()
                if response.status_code == 200:
                    file_id = get_file_id(response.text)
                    return {'status': True, 'file_id': file_id}
            except requests.RequestException as err:
                print('Send to telegram error! '+str(err))
                print(response_text)
                return {'status': False, 'file_id': None}
    # sending with file_id
    elif mode == 'with_id':
        response_text = str()
        try:
            data['photo'] = file_id
            response = requests.post(url, data=data)
            response_text = response.text
            response.raise_for_status()
            if response.status_code == 200:
                file_id = get_file_id(response.text)
                return {'status': True, 'file_id': file_id}
        except requests.RequestException as err:
            print('Send to telegram error! '+str(err))
            print(response_text)
            return {'status': False, 'file_id': None}


if __name__ == '__main__':
    # create tmp dir if not exist
    if os.path.exists('tmp') == False:
        os.mkdir('tmp')
    clean_tmp()
    load_config('config.yaml')
    # login
    api.auth(refresh_token=c.pixiv_refensh_token)
    # get followed artists new pics
    public = api.illust_follow(restrict='public')
    private = api.illust_follow(restrict='private')
    # update
    update(public)
    update(private)

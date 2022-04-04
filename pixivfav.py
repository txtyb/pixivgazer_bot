#!/usr/bin/env python

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
    last_updated = dict()


c = config()


# use this to fix relative path
def relative_path_fix(path_relative):
    return os.path.join(os.path.dirname(__file__), path_relative)


# load config
def load_config(path):
    with open(path, 'r') as file:
        yaml_result = yaml.load(file, Loader=yaml.FullLoader)
        c.chat_id = yaml_result['tg_chat_id']
        c.tg_bot_token = yaml_result['tg_bot_token']
        c.pixiv_refensh_token = yaml_result['pixiv_refresh_token']
    # load last updated id list
    # if '.last_updated.yaml' not exist, give an empty init
    if os.path.exists(relative_path_fix('.last_updated.yaml')) == False:
        c.last_updated = {
            'private': [], 
            'public': []
        }
    else:
        with open(relative_path_fix('.last_updated.yaml'), 'r') as file:
            c.last_updated = yaml.load(file, Loader=yaml.FullLoader)


# preserving 60 pics in /tmp
def clean_tmp():
    pics = os.listdir(relative_path_fix('tmp'))
    if len(pics) >=59:
        # sort pics with modified time
        pics = sorted(pics, key = lambda x:os.path.getmtime(os.path.join(relative_path_fix('tmp'), x)))
    else:
        return
    pics_to_del = pics[0:len(pics)-59-1]
    for pic in pics_to_del:
        os.remove(os.path.join(relative_path_fix('tmp'), pic))
    print('cleaned %d pics in tmp'%len(pics_to_del))
    return


# replace some char to pass telegram api's restriction
def replace_char(str):
    char_to_replace = {'\\': '\\\\', '_': '\\_', '*': '\\*', '[': '\\[', ']': '\\]', '(': '\\(', ')': '\\)', '~': '\\~', '`': '\\`',
                       '>': '\\>', '#': '\\#', '+': '\\+', '-': '\\-', '=': '\\=', '|': '\\|', '{': '\\{', '}': '\\}', '.': '\\.', '!': '\\!'}
    for key, value in char_to_replace.items():
        str = str.replace(key, value)
    return str


# check newly get illusts list with '.last_updated.yaml'
def updated_check(jsondict):
    need_update = list()
    for illust in jsondict.illusts:
        if illust.id not in c.last_updated['public'] and illust.id not in c.last_updated['private']:
            need_update.append(illust.id)
    return need_update
                

''' 
dump updated pics list to '.last_updated.yaml'
typedict exp: {
    'public': jsondict1, 
    'private': jsondict2
}
'''
def updated_dump(typedict):
    for type in typedict:
        id_dict = dict()
        # write public and private type ids seperatly
        for key, value in typedict.items():
            id_dict[key] = list()
            for illust in value.illusts:
                id_dict[key].append(illust.id)

    dump = yaml.dump(id_dict)

    with open(relative_path_fix('.last_updated.yaml'), 'w') as file:
        file.write(dump)


# main method
def update(json_result):
    # gen need_update_list
    need_update_list = updated_check(json_result)
    for id in need_update_list:
        file_id = None
        detail = api.illust_detail(id).illust
        api.download(detail.image_urls['large'], path=relative_path_fix('tmp'), name='%s.jpg' % detail.id)
        # format tags
        tag_caption = str()
        for tag in detail.tags:
            tag_caption += '[\\#%s ](https://www.pixiv.net/tags/%s/artworks)' % (replace_char(tag.name), replace_char(tag.name))
        # format user
        user_caption = '[%s](https://www.pixiv.net/users/%s)'%(replace_char(detail.user.name), detail.user.id)
        # format caption
        caption = '[%s](https://www.pixiv.net/artworks/%s)\nartist: %s\n%s' % (replace_char(detail.title),detail.id, user_caption, tag_caption)
        # print sending action
        print("Sending......title: %s id: %s" % (detail.title, detail.id))
        sendingstatus = True
        # send to all the chats
        for per_chat_id in c.chat_id:
            # if file_id exist, then use it
            if file_id != None:
                send_action = send_and_retry(os.path.join(relative_path_fix('tmp'), '%s.jpg' % detail.id), per_chat_id, caption=caption, mode='with_id', file_id=file_id)
                sendingstatus = send_action['rst']
                if sendingstatus:
                    file_id = send_action['file_id']
                else:
                    print('illust.id: %s sending failed after 2 retrys' % detail.id)
                sleep(1)
            else:
                send_action = send_and_retry(os.path.join(relative_path_fix('tmp'), '%s.jpg' % detail.id), per_chat_id, caption=caption)
                sendingstatus = send_action['rst']
                if sendingstatus:
                    file_id = send_action['file_id']
                else:
                    print('illust.id: %s sending failed after 2 retrys' % detail.id)
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

# retry twice if failed
def send_and_retry(path, chat_id, caption=None, mode='with_file', file_id=None):
    send_action = send_photo(path, chat_id, caption=caption, mode=mode, file_id=file_id)
    sendingstatus = send_action['status']
    if sendingstatus:
        file_id = send_action['file_id']
        return {'rst': True, 'file_id': file_id}
    # if sending failed, retry twice
    retrytime = 0
    while sendingstatus == False and retrytime <= 1:
        retrytime += 1
        sleep(1)
        send_action = send_photo(path, chat_id, caption=caption, mode=mode, file_id=file_id)
        sendingstatus = send_action['status']
        if sendingstatus:
            file_id = send_action['file_id']
            return {'rst': True, 'file_id': file_id}
    if retrytime == 2:
        return {'rst': False, 'file_id': file_id}


if __name__ == '__main__':
    # create tmp dir if not exist
    if os.path.exists(relative_path_fix('tmp')) == False:
        os.mkdir(relative_path_fix('tmp'))
    clean_tmp()
    load_config(relative_path_fix('config.yaml'))
    # login
    api.auth(refresh_token=c.pixiv_refensh_token)
    # get followed artists new pics
    public = api.illust_follow(restrict='public')
    private = api.illust_follow(restrict='private')
    # use for updated_dump
    typedict1 = {
        'public': public, 
        'private': private
    }
    # update
    update(public)
    update(private)
    # dump updated pics ids to ',last_updated.yaml'
    updated_dump(typedict1)

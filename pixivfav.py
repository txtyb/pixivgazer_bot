#!/usr/bin/env python

from ast import Nonlocal
from email.mime import image
from locale import getlocale
from time import sleep
from typing import overload
from unicodedata import name
from xml.dom import NamespaceErr
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
    # pics_list is a bunch of pic_dict()
    pics_list = list()
    for id in need_update_list:
        ''' 
        to store info of this id, something like
        img_urls:
            - https://i.pximg.net/img-original/img/2022/04/04/23/33/28/97411352_p0.jpg
            - https://i.pximg.net/img-original/img/2022/04/04/23/33/28/97411352_p1.jpg
        caption: aweadga
        overten: False
        count: 5
        title: gahsdfgha
        id: 785859
        '''
        pic_dict = dict()
        pic_dict['img_urls'] = list()
        file_ids = list()
        detail = api.illust_detail(id).illust
        count = detail['page_count']
        pic_dict['count'] = count
        current_count = 0
        pic_dict['title'] = detail.title
        pic_dict['id'] = detail.id
        meta_page = list()
        if count == 1:
            meta_page.append(detail.meta_single_page)
        else:
            meta_page = detail.meta_pages
        overten = False
        for img in meta_page:
            # if pic's quantity is over 10, only get 10 pics
            if current_count == 10:
                overten = True
                break
            if count == 1:
                url = img['original_image_url']
            else:
                url = img.image_urls['original']
            pic_dict['img_urls'].append(url)
            current_count += 1
        pic_dict['overten'] = overten
        # format tags
        tags_caption = str()
        for tag in detail.tags:
            tags_caption += '[\\#%s ](https://www.pixiv.net/tags/%s/artworks)' % (replace_char(tag.name), replace_char(tag.name))
        # format user
        user_caption = '[%s](https://www.pixiv.net/users/%s)'%(replace_char(detail.user.name), detail.user.id)
        # format caption
        pic_dict['caption'] = '[%s](https://www.pixiv.net/artworks/%s)\nartist: %s\n%s' % (replace_char(detail.title),detail.id, user_caption, tags_caption)
        # add current pic_dict into pics_list
        pics_list.append(pic_dict)
    for pic in pics_list:
        # send pics
        # print sending action msg
        print("Sending......title: %s id: %s" % (pic['title'], pic['id']))
        urls = pic['img_urls']
        names = list()
        for url in urls:
            # exp: '97411352_p0.jpg'
            name = url.split('/')[-1]
            names.append(name)
            # if count >= 2:
            #     print('processing %s'%name)
            # download pic
            api.download(url, path=relative_path_fix('tmp'), name=name)
        sendingstatus = True
        caption = pic['caption']
        count = pic['count']
        # list to pass data to send func
        '''
        exp: info
        list({'name': name1, 'file_id': file_id1}, {'name': name2, 'file_id': file_id2}...)
        '''
        info = list()
        for name in names:
            info.append(
                {'name': name,
                 'file_id': None
                 })
        # send to all the chats
        for per_chat_id in c.chat_id:
            send_action = send_and_retry(info, per_chat_id, caption=caption)
            sendingstatus = send_action['rst']
            if sendingstatus:
                info = send_action['info']
            else:
                print('%s sending failed after 2 retrys' % name)
            sleep(1)
        # after sending one pic, clear info
        info = None


def get_file_id(jsonstr):
    json_rst = json.loads(jsonstr)
    file_id = json_rst['result']['photo'][0]['file_id']
    return file_id


def send_photo(info, chat_id, caption=None):
    # names = info['names']
    # file_ids = info['file_ids']
    # paths = list(map(lambda x: os.path.join(relative_path_fix('tmp'), x), names))
    count = len(info)
    # decide msg_type
    msg_type = 'single'
    if count > 1:
        msg_type = 'group'
    i = 0
    for pic in info:
        name = pic['name']
        file_id = pic['file_id']
        path = os.path.join(relative_path_fix('tmp'), name)
        # decide sending mode
        mode = 'with_file'
        if file_id != None:
            mode = 'with_id'
        # only one pic
        if msg_type == 'single':
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
                            info[i]['file_id'] = file_id
                            return {'status': True, 'info': info}
                    except requests.RequestException as err:
                        print('Send to telegram error! '+str(err))
                        print(response_text)
                        return {'status': False, 'info': info}
            # sending with file_id
            elif mode == 'with_id':
                response_text = str()
                try:
                    data['photo'] = file_id
                    response = requests.post(url, data=data)
                    response_text = response.text
                    response.raise_for_status()
                    if response.status_code == 200:
                        return {'status': True, 'info': info}
                except requests.RequestException as err:
                    print('Send to telegram error! '+str(err))
                    print(response_text)
                    return {'status': False, 'info': info}
        i += 1

# retry twice if failed
def send_and_retry(info, chat_id, caption=None):
    send_action = send_photo(info, chat_id, caption=caption)
    sendingstatus = send_action['status']
    if sendingstatus:
        info = send_action['info']
        return {'rst': True, 'info': info}
    # if sending failed, retry twice
    retrytime = 0
    while sendingstatus == False and retrytime <= 1:
        retrytime += 1
        sleep(1)
        send_action = send_photo(info, chat_id, caption=caption)
        sendingstatus = send_action['status']
        if sendingstatus:
            info = send_action['info']
            return {'rst': True, 'info': info}
    if retrytime == 2:
        return {'rst': False, 'info': info}


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

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
    def download(pic, path):
        width = pic['width']
        height = pic['height']
        count = len(pic['img_urls'])
        id = pic['id']
        urls = list()
        # file names to send
        names = list()
        # if px too big, then download 'large' instead of 'original'
        if width + height >= 10000:
            detail = api.illust_detail(id).illust
            # if multiple
            if count > 1:
                for page in detail.meta_pages:
                    url = page['image_urls']['large']
                    urls.append(url)
            # if single
            elif count ==1:
                url = detail.image_urls['large']
                urls.append(url)
        else:
            urls = pic['img_urls']
        # only download 10 pics if overten
        if pic['overten']:
            urls = urls[0:11]
        for url in urls:
            # exp: '97411352_p0.jpg'
            name = url.split('/')[-1]
            # download pic
            api.download(url, path=relative_path_fix('tmp'), name=name)
            # size in MB
            size = os.path.getsize(os.path.join(relative_path_fix('tmp'), name))/(1024*1024.0)
            if size > 10:
                detail = api.illust_detail(id).illust
                # if multiple
                if count > 1:
                    # name is something like '97423306_p1.jpg', number = 1
                    number = int(name.split('.')[0].split('_')[1][1:])
                    pages = detail.meta_pages
                    url_new = pages[number]['image_urls']['large']
                    name = url_new.split('/')[-1] 
                    api.download(url_new, path=relative_path_fix('tmp'), name=name)
                # if single
                elif count ==1:
                    url_new = detail.image_urls['large']
                    name = url_new.split('/')[-1] 
                    api.download(url_new, path=relative_path_fix('tmp'), name=name)
            names.append(name)

        return names


    # gen need_update_list
    need_update_list = updated_check(json_result)
    # pics_list contains a bunch of pic_dict()
    pics_list = list()
    for id in need_update_list:
        ''' 
        to store info of this id, something like
        'img_urls':
            - https://i.pximg.net/img-original/img/2022/04/04/23/33/28/97411352_p0.jpg
            - https://i.pximg.net/img-original/img/2022/04/04/23/33/28/97411352_p1.jpg
        'caption': aweadga
        'overten': False
        'count': 5
        'title': gahsdfgha
        'id': 785859
        'width': 715
        'height' :1000
        '''
        pic_dict = dict()
        pic_dict['img_urls'] = list()
        detail = api.illust_detail(id).illust
        count = detail['page_count']
        pic_dict['count'] = count
        current_count = 0
        pic_dict['title'] = detail.title
        pic_dict['id'] = detail.id
        pic_dict['width'] = detail.width
        pic_dict['height'] = detail.height
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
        # download pics, return file names to send
        names = download(pic, relative_path_fix('tmp'))
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


def send_photo(info, chat_id, caption=None):
    def get_file_id(jsonstr):
        json_rst = json.loads(jsonstr)
        file_id = json_rst['result']['photo'][-1]['file_id']
        return file_id


    def get_group_file_id(jsonstr):
        json_rst = json.loads(jsonstr)
        file_ids = list()
        for photo in json_rst['result']:
            file_id = photo['photo'][-1]['file_id']
            file_ids.append(file_id)
        return file_ids
    

    # names = info['names']
    # file_ids = info['file_ids']
    # paths = list(map(lambda x: os.path.join(relative_path_fix('tmp'), x), names))
    count = len(info)
    # decide msg_type
    msg_type = 'single'
    if count > 1:
        msg_type = 'group'
    # use for sending mediagroup
    media_array = list()
    # files sending with_file
    files = dict()
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
        # send mediagroup
        elif msg_type == 'group':
            url = 'https://api.telegram.org/bot%s/sendMediaGroup' % (c.tg_bot_token)
            # construct InputMediaPhoto
            InputMediaPhoto = {
                'type': 'photo'
            }
            if mode == 'with_file':
                InputMediaPhoto['media'] = 'attach://%s'%name
                # need to close later
                file = open(path, 'rb')
                files['%s'%name] = file
            elif mode == 'with_id':
                InputMediaPhoto['media'] = file_id
            # append to media_array
            media_array.append(InputMediaPhoto)
        i += 1
    # make request to send mediagroup
    if msg_type == 'group':
        data = {
            'chat_id': chat_id,
            'media': json.dumps(media_array)
        }
        response_text = str()
        response2_text = str()
        try:
            response = requests.post(url, data=data, files=files)
            # close all the file
            for name, file in files.items():
                file.close()
            response_text = response.text
            response.raise_for_status()
            file_ids = list()
            if response.status_code == 200:
                file_ids = get_group_file_id(response.text)
                for file_id, pic in zip(file_ids, info):
                    pic['file_id'] = file_id
            url2 = 'https://api.telegram.org/bot%s/sendMessage' % (c.tg_bot_token)
            data2 = {
                'chat_id': chat_id,
                'text': caption,
                'parse_mode': 'MarkdownV2', 
                'disable_web_page_preview': True
            }
            # send caption for a single msg
            response2 = requests.post(url2, data=data2)
            response2_text = response2.text
            response2.raise_for_status()
            return {'status': True, 'info': info}
        except requests.RequestException as err:
            print('Send to telegram error! '+str(err))
            if response2_text:
                print(response2_text)
            else:
                print(response_text)
            return {'status': False, 'info': info}


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

import logging
import os
import requests
import json
from pixivpy3 import AppPixivAPI
from config import c
from utils import relativePathFix, replaceChar
from PIL import Image as pillowImage
from time import sleep
from datetime import datetime
from ugoira import ugoira as convertUgoira

api = AppPixivAPI()

# login
api.auth(refresh_token=c.pixiv_refensh_token)
# set language for getting translated tags
api.set_accept_language('zh-cn')


class Image:
    def __init__(self):
        self.imgUrls = list()
        self.caption = str()
        self.overten = bool()
        self.count = int()
        self.single = bool()
        self.title = str()
        self.id = int()
        self.height = int()
        self.width = int()
    

    def download(self):
        def compressUderSize(path, size):
            qual = 95
            currentSize = os.path.getsize(path)/(1024*1024.0)
            while currentSize > size:
                if qual == 0:
                    logging.error('%d can not be compressed below 10MB'%self.id)
                    break

                im = pillowImage.open(path)
                # if the original pic is png, then convert it to jpeg in order to compress
                if path.split('.')[-1] == 'png':
                    im = im.convert('RGB')
                im.save(path, 'JPEG', quality=qual)
                currentSize = os.path.getsize(path)/(1024*1024.0)
                qual -= 5


        # only download 10 pics if overten
        if self.overten:
            self.imgUrls = self.imgUrls[0:10]

        fileNames = list()
        for url in self.imgUrls:
            path = relativePathFix(os.path.join('..', 'tmp'))
            # exp: '97411352_p0.jpg'
            name = url.split('/')[-1]
            # download pic
            print('%d ' % self.id, end='')
            status = api.download(url, path=path, name=name)
            im = pillowImage.open(os.path.join(path, name))
            (imWidth, imHeight) = im.size
            ratio = imWidth/imHeight
            # resize
            if imWidth+imHeight > 10000:
                logging.info('Resizing......')
                newHeight = 10000/(1+ratio)
                newWidth = ratio*newHeight
                newHeight, newWidth = int(newHeight), int(newWidth)
                out = im.resize((newWidth, newHeight))
                out.save(os.path.join(path, name), quality=95)
            # size in MB
            size = os.path.getsize(os.path.join(path, name))/(1024*1024.0)
            if size > 10:
                logging.info('Compressing...... %d is %.1fMB, '%(self.id, size))
                compressUderSize(os.path.join(path, name), 10)
            fileNames.append(name)

        # return downloaded object
        # if single, return type and Photo
        if self.single:
            photo = Photo(fileNames[0], self.caption, self.title, self.id)
            return ['Photo', photo]
        # if not single, return type, MediaGroup, Msg in sequence
        else:
            mediaGroup = MediaGroup(fileNames, self.title, self.id)
            msg = Msg(self.caption)
            return ['MediaGroup', mediaGroup, msg]


class ImageUgoira(Image):
    def download(self):
        def getZipUrl():
            jsonRst = api.ugoira_metadata(self.id)
            self.zipUrl = jsonRst.ugoira_metadata.zip_urls.medium
            self.metaData = jsonRst.ugoira_metadata

        def genGif():
            self.fileName = self.zipFileName.split('.')[0] + '.gif'
            convertUgoira(1, 'gif', os.path.join(path, self.fileName), os.path.join(path, self.zipFileName), self.metaData)

        
        path = relativePathFix(os.path.join('..', 'tmp'))
        getZipUrl()
        self.zipFileName = self.zipUrl.split('/')[-1]
        status = api.download(self.zipUrl, path=path, name=self.zipFileName)
        logging.info('Generating GIF......id: %d' % self.id)
        genGif()

        ugoira = Ugoira(self.fileName, self.caption, self.title, self.id)
        # os.remove(os.path.join(path, self.zipFileName))
        return ['Ugoira', ugoira]


class ObjectToSend():
    def sendAndRetry(self, chatId):
        # retry twice if failed
        retryTime = 2

        status = False
        flag = 0
        while (status == False) and (flag <= retryTime):
            rst = self.send(chatId)
            status = rst[0]
            statusCode = rst[1]
            if statusCode == 429:
                logging.warning('Too many requests! Sleep 60 Secs......')
                sleep(60)
            elif statusCode == 400:
                logging.error('Bad request!')
                break
            # don't retry client errors
            elif str(statusCode)[0] == 4:
                logging.error('Client error!')
                status = True
                break
            flag += 1
            if (flag <= retryTime) and (status is False):
                sleep(1)
            
        if status:
            return True
        else:
            logging.error('Sending failed after 2 retrys......title: %s id: %d' % (self.title, self.id))
            return False


class Photo(ObjectToSend):
    def __init__(self, fileName, caption, title, id, fileId=None):
        self.fileName = fileName
        self.fileId = fileId
        self.caption = caption
        self.title = title
        self.id = id

    
    def getFileId(self, jsonStr):
        jsonRst = json.loads(jsonStr)
        fileId = jsonRst['result']['photo'][-1]['file_id']
        self.fileId = fileId

    
    def send(self, chatId):
        path = relativePathFix(os.path.join('..', 'tmp', self.fileName))
        url = 'https://api.telegram.org/bot%s/sendPhoto' % (c.tg_bot_token)
        data = {
            'chat_id': chatId,
            'caption': self.caption,
            'parse_mode': 'MarkdownV2'
        }
        # send with file
        if self.fileId is None:
            with open(path, 'rb') as photo:
                responseText = str()
                statusCode = int()
                try:
                    response = requests.post(url, data=data, files={'photo': photo})
                    responseText = response.text
                    statusCode = response.status_code
                    response.raise_for_status()
                    if response.status_code == 200:
                        # get fileId
                        self.getFileId(response.text)
                        return [True, statusCode]
                except requests.RequestException as err:
                    logging.error('Send to telegram error! '+str(err))
                    logging.info(responseText)
                    return [False, statusCode]
        # send with fileId
        else:
            responseText = str()
            statusCode = int()
            try:
                data['photo'] = self.fileId
                response = requests.post(url, data=data)
                responseText = response.text
                statusCode = response.status_code
                response.raise_for_status()
                if response.status_code == 200:
                    return [True, statusCode]
            except requests.RequestException as err:
                logging.error('Send to telegram error! '+str(err))
                logging.info(responseText)
                return [False, statusCode]


class MediaGroup(ObjectToSend):
    def __init__(self, fileNames, title, id, fileIds=None):
        self.fileNames = list()
        self.fileIds = list()
        self.mediaArray = list()
        # {'12345p0.jpg': file object1, etc...}
        self.files = dict()
        self.title = str()
        self.id = int()

        self.fileNames = fileNames
        self.fileIds = fileIds
        self.title = title
        self.id = id


    def genMediaArray(self):
        # clean mediaArray
        self.mediaArray = list()
        InputMediaPhoto = dict()
        if self.fileIds is None:
            for name in self.fileNames:
                path = relativePathFix(os.path.join('..', 'tmp', name))
                # construct InputMediaPhoto
                InputMediaPhoto = {
                    'type': 'photo'
                }
                InputMediaPhoto['media'] = 'attach://%s'%name
                # need to close later
                file = open(path, 'rb')
                self.files['%s'%name] = file
                # append to mediaArray
                self.mediaArray.append(InputMediaPhoto)
        else:
            for index, name in enumerate(self.fileNames):
                # construct InputMediaPhoto
                InputMediaPhoto = {
                    'type': 'photo'
                }
                InputMediaPhoto['media'] = self.fileIds[index]
                # append to mediaArray
                self.mediaArray.append(InputMediaPhoto)
        

    def getFileIds(self, jsonStr):
        jsonRst = json.loads(jsonStr)
        fileIds = list()
        for photo in jsonRst['result']:
            fileId = photo['photo'][-1]['file_id']
            fileIds.append(fileId)
        self.fileIds = fileIds


    # if keepFilesOpen == False, files will be closed after sending
    def send(self, chatId):
        # generate the mediaArray
        self.genMediaArray()

        url = 'https://api.telegram.org/bot%s/sendMediaGroup' % (c.tg_bot_token)
        data = {
            'chat_id': chatId,
            'media': json.dumps(self.mediaArray)
        }
        responseText = str()
        statusCode = int()
        try:
            response = requests.post(url, data=data, files=self.files)
            responseText = response.text
            statusCode = response.status_code
            response.raise_for_status()
            if response.status_code == 200:
                # get file ids
                self.getFileIds(response.text)

                # close all the file
                if self.files is not None:
                    for name, file in self.files.items():
                        file.close()
                    # init this attr to None
                    self.files = None
                        
                return [True, statusCode]
        except requests.RequestException as err:
            logging.error('Send to telegram error! type: MediaGroup '+str(err))
            logging.info(responseText)
            return [False, statusCode]


class Msg(ObjectToSend):
    def __init__(self, caption):
        self.caption = caption


    def send(self, chatId):
        responseText = str()
        statusCode = int()
        url = 'https://api.telegram.org/bot%s/sendMessage' % (c.tg_bot_token)
        data = {
            'chat_id': chatId,
            'text': self.caption,
            'parse_mode': 'MarkdownV2', 
            'disable_web_page_preview': True
        }
        try:
            # send caption for a single msg
            response = requests.post(url, data=data)
            responseText = response.text
            statusCode = response.status_code
            response.raise_for_status()
            return [True, statusCode]
        except requests.RequestException as err:
            logging.error('Send to telegram error! type: Msg '+str(err))
            logging.info(responseText)
            return [False, statusCode]


class Ugoira(ObjectToSend):
    def __init__(self, fileName, caption, title, id, fileId=None):
        self.fileName = fileName
        self.fileId = fileId
        self.caption = caption
        self.title = title
        self.id = id


    def getFileId(self, jsonStr):
        jsonRst = json.loads(jsonStr)
        fileId = jsonRst['result']['document']['file_id']
        self.fileId = fileId


    def send(self, chatId):
        path = relativePathFix(os.path.join('..', 'tmp', self.fileName))
        url = 'https://api.telegram.org/bot%s/sendAnimation' % (c.tg_bot_token)
        data = {
            'chat_id': chatId,
            'caption': self.caption,
            'parse_mode': 'MarkdownV2'
        }
        # send with file
        if self.fileId is None:
            with open(path, 'rb') as animation:
                responseText = str()
                statusCode = int()
                try:
                    response = requests.post(url, data=data, files={'animation': animation})
                    responseText = response.text
                    statusCode = response.status_code
                    response.raise_for_status()
                    if response.status_code == 200:
                        # get fileId
                        self.getFileId(response.text)
                        return [True, statusCode]
                except requests.RequestException as err:
                    logging.error('Send to telegram error! '+str(err))
                    logging.info(responseText)
                    return [False, statusCode]
        # send with fileId
        else:
            responseText = str()
            statusCode = int()
            try:
                data['animation'] = self.fileId
                response = requests.post(url, data=data)
                responseText = response.text
                statusCode = response.status_code
                response.raise_for_status()
                if response.status_code == 200:
                    return [True, statusCode]
            except requests.RequestException as err:
                logging.error('Send to telegram error! '+str(err))
                logging.info(responseText)
                return [False, statusCode]

class Update:
    def __init__(self, type):
        # contain a bunch of UpdateItem objects
        self.updateList = list()
        self.jsonResult = str()
        self.type = str()
        # picsList contains a bunch of Image instances
        self.picsList = list()
        # contain Image and MediaGroup instances to send
        self.sendList = list()
        # image that being successfully sent
        self.updatedDump = list()

        self.type = type
        # get followed artists new pics
        if type == 'public':
            self.jsonResult = api.illust_follow(restrict='public')
        elif type == 'private':
            self.jsonResult = api.illust_follow(restrict='private')


    def dump(self):
        if not (len(self.updatedDump) == 0):
            c.dump(self.type, self.updatedDump, self.updateList)


    def send(self):
        chatIds = c.chat_id
        for i in self.sendList:
            # print sending action msg
            if (type(i) == Photo) or (type(i) == MediaGroup) or (type(i) == Ugoira):
                logging.info("Sending......title: %s id: %s" % (i.title, i.id))
            # sending Msg object, logging nothing
            else:
                pass
            for chatId in chatIds:
                status = i.sendAndRetry(chatId)
                if status:
                    # add id to updated ids' list
                    if (type(i) is not Msg) and (i.id not in self.updatedDump):
                        self.updatedDump.append(i.id)
                else:
                    logging.error('%s sending failed after 2 retrys in chat %d' % ('Msg' if type(i) == Msg else i.id, chatId))
                sleep(1)


    def update(self):
        class UpdateItem:
            def __init__(self, id, time, type):
                self.id = id
                self.time = toTimestamp(time)
                self.type = type


        # convert datetime string like '2022-06-04T00:32:12+09:00' to timestamp
        def toTimestamp(time):
            time = time[0:-3] + '00'
            a = datetime.strptime(time, '%Y-%m-%dT%H:%M:%S%z')
            return int(a.timestamp())
        
        
        def genUpdateList():
            needUpdate = list()
            idList = list()
            # extract ids from the list of dicts
            for i in c.last_updated[self.type]:
                idList.append(i['id'])

            for illust in self.jsonResult.illusts:
                if illust.id not in idList:
                    item = UpdateItem(illust.id, illust.create_date, illust.type)
                    needUpdate.append(item)

            # test
            def test():
                item = UpdateItem(91173737, '2022-06-06T01:09:03+09:00', 'ugoira')
                needUpdate.append(item)
                item = UpdateItem(98536884, '2022-06-06T02:09:03+09:00', 'ugoira')
                needUpdate.append(item)
                item = UpdateItem(98807008, '2022-06-06T02:09:03+09:00', 'illust')
                needUpdate.append(item)
                item = UpdateItem(98766380, '2022-06-06T00:09:03+09:00', 'ugoira')
                needUpdate.append(item)
            # test()
            
            # make sure the last is the latest, and images should also be sent in that order
            needUpdate = needUpdate[::-1]
            self.updateList = needUpdate


        def genPicsList():
            # picsList contains a bunch of Image instances
            picsList = list()

            for i in self.updateList:
                ''' 
                to store info of this id, something like
                'img_urls':
                    - https://i.pximg.net/img-original/img/2022/04/04/23/33/28/97411352_p0.jpg
                    - https://i.pximg.net/img-original/img/2022/04/04/23/33/28/97411352_p1.jpg
                'caption': 'aweadga'
                'overten': False
                'count': 5
                'title': gahsdfgha
                'id': 785859
                'width': 715
                'height' :1000
                'single' : False
                '''
                id = i.id
                
                if i.type == 'ugoira':
                    image = ImageUgoira()
                else:
                    image = Image()

                detail = api.illust_detail(id).illust
                count = detail['page_count']
                image.count = count
                image.title = detail.title
                image.id = detail.id
                image.width = detail.width
                image.height = detail.height

                single = bool()
                if count == 1:
                    single = True
                else:
                    single = False
                image.single = single

                metaPage = list()
                if single:
                    metaPage.append(detail.meta_single_page)
                else:
                    metaPage = detail.meta_pages
                overten = False
                for currentCount, img in enumerate(metaPage, 1):
                    # if pic's quantity is over 10, only get 10 pics
                    if currentCount == 10:
                        overten = True
                        # break
                    if single:
                        url = img['original_image_url']
                    else:
                        url = img.image_urls['original']
                    image.imgUrls.append(url)
                image.overten = overten
                # format tags
                tagsCaption = str()
                for tag in detail.tags:
                    # add translated tag names if exist
                    tagName = '%s%s' % (tag.name, ('「%s」' % tag.translated_name) if tag.translated_name else '')
                    tagNameReplaced = replaceChar(tagName)
                    tagsCaption += '[\\#%s  ](https://www.pixiv.net/tags/%s/artworks)' % (
                        tagNameReplaced, replaceChar(tag.name))
                # format user
                userCaption = '[%s](https://www.pixiv.net/users/%s)' % (
                    replaceChar(detail.user.name), detail.user.id)
                # format caption
                image.caption = '[%s](https://www.pixiv.net/artworks/%s)%s\nartist: %s\n%s' % (
                    replaceChar(detail.title), detail.id, '' if count == 1 else ' %dp' % count, userCaption, tagsCaption)
                # add current image into picsList
                picsList.append(image)

            self.picsList = picsList


        def download():
            # contain Image and MediaGroup instances to send
            sendList = list()
            logging.info('Downloading......')
            for pic in self.picsList:
                # download
                obj = pic.download()
                if obj[0] == 'Photo' or obj[0] == 'Ugoira':
                    sendList.append(obj[1])
                elif obj[0] == 'MediaGroup':
                    sendList.append(obj[1])
                    sendList.append(obj[2])
            # \n
            print('')
            logging.info('Done! ')
            self.sendList = sendList


        genUpdateList()
        # test()
        genPicsList()
        if not (len(self.picsList) == 0):
            download()


def test():
    public = Update('public')
    test = public.update()

    logging.debug(1)


if __name__ == '__main__':
    test()

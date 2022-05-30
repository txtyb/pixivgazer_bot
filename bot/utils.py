import os
import logging

# use this to fix relative path
def relativePathFix(pathRelative):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), pathRelative)


# replace some char to pass telegram api's restriction
def replaceChar(str):
    char_to_replace = {'\\': '\\\\', '_': '\\_', '*': '\\*', '[': '\\[', ']': '\\]', '(': '\\(', ')': '\\)', '~': '\\~', '`': '\\`',
                       '>': '\\>', '#': '\\#', '+': '\\+', '-': '\\-', '=': '\\=', '|': '\\|', '{': '\\{', '}': '\\}', '.': '\\.', '!': '\\!'}
    for key, value in char_to_replace.items():
        str = str.replace(key, value)
    return str


# preserving 60 pics in /tmp
def cleanTmp():
    path = relativePathFix(os.path.join('..', 'tmp'))
    pics = os.listdir(path)
    if len(pics) >=59:
        # sort pics with modified time
        pics = sorted(pics, key = lambda x:os.path.getmtime(os.path.join(path, x)))
    else:
        return
    picsToDel = pics[0:len(pics)-59-1]
    for pic in picsToDel:
        os.remove(os.path.join(path, pic))
    logging.info('Cleaned %d pics in tmp'%len(picsToDel))
    return

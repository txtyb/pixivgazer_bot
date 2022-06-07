#!/usr/bin/env python

import sys
import logging
from update import Update
from utils import cleanTmp

# set logger
logger = logging.getLogger('')
logger.setLevel(logging.INFO)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%a, %Y %b %d %H:%M:%S')
ch.setFormatter(formatter)
logger.addHandler(ch)


def test():
    # logger.setLevel(logging.DEBUG)
    # ch.setLevel(logging.DEBUG)

    cleanTmp()
    public = Update('public')
    public.update()
    public.send()
    public.dump()
    logging.debug('Test done')


if __name__ == '__main__':
    # test()
    
    cleanTmp()
    public = Update('public')
    public.update()
    public.send()
    public.dump()

    private = Update('private')
    private.update()
    private.send()
    private.dump()
    
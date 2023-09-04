import yaml, os
from utils import relativePathFix

class Config:
    def __init__(self):
        self.chat_id = ''
        self.tg_bot_token = ''
        self.pixiv_refensh_token = ''
        self.last_updated = dict()
        self.lastUpdatedPath = str()
        self.filtered_tags = []


    # load config
    def load(self, configPath, lastUpdatedPath):
        self.lastUpdatedPath = lastUpdatedPath

        with open(configPath, 'r') as file:
            yaml_result = yaml.load(file, Loader=yaml.FullLoader)
            self.chat_id = yaml_result['tg_chat_id']
            self.tg_bot_token = yaml_result['tg_bot_token']
            self.pixiv_refensh_token = yaml_result['pixiv_refresh_token']
            if yaml_result.get('filtered_tags'):
                self.filtered_tags = yaml_result['filtered_tags']
            else:
                self.filtered_tags = None
            self.admin_id = yaml_result.get('admin_id')
        # load last updated id list
        # if '.last_updated.yaml' not exist, give an empty init
        if os.path.exists(lastUpdatedPath) == False:
            self.last_updated = {
                'private': [], 
                'public': []
            }
        else:
            with open(lastUpdatedPath, 'r') as file:
                self.last_updated = yaml.load(file, Loader=yaml.FullLoader)

    
    def dump(self, type, updatedDump, updateList):
        itemList = list()
        # find the UpdateItem object of the id
        for id in updatedDump:
            item = None
            for j in updateList:
                if j.id == id:
                    item = j
                    break

            tmpDict = dict()
            tmpDict['id'] = item.id
            tmpDict['timestamp'] = item.time

            itemList.append(tmpDict)

        # the lastest id is the last id in the list
        newList = list()
        newList = self.last_updated[type]
        newList.extend(itemList)
        # sort in time order, the last is the latest
        newList.sort(key = lambda x:x['timestamp'])
        # save 40 ids: 10 more for redundancy to avoid image being deleted which could cause duplicate sending
        newList = newList[-40:]
        
        newDict = self.last_updated
        newDict[type] = newList
        dump = yaml.dump(newDict)

        with open(self.lastUpdatedPath, 'w') as file:
            file.write(dump)


c = Config()

c.load(relativePathFix(os.path.join('..', 'config.yaml')), relativePathFix(os.path.join('..', '.last_updated.yaml')))

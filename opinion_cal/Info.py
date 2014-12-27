#-*-coding=utf-8-*-

from utils import _default_mongo
from config import MONGO_DB_NAME, EVENTS_NEWS_COLLECTION_PREFIX

class News(object):
    """新闻类
    """
    def __init__(self, id, topicid):
        self.id = id
        self.topicid = topicid
        self.news_collection = EVENTS_NEWS_COLLECTION_PREFIX + str(topicid)
        self.mongo = _default_mongo(usedb=MONGO_DB_NAME)

    def update_news_subeventid(self, label):
        self.mongo[self.news_collection].update({"_id": self.id}, {"$set": {"subeventid": label}})


#-*-coding=utf-8-*-
"""参数配置文件, 参数会覆盖default_settings.py
"""

MONGOD_PORT = 27019
MONGOD_HOST = '219.224.135.46'

MONGO_DB_NAME = 'news'

EVENTS_COLLECTION = 'news_topic'
SUB_EVENTS_COLLECTION = 'news_subevent'
SUB_EVENTS_FEATURE_COLLECTION = 'news_subevent_feature'
EVENTS_NEWS_COLLECTION_PREFIX = 'post_'
EVENTS_COMMENTS_COLLECTION_PREFIX = 'comment_'
COMMENTS_CLUSTER_COLLECTION = 'comment_cluster'


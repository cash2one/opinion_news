# -*- coding: utf-8 -*-

import os
import time
import math
import uuid
from gensim import corpora
from utils import cut_words, _default_mongo
from config import MONGO_DB_NAME, SUB_EVENTS_COLLECTION, \
        EVENTS_NEWS_COLLECTION_PREFIX, EVENTS_COLLECTION


def process_for_cluto(inputs, cluto_input_folder="cluto"):
    """
    数据预处理函数
    input：
        inputs: 新闻数据, 示例：[{'_id':新闻id,'source_from_name':新闻来源,'title':新闻标题,'content':新闻内容,'timestamp':时间戳}]
    output:
        cluto输入文件路径
    """
    feature_set = set() # 不重复的词集合
    words_list = [] # 所有新闻分词结果集合
    for input in inputs:
        text = input['title'] + input['content']
        words = cut_words(text)
        words_list.append(words)

    # 特征词字典
    dictionary = corpora.Dictionary(words_list)

    # 将feature中的词转换成列表
    feature_set = set(dictionary.keys())

    row_count = len(inputs) # documents count
    column_count = len(feature_set) # feature count
    nonzero_count = 0 # nonzero elements count

    # 文件名以PID命名
    if not os.path.exists(cluto_input_folder):
        os.makedirs(cluto_input_folder)
    file_name = os.path.join(cluto_input_folder, '%s.txt' % os.getpid())

    with open(file_name, 'w') as fw:
        lines = []

        for words in words_list:
            bow = dictionary.doc2bow(words)
            nonzero_count += len(bow)
            line = ' '.join(['%s %s' % (w + 1, c) for w, c in bow]) + '\n'
            lines.append(line)

        fw.write('%s %s %s\n' % (row_count, column_count, nonzero_count))
        fw.writelines(lines)

    return file_name


def cluto_kmeans_vcluster(k=10, input_file=None, vcluster='./cluto-2.1.2/Linux-i686/vcluster', \
        cluto_input_folder="cluto"):
    '''
    cluto kmeans聚类
    input：
        k: 聚簇数，默认取10
        input_file: cluto输入文件路径，如果不指定，以cluto_input_folder + pid.txt方式命名
        vcluster: cluto vcluster可执行文件路径

    output：
        cluto聚类结果, list
    '''
    # 聚类结果文件, result_file
    if not input_file:
        input_file = os.path.join(cluto_input_folder, '%s.txt' % os.getpid())
        result_file = os.path.join(cluto_input_folder, '%s.txt.clustering.%s' % (os.getpid(), k))
    else:
        result_file = '%s.clustering.%s' % (input_file, k)

    command = "%s -niter=20 %s %s" % (vcluster, input_file, k)
    os.popen(command)

    return [line.strip() for line in open(result_file)]


def label2uniqueid(labels):
    '''
        为聚类结果不为其他类的生成唯一的类标号
        input：
            labels: 一批类标号，可重复
        output：
            label2id: 各类标号到全局唯一ID的映射
    '''
    label2id = dict()
    for label in set(labels):
        label2id[label] = str(uuid.uuid4())

    return label2id


def kmeans(items, k=10):
    """kmeans聚类
       input:
           items: [{"title": "新闻标题", "content": "新闻内容"}], 以utf-8编码
       output:
           items: [{"title": "新闻标题", "content": "新闻内容", "label": "簇标签"}]
    """
    input_file = process_for_cluto(items)
    labels = cluto_kmeans_vcluster(k=k, input_file=input_file) # cluto聚类，生成文件，每行为一条记录的簇标签
    label2id = label2uniqueid(labels)

    for idx, item in enumerate(items):
        item['label'] = label2id[labels[idx]]

    return items

def freq_word(items, topk=20):
    '''
    统计一批文本的topk高频词
    input：
        items:
            新闻组成的列表:字典的序列, 数据示例：[{'_id':新闻id,'source_from_name':新闻来源,'title':新闻标题,'content':新闻内容,'timestamp':时间戳,'lable':类别标签},...]
        topk:
            按照词频的前多少个词, 默认取20
    output：
        topk_words: 词、词频组成的列表, 数据示例：[(词，词频)，(词，词频)...]
    '''
    from utils import cut_words
    from collections import Counter
    words_list = []
    for item in items:
        text = item['title'] + item['content']
        words = cut_words(text)
        words_list.extend(words)

    counter = Counter(words_list)
    topk_words = counter.most_common(topk)
    keywords_dict = {k: v for k, v in topk_words}

    return keywords_dict


def cluster_evaluation(items, topk_freq=20, least_freq=10):
    '''
    聚类评价，计算每一类的tf-idf: 计算每一类top词的tfidf，目前top词选取该类下前20个高频词，一个词在一个类中出现次数大于10算作在该类中出现
    input:
        items: 新闻数据, 字典的序列, 输入数据示例：[{'title': 新闻标题, 'content': 新闻内容, 'label': 类别标签}]
        topk_freq: 选取的高频词的前多少
        least_freq: 计算tf-idf时，词在类中出现次数超过least_freq时，才被认为出现
    output:
        各簇的文本, dict
    '''
    def tfidf(keywords_count_list):
        '''计算tfidf
           input
               keywords_count_list: 不同簇的关键词, 词及词频二元组的list
           output
               不同簇的tfidf, list
        '''
        cluster_tf_idf = [] # 各类的tf-idf
        for keywords_dict in keywords_count_list:
            tf_idf_list = [] # 该类下词的tf-idf list
            total_freq = sum(keywords_dict.values()) # 该类所有词的词频总和
            total_document_count = len(keywords_count_list) # 类别总数
            for keyword, count in keywords_dict.iteritems():
                tf = float(count) / float(total_freq) # 每个词的词频 / 该类所有词词频的总和
                document_count = sum([1 if keyword in kd.keys() and kd[keyword] > least_freq else 0 for kd in keywords_count_list])
                idf = math.log(float(total_document_count) / float(document_count + 1))
                tf_idf = tf * idf
                tf_idf_list.append(tf_idf)

            cluster_tf_idf.append(sum(tf_idf_list))

        return cluster_tf_idf

    # 将文本按照其类标签进行归类
    items_dict = {}
    for item in items:
        try:
            items_dict[item['label']].append(item)
        except:
            items_dict[item['label']] = [item]

    # 对每类文本提取topk_freq高频词
    labels_list = []
    keywords_count_list = []
    for label, one_items in items_dict.iteritems():
        labels_list.append(label)
        keywords_count = freq_word(one_items)
        keywords_count_list.append(keywords_count)

    # 计算每类的tfidf
    tfidf_list = tfidf(keywords_count_list)
    tfidf_dict = dict(zip(labels_list, tfidf_list))
    keywords_dict = dict(zip(labels_list, keywords_count_list))

    def choose_by_tfidf(top_num=5, last_num=2):
        """ 根据tfidf对簇进行选择
            input:
                top_num: 保留top_num的tfidf类
                last_num: 去除last_num的tfidf类
            output:

        """
        cluster_num = len(tfidf_list)
        if cluster_num < top_num + last_num:
            raise ValueError("cluster number need to be larger than top_num + last_num")

        sorted_tfidf = sorted(tfidf_dict.iteritems(), key=lambda(k, v): v, reverse=True)
        delete_labels = [l[0] for l in sorted_tfidf[-last_num:]]
        middle_labels = [l[0] for l in sorted_tfidf[top_num:-last_num]]

        other_items = []
        for label in items_dict.keys():
            items = items_dict[label]
            if label in delete_labels:
                for item in items:
                    item['label'] = 'other'
                    other_items.append(item)

                items_dict.pop(label)

            if label in middle_labels:
                top_words_set = set(keywords_dict[label].keys())
                after_items = []
                for item in items:
                    hit = False
                    text = item['title'] + item['content']
                    for w in top_words_set:
                        if w in text:
                            hit = True
                            break

                    if not hit:
                        item['label'] = 'other'
                        other_items.append(item)
                    else:
                        after_items.append(item)

                if len(after_items) == 0:
                    items_dict.pop(label)
                else:
                    items_dict[label] = after_items

        try:
            items_dict['other'].extend(other_items)
        except KeyError:
            items_dict['other'] = other_items

    # 根据簇的tfidf评价选择
    choose_by_tfidf()

    def choose_by_size(least_size=5):
        """小于least_size的簇被归为其他簇
        """
        other_items = []
        for label in items_dict.keys():
            items = items_dict[label]
            if len(items) < least_size:
                for item in items:
                    item['label'] = 'other'
                    other_items.append(item)

                items_dict.pop(label)

        try:
            items_dict['other'].extend(other_items)
        except KeyError:
            items_dict['other'] = other_items

    # 根据簇的大小进行评价选择
    choose_by_size()

    return items_dict


if __name__=="__main__":
    topic = "APEC2014"
    topicid = "54916b0d955230e752f2a94e"
    mongo = _default_mongo(usedb=MONGO_DB_NAME)
    results = mongo[EVENTS_NEWS_COLLECTION_PREFIX + topicid].find()
    inputs = [{"title": r["title"].encode("utf-8"), "content": r["content168"].encode("utf-8")} for r in results]

    # kmeans 聚类
    results = kmeans(inputs)

    # cluster evaluation
    results = cluster_evaluation(results)
    for k, v in results.iteritems():
        print k, len(v)

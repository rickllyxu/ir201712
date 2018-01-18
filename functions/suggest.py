# -*- coding:utf-8 -*-
"""
@author: xuesu

"""

import itertools
import json

import config
import indexes
import filters
import utils.decorator
import utils.utils
import datasources
import update.similar_text
import update.segment

@utils.decorator.timer
def suggest_autocomplete(word_regex_list, num=None):
    if num is None:
        num = config.functions_config.autocomplete_default_number
    candidate_texts = indexes.IndexHolder().word_text_index.collect(word_regex_list[-1])
    candidate_texts = filters.filter_by_avgtfidf(candidate_texts, num)
    return candidate_texts


@utils.decorator.timer
def suggest_similar_search(word_regex_list, num=None):
    if num is None:
        num = config.functions_config.similar_search_default_number
    word_wildcard_list = [word_regex for word_regex in word_regex_list if '*' in word_regex]
    word_texts = [word_regex for word_regex in word_regex_list if '*' not in word_regex]
    if word_wildcard_list:
        wildcard_groups = list()
        for word_text in word_wildcard_list:
            candidates = indexes.IndexHolder().word_text_index. \
                collect(word_text, action=indexes.IndexHolder().word_text_index.CollectionAction.SIMILAR)
            candidates = filters.filter_by_avgtfidf(candidates, config.functions_config.similar_search_candidate_number)
            if candidates:
                wildcard_groups.append(candidates)
        if wildcard_groups:
            wildcard_candidates_groups = [list(x) for x in itertools.product(*wildcard_groups)]
            for i in range(len(wildcard_candidates_groups)):
                wildcard_candidates_groups[i] += word_texts
            return filters.filter_by_coocurrence(wildcard_candidates_groups, num)
    candidates_groups = list()
    for i, word_text in enumerate(word_texts):
        other_words = word_texts[:i] + word_texts[i + 1:]
        candidates = indexes.IndexHolder().word_text_index. \
            collect(word_text, action=indexes.IndexHolder().word_text_index.CollectionAction.SIMILAR)
        candidates = filters.filter_by_avgtfidf(candidates, config.functions_config.similar_search_candidate_number)
        for candidate in candidates:
            if candidate == word_text:
                continue
            candidates_groups.append([candidate] + other_words)
    return filters.filter_by_coocurrence(candidates_groups, num)


@utils.decorator.timer
def suggest_similar_news(session, _id):
    redis_op = datasources.get_redis().redis_op()
    test_news = datasources.get_db().find_news_abstract_and_content_by_id(session, _id)
    test_data = []
    if test_news.abstract is None:
        for w, pos, start, end in update.segment.tokenize(test_news.content):
            if pos.startswith('n'):
                test_data.append(w)

    if redis_op.exists('similar_news_from_hot_news'):
            return suggest_similar_news_predict(redis_op, test_news.abstract or test_data, True if test_news is None else False)

    p = redis_op.lrange('hot_news_list', 0, -1)
    p = [u.replace('\'', '"').replace('None', 'null') for u in p]

    p = [json.loads(u) for u in p]

    raw_corpora = [u['abstract'] for u in p]
    update.similar_text.corpora_process(raw_corpora)

    redis_op.set('similar_news_from_hot_news', 1)
    return suggest_similar_news_predict(redis_op, test_news.abstract or test_data, True if test_news is None else False)


@utils.decorator.timer
def suggest_similar_news_predict(redis_op, news_abstract, cutted):
    r = update.similar_text.similarity_id(news_abstract, cutted)

    if len(r) == 0:
        return [{'id': None, 'title': '没有相似新闻可推荐'}]
    if r[0][1] == 1.0:
        r = r[1:]
    try:
        p = list()
        p += [redis_op.lrange('hot_news_list', u[0], u[0]) for u in r]
        p = [u[0].replace('\'', '"').replace('None', 'null') for u in p]
        p = [json.loads(u) for u in p]
        ans = [{'id': u['id'], 'title': u['title']} for u in p]
        return ans
    except Exception as e:
        return [{'id': None, 'title': '没有相似新闻可推荐'}]


@utils.decorator.timer
def suggest_hot_news(session, page):
    """
    check that documents in redis(cache) is not expired 
    :param session: 
    :return: 
    """
    # check first.
    # if expired, we should construct 1000 hot news again
    redis_op = datasources.get_redis().redis_op()
    EXPIRED = not redis_op.exists('hot_news_list')
    print('Expired:', EXPIRED)
    if EXPIRED:
        r = datasources.get_db().find_hot_news(session, 1000)

        cache = [{'title': news.title.replace('"', '“').replace('\'', '“').replace('\n', ' ').replace('\xa0', ' '),
                  'abstract': news.abstract.replace('"', '“').replace('\'', '“').replace('\n', ' ').replace('\xa0', ' '),
                  'time': str(news.time),
                  'keywords': news.keywords.replace('"', '“').replace('\'', '“').replace('\n', ' ').replace('\xa0', ' '),
                  'id': news.id} for news in r]
        # we should cache the variable cache into redis.
        # print(cache)
        redis_op.lpush('hot_news_list', *cache)
        redis_op.expire('hot_news_list', config.cache_config.expire)
        redis_op.delete('similar_news_from_hot_news')
        if len(r) > 10:
            candidate = cache[:10]
        else:
            candidate = cache
        return candidate
    else:  # to read redis.
        llen = redis_op.llen('host_news_list')
        if (page - 1) * 10 > llen:
            candidate = []
        elif page * 10 > llen:
            candidate = redis_op.lrange('hot_news_list', (page - 1) * 10, -1)
        else:
            candidate = redis_op.lrange('hot_news_list', (page - 1) * 10, page * 10)
        candidate = [u.replace('\'', '"').replace('None', 'null') for u in candidate]
        candidate = [json.loads(u) for u in candidate]
        return candidate

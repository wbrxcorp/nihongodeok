#!/usr/bin/python
from __future__ import print_function
import sys
import urllib
import urllib2
import json
import nihongodeok

def run(article_id):
    return nihongodeok.create_and_push_bag_of_words(article_id, True)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        articles = sys.argv[1:]
    else:
        articles = map(lambda x:x["id"], nihongodeok.async_get(nihongodeok.api_base + "/latest_articles/ja").decode_json())
    
    for article_id in articles:
        print(run(article_id))


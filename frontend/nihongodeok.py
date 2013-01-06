import os
import json
import urllib
import urllib2
import nltk
import asynchttp

api_base="http://api.nihongodeok.com/trunk"
hiwihhi_api_base="http://api.hiwihhi.com/trunk"
pagecapture_base="http://pagecapture.local"
pagecapture_external_base="http://pagecapture.nihongodeok.com"
pagecapture_request="/cgi-bin/capture_request.py"

yahoo_application_id="dj0zaiZpPVBpYUdyb0Nzd1JDYSZkPVlXazlOMUEwUVhwWE5UWW1jR285TUEtLSZzPWNvbnN1bWVyc2VjcmV0Jng9MzE-"
yahoo_secret="25106cf532f5193bf0eb8f775166a0d4f899b457"

__CONFIG_FILE = os.path.dirname(os.path.abspath( __file__ )) + "/nihongodeok.conf"

if os.path.exists(__CONFIG_FILE):
    with open(__CONFIG_FILE, "r") as f:
        config = json.load(f)
    for item in config:
        globals()[item] = config[item]

class AsyncCallToken:
    def __init__(self, response, content):
        self.response = response
        self.content = content

    def decode_json(self):
        return json.loads(str(self.content))

    def parse_html(self):
        return BeautifulSoup.BeautifulSoup(str(self.content))

def encoded_dict(in_dict):
    out_dict = {}
    for k, v in in_dict.iteritems():
        if isinstance(v, unicode):
            v = v.encode('utf8')
        elif isinstance(v, str):
            # Must be encoded in UTF-8
            v.decode('utf8')
        out_dict[k] = v
    return out_dict

def async_get(url, params = None):
    http = asynchttp.Http()
    if params != None and len(params) > 0:
        url += "?" + urllib.urlencode(encoded_dict(params))
    response, content = http.request(url)
    return AsyncCallToken(response, content)

def async_post(url, params):
    http = asynchttp.Http()
    response, content = http.request(url, "POST", urllib.urlencode(encoded_dict(params)), headers = {'Content-type': 'application/x-www-form-urlencoded'})
    return AsyncCallToken(response, content)

def async_head(url, params = None):
    http = asynchttp.Http()
    if params != None and len(params) > 0:
        url += "?" + urllib.urlencode(encoded_dict(params))
    response, content = http.request(url, "HEAD")
    return AsyncCallToken(response, content)

def get_article(article_id):
    return json.load(urllib2.urlopen(api_base + "/get_article/%s" % article_id))

def async_get_article(article_id):
    return async_get(api_base + "/get_article/%s" % article_id)

def async_get_related_articles(article_id):
    return async_get(api_base + "/related_articles/%s" % article_id)

def extract_keyphrase(text):
    params = {"appid":yahoo_application_id,"sentence":text.encode("utf-8"),"output":"json"}
    req = urllib2.Request("http://jlp.yahooapis.jp/KeyphraseService/V1/extract", urllib.urlencode(params))
    return json.load(urllib2.urlopen(req))

def push_bag_of_words(article_id, words_en, words_ja = None):
    if words_en == None and words_ja == None:
        return False

    params = {}
    if words_en != None: params["words_en"] = words_en.encode("utf-8")
    if words_ja != None: params["words_ja"] = words_ja.encode("utf-8")
    req = urllib2.Request(api_base + "/bag_of_words/%s" % article_id, urllib.urlencode(params))
    return json.load(urllib2.urlopen(req))[0]

def create_bag_of_words(article):
    subject_en = article["subject_en"]
    body_en = article["body_en"]
    subject_ja = article["subject_ja"]
    body_ja = article["body_ja"]

    words_en = None
    words_ja = None

    english_stopwords = nltk.corpus.stopwords.words("english")

    if (subject_en != None and subject_en != "") or (body_en != None and body_en != ""):
        words_en = " ".join(set(map(lambda x:x.lower(), filter(lambda x:x not in english_stopwords, nltk.word_tokenize(subject_en + '\n' + body_en)))))
    if (subject_ja != None and subject_ja != "") or (body_ja != None and body_ja != ""):
        words_ja = " ".join(extract_keyphrase(subject_ja + '\n' + body_ja).keys())
    return words_en, words_ja

def create_and_push_bag_of_words(article_id, print_result = False):
    article = get_article(article_id)

    words_en, words_ja = create_bag_of_words(article)

    if print_result:
        print words_en
        print words_ja

    return push_bag_of_words(article_id, words_en, words_ja)

def request_page_capture(url):
    async_post(pagecapture_base + pagecapture_request, {"url":url})

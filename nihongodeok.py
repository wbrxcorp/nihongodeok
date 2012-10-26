import socket
import os
import re
import json
import email.utils
import datetime
import urllib2

api_base = "http://search.local/"
http_proxy = "http://search.local:3128"

__CONFIG_FILE = os.path.dirname(os.path.abspath( __file__ )) + "/nihongodeok.conf"

if os.path.exists(__CONFIG_FILE):
    with open(__CONFIG_FILE, "r") as f:
        config = json.load(f)
    for item in config:
        globals()[item] = config[item]

if http_proxy != None:
    os.environ["http_proxy"] = http_proxy

def rfc822_to_date(date_str):
    parsed_date = email.utils.parsedate_tz(date_str)
    return datetime.date(parsed_date[0],parsed_date[1],parsed_date[2])

def date_to_str(date):
    return "%04d-%02d-%02d" % (date.year, date.month, date.day) if date != None else None

def normalize(str_to_be_normalized):
    return re.sub("\n{3,}", "\n\n", str_to_be_normalized.strip())

class Article:
    def __init__(self, url):
        if url == None or not(url.startswith("http://") or url.startswith("http://")):
            raise Exception("URL not specified or malformed URL.")
        self.url = url
        self.canonical = False
    def _get_canonical_url(self):
        # call api here
        # warn if canonical url is different from original
        self.canonical = True
        self.already_exist = False
    def is_already_exist(self):
        if not self.canonical: self._get_canonical_url()
        return self.already_exist
    def open(self):
        if not self.canonical: self._get_canonical_url()
        return urllib2.urlopen(self.url)

    def _check_error(self):
        if not hasattr(self, "subject") or self.subject == None:
            raise Exception("Subject(subject) is not specified.")
        if not hasattr(self, "body") or self.body == None:
            raise Exception("Article body(body) is not set.")
        if not hasattr(self, "language") or self.language == None:
            raise Exception("Language(language) is not specified.")
        if self.language not in ("en","ja"):
            raise Exception("Unsupported language(%s)." % self.language)
        if not hasattr(self, "scraped_by") or self.scraped_by == None:
            raise Exception("Scraper's name(scraped_by) is not specified.")
        if not hasattr(self, "site_id") or self.site_id == None:
            raise Exception("Website Identifier(site_id) is not specified.")
        if not hasattr(self, "article_date"):
            raise Exception("Article date(article_date) is not set.")
        elif self.article_date == None:
            print "Warning: Article date(article_date) is being left blank."
        elif not isinstance(self.article_date, datetime.date):
            raise Exception("Article date(article_date) must be datetime.date object.")

    def dump(self):
        self._check_error()
        print "Subject: %s" % normalize(self.subject)
        print "Date: %s" % date_to_str(self.article_date)
        print "Site: %s" % self.site_id
        print normalize(self.body)

    def push(self):
        self._check_error()
        print "pushing to database..."
        str_article_date = date_to_str(self.article_date)
        request_body = json.dumps({"url":self.url, "language":self.language, 
                "subject":normalize(self.subject), "body":normalize(self.body), "scraped_by":self.scraped_by,
                "site_id":self.site_id, "article_date":str_article_date})
        # call api here
        print "pushed. url=%s" % self.url

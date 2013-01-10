import socket
import os
import re
import json
import email.utils
import datetime
import urllib2
from BeautifulSoup import BeautifulSoup

api_base = "http://api.nihongodeok.com/0.1/"

VERSION="0.1.7"

__CONFIG_FILE = os.path.dirname(os.path.abspath( __file__ )) + "/nihongodeok.conf"

MONTHS = { "jan":1, "feb":2, "mar":3, "apr":4, "may":5, "jun":6, "jul":7, "aug":8, "sep":9, "oct":10, "nov":11, "dec":12 }

if os.path.exists(__CONFIG_FILE):
    with open(__CONFIG_FILE, "r") as f:
        config = json.load(f)
    for item in config:
        globals()[item] = config[item]

def rfc822_to_date(date_str):
    parsed_date = email.utils.parsedate_tz(date_str)
    return datetime.date(parsed_date[0],parsed_date[1],parsed_date[2])

def date_to_str(date):
    if isinstance(date, basestring):
        if re.match("^[12][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]$", date): return date
        if re.search("[0-3]?[0-9] +[A-Za-z][A-Za-z][A-Za-z] +[12][0-9][0-9][0-9] +[012][0-9]:[0-5][0-9]:[0-5][0-9]", date):
            # assume as rfc822
            date = rfc822_to_date(date)
        else:
            match = re.search("[0-3]?[0-9] +[A-Za-z][A-Za-z][A-Za-z] +[12][0-9][0-9][0-9]", date)
            if match != None:
                splitted_date = match.group().split()
                date = datetime.date(int(splitted_date[2]), MONTHS[splitted_date[1].lower()], int(splitted_date[0]))

    if not isinstance(date, datetime.date):
        raise Exception("Weird date string: %s" % date)

    return "%04d-%02d-%02d" % (date.year, date.month, date.day) if date != None else None

def normalize(str_to_be_normalized):
    return re.sub("\n{3,}", "\n\n", str_to_be_normalized.strip())

def cacheable_urlopen(url):
    return urllib2.urlopen(api_base + "/cacheable_fetch?url=%s" % urllib2.quote(url))

class Article:
    def __init__(self, url):
        if url == None or not(url.startswith("http://") or url.startswith("http://")):
            raise Exception("URL not specified or malformed URL.")
        self.url = url
        self.canonical = False
    def _get_canonical_url(self):
        result = json.load(urllib2.urlopen(api_base + "/get_article?url=%s" % urllib2.quote(self.url)))
        # warn if canonical url is different from original
        canonical_url = result[0]
        result = result[1]
        if self.url != canonical_url:
            print "Canonical URL(%s) is different from given URL(%s)!" % (canonical_url, self.url)
            self.url = canonical_url
        self.canonical = True
        #print result
        self.already_exist = (result is not None)

    def is_already_exist(self):
        if not self.canonical: self._get_canonical_url()
        return self.already_exist
    def open(self):
        if not self.canonical: self._get_canonical_url()
        return cacheable_urlopen(self.url)
    def parse(self):
        return BeautifulSoup(self.open().read(),convertEntities=BeautifulSoup.HTML_ENTITIES)

    def _check_error(self):
        if not hasattr(self, "subject") or self.subject == None:
            raise Exception("Subject(subject) is not specified.")
        if not isinstance(self.subject, basestring):
            raise Exception("Subject(subject) must not be other than string type. given type=%s" % type(self.subject))
        if normalize(self.subject) == "":
            raise Exception("Subject(subject) is empty. url=%s" % self.url)
        if not hasattr(self, "body") or self.body == None:
            raise Exception("Article body(body) is not set.")
        if not isinstance(self.body, basestring):
             raise Exception("Article body(body) must not be other than string type. given type=%s" % type(self.body))
        if normalize(self.body) == "":
            raise Exception("Article body(body) is empty. url=%s" % self.url)
        if not hasattr(self, "language") or self.language == None:
            raise Exception("Language(language) is not specified.")
        if self.language not in ("en","ja"):
            raise Exception("Unsupported language(%s)." % self.language)
        if not hasattr(self, "scraped_by") or self.scraped_by == None:
            raise Exception("Scraper's name(scraped_by) is not specified.")
        if not hasattr(self, "site_id") or self.site_id == None:
            raise Exception("Website Identifier(site_id) is not specified.")
        if not hasattr(self, "date"):
            raise Exception("Article date(date) is not set.")
        elif self.date == None:
            print "Warning: Article date(date) is being left blank."

    def dump(self):
        self._check_error()
        print "URL: %s" % self.url
        print "Subject: %s" % normalize(self.subject)
        print "Date: %s" % date_to_str(self.date)
        print "Site: %s" % self.site_id
        print normalize(self.body)

    def push(self):
        self._check_error()
        print "pushing to database..."
        str_date = date_to_str(self.date)
        request_body = json.dumps({"url":self.url, "language":self.language, 
                "subject":normalize(self.subject), "body":normalize(self.body), "scraped_by":self.scraped_by,
                "site_id":self.site_id, "date":date_to_str(self.date)})
        req = urllib2.Request(api_base + "/push_article", data=request_body, headers={'Content-type': 'application/json'})
        return json.load(urllib2.urlopen(req))

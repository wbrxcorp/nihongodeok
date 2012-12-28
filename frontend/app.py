#!/usr/bin/python
# -*- coding:utf-8 -*-
import os
import sys
import cgi
import datetime
import flask
import werkzeug.urls
import json
import urllib
import urllib2
import re
from BeautifulSoup import BeautifulSoup,Comment
import asynchttp
import default_config

app = flask.Flask(__name__)
app.config.from_object(default_config.object)
app_dir = os.path.dirname(os.path.abspath( __file__ ))
config_file = app_dir + "/nihongodeok.conf"
if os.path.exists(config_file): app.config.from_pyfile(config_file)
API = app.config["API"]
HIWIHHI_API = app.config["HIWIHHI_API"]

def load(path):
    return json.load(urllib2.urlopen(API + path))

def load_hiwihhi(path):
    return json.load(urllib2.urlopen(HIWIHHI_API + path))

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

def load_keywords():
    hottrends = async_get(HIWIHHI_API + "/hottrends")
    keywords = async_get(HIWIHHI_API + "/keywords/splitted?offset=1")

    hottrends = hottrends.decode_json()
    keywords = keywords.decode_json()

    kwd = {}
    for hottrend in hottrends:
        hashcode = hottrend[1]
        if hashcode not in kwd:
            kwd[hashcode] = async_get(API + "/search", { "q":hottrend[0],"limit":0 })
    for keyword in keywords:
        hashcode = keyword[1]
        if hashcode not in kwd:
            kwd[hashcode] = async_get(API + "/search", { "q":keyword[0],"limit":0 })

    for hashcode in kwd:
        kwd[hashcode] = kwd[hashcode].decode_json()[0]

    for hottrend in hottrends:
        hashcode = hottrend[1]
        if hashcode in kwd: hottrend.append(kwd[hashcode])
        
    for keyword in keywords:
        hashcode = keyword[1]
        if hashcode in kwd: keyword.append(kwd[hashcode])

    return (hottrends, keywords)

@app.route('/')
def index():
    articles = load("/latest_articles/ja")
    hottrends, keywords = load_keywords()

    return flask.render_template("index.html",articles=articles,hottrends=hottrends,keywords=keywords)

@app.route("/tools/scrape")
def _scrape():
    script = """def scrape(soup):
    def element_text(element):
        return ''.join(element.findAll(text=True))
    def join_all_paragraphs(paragraphs):
        return "\\n\\n".join(map(lambda x:element_text(x).strip(), paragraphs))

    subject = element_text(soup.findAll('h1')[0])

    paragraphs = []
    paragraphs += soup.findAll('p')
    if len(paragraphs) == 0: return None

    body = join_all_paragraphs(paragraphs)

    date = None

    return (subject, body, date)"""
    return flask.render_template("scrape.html",script=script)

def remove_comments(soup):
    for comment in soup.findAll(text=lambda text:isinstance(text, Comment)):
        print comment
        comment.extract()    

@app.route("/tools/scrape", methods=['POST'])
def _scrape_post():
    url = flask.request.form["url"]
    script = flask.request.form["script"]
    try:
        result = load("/get_article?url=%s" % urllib2.quote(url))
        canonical_url = result[0]

        exec(script)
        soup = BeautifulSoup(urllib2.urlopen(API + "/cacheable_fetch?url=" + urllib2.quote(canonical_url)).read(),convertEntities=BeautifulSoup.HTML_ENTITIES)
        remove_comments(soup)
        result = scrape(soup)
        if result == None:
            return flask.jsonify(html="<h3>Article skipped</h3>Scraper returned None\n")
        subject,body,article_date = result

        html = "" if canonical_url == url else "Canonical URL: <a href='%s' target='_blank'>%s</a>" % (canonical_url, canonical_url)
        html += "<h3><a href='%s' target='_blank'>%s</a></h3>\n%s" % (canonical_url, subject, re.sub("\n", "<br/>", cgi.escape(body)))
        return flask.jsonify(html=html,canonical_url=canonical_url)
    except Exception, e:
        #exc_type, exc_obj, exc_tb = sys.exc_info()
        return flask.jsonify(html="<h3>Error</h3>\n%s" % (e))

@app.route("/tools/latest_articles")
def latest_articles():
    request = "/latest_articles"

    conditions = []
    if "scraped_by" in flask.request.args:
        conditions.append("scraped_by=%s" % urllib2.quote(flask.request.args["scraped_by"]))
    if "site_id" in flask.request.args:
        conditions.append("site_id=%s" % urllib2.quote(flask.request.args["site_id"]))

    if len(conditions) > 0:
        request += '?'
        request += '&'.join(conditions)

    l = load("/list")
    articles = load(request)
    return flask.render_template("latest_articles.html", articles=articles, scrapers=l["scrapers"], sites=l["sites"])

@app.route("/tools/show_article/<article_id>.html")
def show_article(article_id):
    try:
        article = load("/get_article/%s" % article_id)
    except urllib2.HTTPError, e:
        return "HTTP Error %d during communicating with API" % (e.code), e.code

    return flask.render_template("show_article.html", article=article)

@app.route("/tools/delete_article", methods=['POST'])
def delete_article():
    article_id = flask.request.form["article_id"]
    name = flask.request.form["name"]

    article = load("/get_article/%s" % article_id)
    if article["scraped_by"] != name:
        return "Name doesn't match"

    req = urllib2.Request(API + "/delete_article", urllib.urlencode({"article_id":article_id}))
    result = json.load(urllib2.urlopen(req))
    return "deleted. <a href='./latest_articles'>Back to list</a>"

@app.route("/tools/statistics")
def statistics():
    statistics = load("/statistics")
    return flask.render_template("statistics.html", statistics=statistics)

@app.route("/tools/translate/")
def to_be_translated():
    articles = load("/articles_to_be_translated")
    return flask.render_template("to_be_translated.html", articles = articles)

@app.route("/tools/translate/<article_id>", methods=['GET'])
def translate_get(article_id, message = None):
    try:
        article = load("/get_article/%s" % article_id)
    except urllib2.HTTPError, e:
        return "HTTP Error %d during communicating with API" % (e.code), e.code

    return flask.render_template("translate.html", article=article, message=message)

@app.route("/tools/translate/<article_id>", methods=['POST'])
def translate_post(article_id):
    subject = flask.request.form["subject"].encode("utf-8")
    body = flask.request.form["body"].encode("utf-8")
    params = {"article_id":article_id, "language":"ja", "subject":subject, "body":body}
    req = urllib2.Request(API + "/translate_article", urllib.urlencode(params))
    result = json.load(urllib2.urlopen(req))
    
    return translate_get(article_id)

@app.route("/tools/edit_article/<language>", methods=['GET'])
def edit_article(language):
    return flask.render_template("edit_article.html")

@app.route("/tools/edit_article/<language>", methods=['POST'])
def edit_article_post(language):
    url = flask.request.form["url"]
    subject = flask.request.form["subject"]
    body = flask.request.form["body"]
    scraped_by = flask.request.form["scraped_by"]
    site_id = flask.request.form["site_id"]
    date = flask.request.form["date"]
    request_body = json.dumps({"url":url, "language":language, 
                               "subject":subject, "body":body, 
                               "scraped_by":scraped_by,
                               "site_id":site_id, "date":date})
    req = urllib2.Request(API + "/push_article", data=request_body, headers={'Content-type': 'application/json'})
    result = json.load(urllib2.urlopen(req))
    if result[1] == None: return "Failed"
    #else
    return flask.redirect("/tools/edit_article/%s/%s" % (result[1], language))    

@app.route("/tools/synonyms/missing")
def missing_synonyms():
    sold_keywords = async_get(HIWIHHI_API + "/keywords")
    synonyms = async_get(API + "/synonyms")
    sold_keywords = sold_keywords.decode_json()
    synonyms = synonyms.decode_json()

    keywords = set()
    for sold_keyword in sold_keywords:
        kws = re.split(u"[ 　]", sold_keyword[0])
        for kw in kws:
            if kw != "": keywords.add(kw)

    missings = []
    for keyword in keywords:
        if keyword not in synonyms: missings.append(keyword)

    return flask.render_template("missing_synonyms.html", keywords=missings)

@app.route("/tools/synonyms/edit", methods=['GET'])
def edit_synonym():
    keyword = flask.request.args["keyword"]
    synonyms = async_get(API + "/synonyms", {"q":keyword} )
    synonyms = synonyms.decode_json()
    data = {"keyword":keyword}
    if keyword in synonyms:
        data["synonyms"] = synonyms[keyword]
        data["count"] = async_get(API + "/search", {"q":data["synonyms"], "limit":0}).decode_json()[0]
    else:
        data["count"] = async_get(API + "/search", {"q":keyword, "limit":0}).decode_json()[0]

    return flask.render_template("edit_synonyms.html", **data)

@app.route("/tools/synonyms/edit", methods=['POST'])
def post_edit_synonym():
    keyword = flask.request.form["keyword"]
    synonyms = flask.request.form["synonyms"]
    result = async_post(API + "/synonym", {"keyword":keyword,"synonyms":synonyms}).decode_json()
    return flask.redirect("/tools/synonyms/edit?keyword=%s" % urllib2.quote(keyword.encode("utf-8")) )

@app.route("/ts/<script_name>.js")
def ts(script_name):
    tsfile = "%s/ts/%s.ts" % (app_dir, script_name)
    jsfile = "%s/ts/%s.js" % (app_dir, script_name)

    if not os.path.exists(tsfile):
        return "Not found", 404

    need_compile = False
    if not os.path.exists(jsfile): need_compile = True
    else:
        stat_jsfile = os.stat(jsfile)
        if stat_jsfile.st_size == 0 or os.stat(tsfile).st_mtime > stat_jsfile.st_mtime: 
            need_compile = True

    if need_compile:
        if os.system("tsc --out %s %s" % (jsfile, tsfile)) != 0:
            return "alert('TypeScript compilation error');"

    return flask.send_file("%s/ts/%s.js" % (app_dir, script_name), "text/javascript")

def complement_search_result(result):
    article = result["article"]
    snippets = result["snippets"]
    subject = cgi.escape(article["subject_en"])
    if len(snippets["subject_en"]) > 0:
        subject = snippets["subject_en"][0]
    subject_ja = article["subject_ja"]
    if subject_ja != None and subject_ja != "":
        subject = cgi.escape(subject_ja)
    if len(snippets["subject_ja"]) > 0:
        subject = snippets["subject_ja"][0]        
    result["subject"] = subject

    body = article["body_en"]
    body_ja = article["body_ja"]
    if body_ja != None and body_ja != "":
        body = body_ja
    result["body"] = body

    new_snippets = []
    new_snippets += snippets["body_ja"]
    new_snippets += snippets["body_en"]
    new_snippets = new_snippets[:3]

    result["snippets"] = new_snippets if len(new_snippets) > 0 else None

@app.route("/search")
def search():
    if "q" not in flask.request.args:
        return flask.render_template("search.html")
    q = flask.request.args["q"]
    page = int(flask.request.args["page"]) if "page" in flask.request.args else 1
    search_uri = "/search?q=%s&offset=%d&limit=10" % (urllib2.quote(q.encode("utf-8")), (page - 1) * 10)
    data = {"page":page}
    if q != "":
        results = load(search_uri)
        data["count"] = results[0]
        data["results"] = results[1]
        for result in results[1]: complement_search_result(result)

    data["keyword"] = q
    return flask.render_template("search_result.html", **data)

@app.route('/k/<hashcode>.html')
def keyword(hashcode):
    hottrends, keywords = load_keywords()
    keyword = load_hiwihhi("/keyword/%s" % hashcode)
    search_uri = "/search?q=%s&limit=20" % (urllib2.quote(keyword[0].encode("utf-8")))

    results = load(search_uri)[1]
    for result in results: complement_search_result(result)

    data = { "results":results, "keyword":keyword[0],"links":keyword[1],"hottrends":hottrends,"keywords":keywords }
    return flask.render_template("keyword.html", **data)

@app.route("/site/<site_id>/")
def site(site_id):
    hottrends, keywords = load_keywords()
    articles = load("/latest_articles/ja?site_id=%s" % urllib2.quote(site_id.encode("utf-8")))
    return flask.render_template("site.html", site_id=site_id,articles=articles,hottrends=hottrends,keywords=keywords)

@app.template_filter("urlencode")
def urlencode(text):
    return werkzeug.urls.url_quote(text)

@app.template_filter("unixtime2exacttime")
def unixtime2exacttime(t):
    now = datetime.datetime.fromtimestamp(t / 1000)
    return now.strftime(u"%Y-%m-%d %H:%M")

@app.template_filter("articletext")
def articletext(text):
    return re.sub("\n", "<br/>", cgi.escape(text))

@app.template_filter("articlehead")
def articlehead(text):
    shortened = len(text) > 200
    text = text[:200]
    if shortened: text += "..."
    return text

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True)


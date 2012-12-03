#!/usr/bin/python
# -*- coding:utf-8 -*-
import os
import sys
import cgi
import flask
import json
import urllib
import urllib2
import MeCab
import re
from BeautifulSoup import BeautifulSoup,Comment
import default_config

app = flask.Flask(__name__)
app.config.from_object(default_config.object)
app_dir = os.path.dirname(os.path.abspath( __file__ ))
config_file = app_dir + "/nihongodeok.conf"
if os.path.exists(config_file): app.config.from_pyfile(config_file)
API = app.config["API"]
NEW_API = app.config["NEW_API"]

def load(path):
    return json.load(urllib2.urlopen(API + path))

@app.route('/')
def index():
    articles = load("/latest_articles/ja")
    return flask.render_template("index.html",articles=articles)

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
        result = result[1]
        canonical_url = result["canonical_url"]

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

    if "body_en" in article:
        article["encoded_body_en"] = re.sub("\n", "<br/>", cgi.escape(article["body_en"]))
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

    if "body_en" in article:
        article["encoded_body_en"] = re.sub("\n", "<br/>", cgi.escape(article["body_en"]))
    return flask.render_template("translate.html", article=article, message=message)

@app.route("/tools/translate/<article_id>", methods=['POST'])
def translate_post(article_id):
    subject = flask.request.form["subject"].encode("utf-8")
    body = flask.request.form["body"].encode("utf-8")
    params = {"article_id":article_id, "language":"ja", "subject":subject, "body":body}
    req = urllib2.Request(API + "/translate_article", urllib.urlencode(params))
    result = json.load(urllib2.urlopen(req))
    
    return translate_get(article_id)

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

@app.route("/search")
def search():
    return "Not implemented yet"

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True)


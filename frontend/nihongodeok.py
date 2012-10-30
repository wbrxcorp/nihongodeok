#!/usr/bin/python
# -*- coding:utf-8 -*-
import os
import sys
import cgi
import flask
import json
import urllib2
import MeCab
import re
from BeautifulSoup import BeautifulSoup
import default_config

app = flask.Flask(__name__)
app.config.from_object(default_config.object)
config_file = os.path.dirname(os.path.abspath( __file__ )) + "/nihongodeok.conf"
if os.path.exists(config_file): app.config.from_pyfile(config_file)
API = app.config["API"]

def load(path):
    return json.load(urllib2.urlopen(API + path))

@app.route('/')
def index():
    return flask.render_template("index.html")

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

@app.route("/tools/scrape", methods=['POST'])
def _scrape_post():
    url = flask.request.form["url"]
    script = flask.request.form["script"]
    try:
        result = load("/get_article?url=%s" % urllib2.quote(url))
        result = result[1]
        canonical_url = result["canonical_url"]

        exec(script)
        soup = BeautifulSoup(urllib2.urlopen(canonical_url).read(),convertEntities=BeautifulSoup.HTML_ENTITIES)
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
    article = load("/get_article/%s" % article_id)
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

    req = urllib2.Request(API + "/push_article", data="article_id=%s" % article_id)
    result = json.load(urllib2.urlopen(req))
    return "deleted. <a href='./latest_articles'>Back to list</a>"

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True)


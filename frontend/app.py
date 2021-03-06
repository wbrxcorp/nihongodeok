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
import nihongodeok
import default_config

app = flask.Flask(__name__)
app.secret_key = nihongodeok.facebook_app_secret

def load(path):
    return json.load(urllib2.urlopen(nihongodeok.api_base + path))

def load_hiwihhi(path):
    return json.load(urllib2.urlopen(nihongodeok.hiwihhi_api_base + path))

def load_keywords():
    hottrends = nihongodeok.async_get(nihongodeok.hiwihhi_api_base + "/hottrends")
    keywords = nihongodeok.async_get(nihongodeok.hiwihhi_api_base + "/keywords/splitted?offset=1")

    hottrends = hottrends.decode_json()
    keywords = keywords.decode_json()

    kwd = {}
    for hottrend in hottrends:
        hashcode = hottrend[1]
        if hashcode not in kwd:
            kwd[hashcode] = nihongodeok.async_get(nihongodeok.api_base + "/search", { "q":hottrend[0],"limit":0 })
    for keyword in keywords:
        hashcode = keyword[1]
        if hashcode not in kwd:
            kwd[hashcode] = nihongodeok.async_get(nihongodeok.api_base + "/search", { "q":keyword[0],"limit":0 })

    for hashcode in kwd:
        kwd[hashcode] = kwd[hashcode].decode_json()[0]

    for hottrend in hottrends:
        hashcode = hottrend[1]
        if hashcode in kwd: hottrend.append(kwd[hashcode])
        
    for keyword in keywords:
        hashcode = keyword[1]
        if hashcode in kwd: keyword.append(kwd[hashcode])

    return (hottrends, keywords)

def get_article_by_id(article_id):
    return load("/get_article/%s" % article_id)

def request_clear_query_cache(table_name):
    nihongodeok.async_post(nihongodeok.api_base + "/clear_query_cache", {"table_name":table_name})

@app.route('/')
def index():
    articles = load("/latest_articles/ja")
    hottrends, keywords = load_keywords()

    return flask.render_template("index.html",articles=articles,hottrends=hottrends,keywords=keywords)

@app.route('/favicon.ico')
def favicon():
    return flask.send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/robots.txt')
def robots():
    return flask.send_from_directory(os.path.join(app.root_path, 'static'),
                               'robots.txt', mimetype='text/plain')

@app.route("/channel.html")
def channel_html_for_facebook():
    return '<script src="//connect.facebook.net/ja_JP/all.js"></script>'

@app.route("/login.html")
def login():
    if "user_id" not in flask.session:
        print flask.request.cookies
        cookie_name = "fbsr_" + nihongodeok.facebook_app_id
        if cookie_name in flask.request.cookies:
            flask.session["user_id"] = nihongodeok.get_user_id_from_external_id("fb_" + nihongodeok.parse_signed_request(flask.request.cookies[cookie_name])["user_id"])
    return flask.render_template("login.html", facebook_app_id=nihongodeok.facebook_app_id)

@app.route("/tools/")
def tools_index():
    return flask.render_template("tools_index.html")

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
        soup = BeautifulSoup(urllib2.urlopen(nihongodeok.api_base + "/cacheable_fetch?url=" + urllib2.quote(canonical_url)).read(),convertEntities=BeautifulSoup.HTML_ENTITIES)
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
        article = get_article_by_id(article_id)
    except urllib2.HTTPError, e:
        return "HTTP Error %d during communicating with API" % (e.code), e.code

    return flask.render_template("show_article.html", article=article)

@app.route("/tools/delete_article", methods=['POST'])
def delete_article():
    article_id = flask.request.form["article_id"]
    name = flask.request.form["name"]

    article = get_article_by_id(article_id)
    if article["scraped_by"] != name:
        return "Name doesn't match"

    req = urllib2.Request(nihongodeok.api_base + "/delete_article", urllib.urlencode({"article_id":article_id}))
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
        article = get_article_by_id(article_id)
    except urllib2.HTTPError, e:
        return "HTTP Error %d during communicating with API" % (e.code), e.code

    return flask.render_template("translate.html", article=article, message=message)

@app.route("/tools/translate/<article_id>", methods=['POST'])
def translate_post(article_id):
    subject = flask.request.form["subject"].encode("utf-8")
    body = flask.request.form["body"].encode("utf-8")
    params = {"article_id":article_id, "language":"ja", "subject":subject, "body":body}
    req = urllib2.Request(nihongodeok.api_base + "/translate_article", urllib.urlencode(params))
    result = json.load(urllib2.urlopen(req))

    article = nihongodeok.get_article(article_id)
    nihongodeok.request_page_capture(article["url"])
    words_en, words_ja = nihongodeok.create_bag_of_words(article)
    nihongodeok.push_bag_of_words(article_id, words_en, words_ja)

    return translate_get(article_id)

@app.route("/tools/new_article/<language>", methods=['GET'])
def new_article(language):
    return flask.render_template("new_article.html")

@app.route("/tools/new_article/<language>", methods=['POST'])
def new_article_post(language):
    url = flask.request.form["url"]
    subject = flask.request.form["subject"]
    body = flask.request.form["body"]
    scraped_by = flask.request.form["scraped_by"]
    site_id = flask.request.form["site_id"]
    date = flask.request.form["date"]
    if url =="" or subject == "" or body == "" or scraped_by == "" or site_id == "" or date == "":
        return "Bad Reqeust", 400
    request_body = json.dumps({"url":url, "language":language, 
                               "subject":subject, "body":body, 
                               "scraped_by":scraped_by,
                               "site_id":site_id, "date":date})
    req = urllib2.Request(nihongodeok.api_base + "/push_article", data=request_body, headers={'Content-type': 'application/json'})
    result = json.load(urllib2.urlopen(req))
    if result[1] == None: return "Failed"
    #else
    request_clear_query_cache("articles")
    return flask.redirect("/tools/edit_article/%s/%s" % (result[1], language))

@app.route("/tools/edit_article/<article_id>/<language>", methods=['GET'])
def edit_article(article_id, language):
    article = get_article_by_id(article_id)
    subject = article["subject_" + language]
    body = article["body_" + language]
    return flask.render_template("edit_article.html", language=language,article=article, subject=subject, body=body)

@app.route("/tools/edit_article/<article_id>/<language>", methods=['POST'])
def edit_article_post(article_id, language):
    pass

@app.route("/tools/synonyms/missing")
def missing_synonyms():
    sold_keywords = nihongodeok.async_get(nihongodeok.hiwihhi_api_base + "/keywords")
    synonyms = nihongodeok.async_get(nihongodeok.api_base + "/synonyms")
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
    synonyms = nihongodeok.async_get(nihongodeok.api_base + "/synonyms", {"q":keyword} )
    synonyms = synonyms.decode_json()
    data = {"keyword":keyword}
    if keyword in synonyms:
        data["synonyms"] = synonyms[keyword]
        data["count"] = nihongodeok.async_get(nihongodeok.api_base + "/search", {"q":data["synonyms"], "limit":0}).decode_json()[0]
    else:
        data["count"] = nihongodeok.async_get(nihongodeok.api_base + "/search", {"q":keyword, "limit":0}).decode_json()[0]

    return flask.render_template("edit_synonyms.html", **data)

@app.route("/tools/synonyms/edit", methods=['POST'])
def post_edit_synonym():
    keyword = flask.request.form["keyword"]
    synonyms = flask.request.form["synonyms"]
    result = nihongodeok.async_post(nihongodeok.api_base + "/synonym", {"keyword":keyword,"synonyms":synonyms}).decode_json()
    request_clear_query_cache("articles")
    return flask.redirect("/tools/synonyms/edit?keyword=%s" % urllib2.quote(keyword.encode("utf-8")) )

@app.route("/ts/<script_name>.js")
def ts(script_name):
    tsfile = "%s/ts/%s.ts" % (app.root_path, script_name)
    jsfile = "%s/ts/%s.js" % (app.root_path, script_name)

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

    return flask.send_file("%s/ts/%s.js" % (app.root_path, script_name), "text/javascript")

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

@app.route("/article/<article_id>.html")
def article(article_id):
    article = nihongodeok.async_get_article(article_id)
    related_articles = nihongodeok.async_get_related_articles(article_id)

    if article.response.status == 404:
        return "404 Not found", 404

    article = article.decode_json()
    related_articles = related_articles.decode_json()

    url = article["url"]

    pagecapture_path = "/%s/%s.png" % (article_id[:2], article_id)
    img_exists = nihongodeok.async_head(nihongodeok.pagecapture_base + pagecapture_path)
    pagecapture = None
    if img_exists.response.status == 200:
        pagecapture = nihongodeok.pagecapture_external_base + pagecapture_path
    else:
        nihongodeok.request_page_capture(url)

    return flask.render_template("article.html", article=article,pagecapture=pagecapture,related_articles=related_articles)

@app.route("/article/<article_id>/related.html")
def related_articles(article_id):
    if len(article_id) != 16:
        return "404 Not found", 404
    article = nihongodeok.async_get_article(article_id)
    related_articles = nihongodeok.async_get_related_articles(article_id, 20)
    if article.response.status == 404 or related_articles.response.status == 404:
        return "404 Not found", 404
    article = article.decode_json()
    related_articles = related_articles.decode_json()
    return flask.render_template("related_articles.html", article=article, related_articles=related_articles)

@app.route("/site/<site_id>/")
def by_site(site_id):
    hottrends, keywords = load_keywords()
    articles = load("/latest_articles/ja?site_id=%s" % urllib2.quote(site_id.encode("utf-8")))
    return flask.render_template("site.html", site_id=site_id,articles=articles,hottrends=hottrends,keywords=keywords)

@app.route("/date/<date>/")
def by_date(date):
    if not re.compile("^[0-9]{8}$").match(date):
        return "Bad date format", 400
    date = date[:4] + '-' + date[4:6] + '-' + date[6:8]
    hottrends, keywords = load_keywords()
    articles = load("/latest_articles/ja?date=%s" % urllib2.quote(date.encode("utf-8")))
    return flask.render_template("date.html", date=date,articles=articles,hottrends=hottrends,keywords=keywords)
    

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


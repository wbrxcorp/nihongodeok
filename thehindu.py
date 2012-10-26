#!/usr/bin/python
import feedparser
from BeautifulSoup import BeautifulSoup
import nihongodeok   # a library which is designed for this project. 
# you can save scraped articles to the database without MySQL APIs 
# through this "nihongodeok" library.   
# by the way,  "nihongo de ok"  means "You can tell me in Japanese language"

# defining constant values
# well experienced programmer defines constant values like below rather than
# simply putting values inside functions.  KEEP THIS IN YOUR MIND
SCRAPED_BY = "shimada"
LANGUAGE = "en"
SITE_ID = "The Hindu"
FEED_URL = "http://www.thehindu.com/?service=rss"

# scraper function what is designed only for a particular website.
# prepared BeautifulSoup object is given by caller as a paramater.
def scrape(soup):
    # extracting subject of the article from HTML structure
    h3s=soup.findAll('h1')
    for h1 in h3s:
	if len(h1.contents) == 0: continue
        subject = h1.contents[0].string
        break

    # extracting contents of the article
    h4s=soup.findAll('p', attrs={'class': 'body'})
    ps = []
    for p in h4s:
         if len(p.contents) == 0: continue
         ps.append(p.contents[0].string.strip())
    # "join" method concatinates array of string into one string object
    body = "\n\n".join(ps) # double line feeds between paragraphs

    # in Python, function can return multiple values unlike Java.
    return ( subject, body )

# create an Article object from specified link
# it downloads the webpage's HTML file specified by url and calls 
# scraper function to extract subject and body from it.
def create_article(url, article_date = None):
    # create a new Article object giving the article's URL.
    a = nihongodeok.Article(url)
    # set up necessary fields
    a.article_date = article_date
    a.scraped_by = SCRAPED_BY
    a.language = LANGUAGE
    a.site_id = SITE_ID

    # check if this article is already there in the database
    # this functionality is provided by nihongodeok library.
    if a.is_already_exist():
        print "Article already exists in database, skip."
        return # if so, just skip this article to save precious resources

    try:
        # download and parse the article's HTML file using BeautifulSoup
        soup = BeautifulSoup(a.open().read(),
                                 convertEntities=BeautifulSoup.HTML_ENTITIES)
    except Exception, e:
        # This exception may happen when the target website is having any problem
        # (e.g. server down, page deleted) or our network connection is in trouble.
        print "Article couldn't be downloaded due to an exception. skipping."
        print e
        return

    # call scraper function to extract article's subject and contents
    # scrape function returns both subject and body at the same time.
    a.subject, a.body = scrape(soup)

    # return an Article object just we made up completely to the caller
    return a

def run(push=True):
    # download feed and parse it
    feed = feedparser.parse( FEED_URL )

    # process each link
    for item in feed["items"]:
        # URL of one article
        link = item["link"]
        # article's publish date(it's provided in rfc822 format so it should be converted)
        article_date = nihongodeok.rfc822_to_date(item["published"])
        # call create_article specifying link. this function returns Article object
        a = create_article(link, article_date)
        # push generated Article object to the database server.
        # this functionality is provided by nihongodeok library.
        if push: a.push()
        else: a.dump() # just print it out to screen rather than sending to server if push==False

if __name__ == '__main__':
    # testing example: just scrape single article and print it to screen
    create_article("http://www.thehindu.com/news/international/china-expels-bo-xilai-from-legislature/article4033690.ece").dump()

    # spider a feed and scrape all articles and save them to database
    # if you giva False as a parameter, articles won't be saved and just printed in screen
    run()

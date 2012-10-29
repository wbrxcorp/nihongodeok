#!/usr/bin/python
import time
import feedparser
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

# collect latest articles' link from feed and scrape/save them
def run(push=True):
    # download feed and parse it
    feed = feedparser.parse( FEED_URL )

    # process each link
    for item in feed["items"]:
        # URL of one article
        link = item["link"]
        # create a new Article object giving the article's URL.
        a = nihongodeok.Article(link)
        # set up necessary fields
        a.scraped_by = SCRAPED_BY
        a.language = LANGUAGE
        a.site_id = SITE_ID

        # check if this article is already there in the database
        # this functionality is provided by nihongodeok library.
        if a.is_already_exist():
            print "Article already exists in database, skipping."
            continue # if so, just skip this article to save precious resources

        print "Processing: %s" % a.url
        # download and parse the article's HTML file using BeautifulSoup
        soup = a.parse()
        time.sleep(1)

        # call scraper function to extract article's subject and contents
        # scrape function returns both subject and body at the same time.
        a.subject, a.body = scrape(soup)

        # article's publish date(it's provided in rfc822 format so it should be converted)
        a.date = item["published"]

        # sometimes there are atciles what doesn't have any contents but photograph.
        # since articles without any text contents are out of our concern, you should skip such articles.
        # e.g. http://www.thehindu.com/news/cities/Hyderabad/livelihood-struggles/article4040473.ece
        if nihongodeok.normalize(a.body) == "": 
            print "Empty contents. URL=%s . skipping." % a.url
            continue   # nihongodeok.normalize() function removes unnecessary whitespaces from string

        # push generated Article object to the database server.
        # this functionality is provided by nihongodeok library.
        if push:
            result = a.push()
            print "pushed. url=%s, result=%s" % (a.url, result)
        else:
            a.dump() # just print it out to screen rather than sending to server if push==False

if __name__ == '__main__':
    # testing example: just scrape single article and print it to screen
    a = nihongodeok.Article("http://www.thehindu.com/news/cities/Delhi/airport-metro-dmrc-rejects-reliance-infras-offer-to-quit/article4038332.ece")
    a.scraped_by = SCRAPED_BY
    a.language = LANGUAGE
    a.site_id = SITE_ID
    a.subject, a.body = scrape(a.parse())
    a.date = "Sat, 27 Oct 2012 12:04:06 +0530"
    a.dump()

    # spider a feed and scrape all articles and save them to database
    # if you giva False as a parameter, articles won't be saved and just printed in screen
    run()

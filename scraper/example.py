#!/usr/bin/python
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

if __name__ == '__main__':
    # testing example: just scrape single article and print it to screen
    article_url = "http://www.thehindu.com/news/cities/Delhi/airport-metro-dmrc-rejects-reliance-infras-offer-to-quit/article4038332.ece"
    a = nihongodeok.Article(article_url) # create a new Article object with link
    if a.is_already_exist(): # check if article already exists in database
        print "Same artcile already exists in the database"

    # set up requested fields
    a.scraped_by = SCRAPED_BY
    a.language = LANGUAGE
    a.site_id = SITE_ID

    soup = a.parse()  # download link and generate BeautifulSoup instance automatically

    # get subject/body from soup using scrape function above
    a.subject, a.body = scrape(soup)

    # article date can be "YYYY-MM-DD" format or RFC822 like below
    a.date = "Sat, 27 Oct 2012 12:04:06 +0530"

    # print article on screen
    a.dump()  # you can save scraped article by using a.push() instead

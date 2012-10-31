# http://edition.cnn.com/2012/10/30/us/tropical-weather-sandy/index.html
def scrape(soup):
    def element_text(element):
        return ''.join(element.findAll(text=True))
    def join_all_paragraphs(paragraphs):
        return "\n\n".join(map(lambda x:element_text(x).strip(), paragraphs))

    subject = element_text(soup.findAll('h1')[0])

    paragraphs = []
    first_one = soup.findAll('p', attrs={'class': None})
    if len(first_one) > 0: paragraphs.append(first_one[0])
    paragraphs += soup.findAll('p', attrs={'class': re.compile(r'\bcnn_storypgraphtxt\b')})

    body = join_all_paragraphs(paragraphs)

    date = None  # leave it to feed

    return (subject, body, date)
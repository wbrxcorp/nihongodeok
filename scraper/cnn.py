# http://edition.cnn.com/2012/10/30/us/tropical-weather-sandy/index.html
def scrape(soup):
    subject = soup.findAll('h1')[0].string
    paragraphs = []
    first_one = soup.findAll('p', attrs={'class': None})
    if len(first_one) > 0: paragraphs.append(first_one[0])
    paragraphs += soup.findAll('p', attrs={'class': re.compile(r'\bcnn_storypgraphtxt\b')})
    if len(paragraphs) == 0: return None

    body = "\n\n".join(map(lambda x:''.join(x.findAll(text=True)), paragraphs))

    return (subject, body, None)

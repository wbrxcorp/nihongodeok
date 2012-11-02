#!/usr/bin/python
import urllib2
from BeautifulSoup import BeautifulSoup,Comment

soup = BeautifulSoup("<html><body><p>Hello!</p><p><script>aaa</script></p><p>World!</p>")
ps = soup.findAll("p")

print "Before filter"
for p in ps:
    print p.text # Hello! aaa World!

# execute filter
ps = filter(lambda x:len(x.findAll("script"))==0, ps)

print "After filter"
for p in ps:
    print p.text # Hello! World!




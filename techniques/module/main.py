import thehindu
import yahoo
import bbc

if __name__ == '__main__':
	for site in ( thehindu, yahoo, bbc ):
		site.run()


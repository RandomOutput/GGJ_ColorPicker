from twython import Twython, TwythonError
import Configs
import urllib2
from PIL import Image
from io import BytesIO

lastIncomingId = 427496529838886912

def extractImageUrl(post):
	entities = None
	media = None
	url = None
	if "entities" in post:
		entities = post["entities"]

		if "media" in entities:
			media = entities["media"]

		if media != None and len(media) > 0 and "media_url_https" in media[0]:
			url = media[0]["media_url_https"]

	return url

def extractUsername(post):
	user = None
	screen_name = None

	if "user" in post:
		user = post["user"]

		if "screen_name" in user:
			screen_name = user["screen_name"]

	return screen_name


twitter_acnt = Twython(
					Configs.consumer_key,
					Configs.consumer_secret,
					Configs.access_token_key,
					Configs.access_token_secret)

mention_posts = twitter_acnt.get_mentions_timeline(since_id=lastIncomingId)

for post in mention_posts:
	print str(extractUsername(post)) + ": " + str(extractImageUrl(post)) + "\n"

	url = extractImageUrl(post)

	if url != None:
		image_data = urllib2.urlopen(url).read()
		im = Image.open(BytesIO(image_data))
		print str(im)
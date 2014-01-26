from threading import RLock, Thread, Timer, currentThread
from twython import Twython, TwythonError
import logging
import sys
import time
from datetime import datetime
from BotException import BotException
import traceback
import Configs
import ColorPicker
import re
import math
from PIL import Image
from io import BytesIO
import urllib2

logging.basicConfig(filename='logs.log',level=logging.INFO)


class ColorBot:
	def __init__(self):
		if __name__ != "__main__":
			raise BotException("ColorBot must run in the main module")

		self.started = False
		self.postInterval = 2
		self.postQueue = []

		#Update data
		self.updateInterval = 60

		#The goal image
		self.goalImage = None

		#Data for grabbing incoming posts from twitter
		self.incomingQueue = []
		self.lastIncomingId = 427546836853735424

		#Image processing Worker Queue
		self.imageWorkers = []
		self.continueWork = False
		self.workerCount = 5

		#Store the best submission this round
		self.bestPost = None
		self.bestDistance = sys.float_info.max

		self.lastPost = ""
		self.lastPostTime = 0

		self.printLock = RLock()
		self.post_lock = RLock()
		self.data_lock = RLock()

	#Blocks until bot exits
	def startBot(self):
		self.logInfo("Starting ThreadedBot.")

		self.started = True

		try:
			self.twitter_acnt = Twython(
					Configs.consumer_key,
					Configs.consumer_secret,
					Configs.access_token_key,
					Configs.access_token_secret)
		except:
			raise

		self.roundThread = None
		self.updateThread = None

		while True:
			console_input = raw_input("--> ").lower()

			input_responses = {
				'startround': (self.startRound, []),
				'exitbot': (self.stopBot, []),
				'printlastpost': (self.printLastPost, []),
				'endround': (self.endRound, [])
			}
			
			response = input_responses.get(console_input, (bot.inputError, []))

			print str(response)
			
			try:
				directive = response[0](*response[1])
			except BotException as e:
				if e.value == "Unrecognized Command.":
					print "Unrecognized Command."
					continue
				else:
					raise

			if directive == "kill":
				break
			elif directive != None:
				print str(directive)

	def startRound(self):
		filename = raw_input("image filename: ")
		post_text = raw_input("post text: ")
		round_len = raw_input("round length: ")

		bestDistance = sys.float_info.max
		bestPost = None
		
		try: 
			round_len = int(round_len)
		except:
			print "Can't convert to integer."
			return None

		try:
			im = Image.open(filename)
		except:
			print "Can't open image: " + str(sys.exc_info()[0])
			return None

		#Set the last known id to the ID of the starting post.
		self.lastIncomingId = self.makePost(post=str(post_text), media=im)
		self.goalImage = im

		self.clearRoundData()
		self.restartUpdateThread()

		self.startWorkerQueue()
		self.killRoundThread()
		self.roundThread = Timer(round_len, self.endRound)

		self.roundThread.start()

	def clearRoundData(self):
		self.stopWorkerQueue()

		with self.data_lock:
			self.bestImage = None
			self.imageQueue = [] 

	def startWorkerQueue(self):
		self.logInfo("Start Worker Queue")
		self.continueWork = True
		for i in range(0,self.workerCount):
			newWorker = Thread(target=self.processImageFromQueue)
			self.imageWorkers.append(newWorker)
			newWorker.start()

	def stopWorkerQueue(self):
		self.logInfo("Stop worker queue")
		self.continueWork = False
		#Do something to stop the worker queue
		for worker in self.imageWorkers:
			worker.join()

		self.imageWorkers = []

	def processImageFromQueue(self):
		while self.continueWork:
			myPost = None

			with self.data_lock:
				if len(self.incomingQueue) > 0:
					self.logInfo("Gonna get a post")
					myPost = self.incomingQueue.pop(0)
				else:
					continue

			if self.goalImage == None:
				continue

			self.logInfo("Start processing image")

			#result = Get Post and result
			if myPost != None:
				url = self.extractImageUrl(myPost)
				image_data = urllib2.urlopen(url).read()
				im = Image.open(BytesIO(image_data))

				try:
					result = ColorPicker.getColorDiff(im, self.goalImage)
				except:
					self.logError("Error decoding posted image." + str(sys.exc_info()[0]))
					traceback.print_exc()
					continue

				with self.data_lock:
					if(result < self.bestDistance):
						self.logInfo("New best distance: " + str(result))
						self.bestDistance = result
						self.bestPost = myPost
					else:
						self.logInfo("Not quite good enough.")

			self.logInfo("Done processing.")

	def getPostsFromTwitter(self):
		self.logInfo("Get posts from twitter")
		if self.lastIncomingId == None:
			self.logError("Don't have the last incoming tweet set")
			return None
			
		mention_posts = self.twitter_acnt.get_mentions_timeline(since_id=self.lastIncomingId)
		count = 0
		for post in mention_posts:
			if self.extractImageUrl(post) != None:
				with self.data_lock:
					count += 1
					self.incomingQueue.append(post)

			post_id = self.extractPostId(post)

			if post_id != None:
				self.lastIncomingId = post_id

		self.logInfo("Got " + str(count) + " posts")
		self.restartUpdateThread()

	def restartUpdateThread(self):
		if self.updateThread:
			self.updateThread.cancel()

			if currentThread() != self.updateThread and self.updateThread.is_alive():
					try:
						self.updateThread.join()
					except RuntimeError as e:
						self.logError("RuntimeError stopping updateThread: " + str(e))

		self.updateThread = None
		self.updateThread = Timer(self.updateInterval, self.getPostsFromTwitter)
		self.updateThread.start()

	def endRound(self):
		self.killRoundThread()

		if self.bestPost != None:
			post_text = "We have a winnder! @" + str(self.extractUsername(self.bestPost)) + " with their image "
			url = self.extractImageUrl(self.bestPost)
			image_data = urllib2.urlopen(url).read()
			im = Image.open(BytesIO(image_data))
			self.makePost(post=str(post_text), media=im)
		else:
			self.logInfo("No submissions.")
			self.makePost(post="The round's over but no one submitted :-( Come on #GGJ14 and #SFGGJ14!")

	def killRoundThread(self):
		if self.roundThread:
				self.roundThread.cancel()
				
				if currentThread() != self.roundThread and self.roundThread.is_alive():
					try:
						self.roundThread.join()
					except RuntimeError as e:
						self.logError("RuntimeError stopping roundThread: " + str(e))

				self.roundThread = None

	def makePost(self, post, media=None):
		if not self.started:
			raise BotException("Bot not started.")

		with self.post_lock, self.data_lock:
				try:	
					self.logInfo("post text = " + str(post))
					if media != None:
						media.save('image.png')
						imageData = open('image.png', "rb")
						response = self.twitter_acnt.update_status_with_media(status=post, media=imageData)
					else:
						response = self.twitter_acnt.update_status(status=post)

					if response != None:
						if "id" in response:
							return response["id"]
						else:
							return None
				except TwythonError as e:
					self.logError("Trython error posting tweet: " + str(e))
					traceback.print_exc()
				except NameError as e:
					self.logError("NameError error posting tweet: " + str(e))
					traceback.print_exc()
				except AttributeError as e:
					self.logError("AttributeError error posting tweet: " + str(e))
					traceback.print_exc()
				except:
					self.logError("Unexpected error posting tweet: " + str(sys.exc_info()[0]))
					traceback.print_exc()

		return None

	def extractImageUrl(self, post):
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

	def extractUsername(self, post):
		user = None
		screen_name = None

		if "user" in post:
			user = post["user"]

			if "screen_name" in user:
				screen_name = user["screen_name"]

		return screen_name

	def extractPostId(self, post):
		if "id" in post:
			return post["id"]

		return None

	def printLastPost(self):
		if not self.started:
			raise BotException("Bot not started.")

		with self.postLock:
			return str("Last Post: " + self.lastPost)

	def flushQueue(self):
		if not self.started:
			raise BotException("Bot not started.")

		with self.data_lock:
			self.logInfo(str("Flushing the Queue"))

			return "Queue Flushed"


	def stopBot(self):
		if not self.started:
			raise BotException("Bot not started.")

		self.logInfo(str("Stopping Bot"))
		print "Stopping Bot"

		self.stopWorkerQueue()

		with self.post_lock, self.data_lock:
			self.logInfo(str("Waiting on updateThread to terminate."))
			if self.updateThread != None:
				self.updateThread.cancel()

			self.logInfo(str("Waiting on roundThread to terminate."))
			if self.roundThread != None:
				self.roundThread.cancel()

			if self.updateThread != None and self.updateThread.is_alive():
				try:
					self.updateThread.join()
				except RuntimeError as e:
					self.logError("RuntimeError stopping updateThread: " + str(e))

			if self.roundThread != None and self.roundThread.is_alive():
				try:
					self.roundThread.join()
				except RuntimeError as e:
					self.logError("RuntimeError stopping roundThread: " + str(e))

			self.updateThread = None
			self.roundThread = None

			return "kill"

	def logInfo(self, message):
		with self.printLock:
			logging.info(str(datetime.now().strftime(" %Y-%m-%d %H:%M:%S: ")) + str(message))

	def logError(self, message):
		with self.printLock:
			logging.error(str(datetime.now().strftime(" %Y-%m-%d %H:%M:%S: ")) + str(message))

	def inputError(self):
		raise BotException("Unrecognized Command.")

if __name__ == "__main__":
	bot = ColorBot()

	try:
		bot.startBot()
	except:
		bot.logError("Error in bot - " + str(sys.exc_info()[0]))
		logging.exception("Exception Info:")
		traceback.print_exc()
		bot.stopBot()

	bot.logInfo("------> Nominal Exit.\n\n")
	print "\n------> Nominal Exit."

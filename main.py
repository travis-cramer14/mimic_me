# Last modified: September 29, 2018 4:20pm
# This script runs the @get_mimicked Twitter bot. 

import datetime as dt
import json
import operator
import re
import sys
import time

import requests
import twitter

from markov_python.cc_markov import MarkovChain

# configurations
use_mysql = False  # uses a local mysql database rather than a .txt file -- requires some setup
forever = False  # runs while loop forever -- instead of using a scheduler like cron
verbose = False  # will print logs on every run -- false will print only logs when new tweet is posted

# messages
SORRY_RESPONSE = 'Sorry, you must have at least 100 words tweeted in total to be mimicked.'
INFORMATION_RESPONSE = 'Well, hi there! Tweet at me with the words "Mimic me" to get a mimicking response!'

# import passwords for Twitter REST API from local text file
passwords_file = open('passwords.txt', 'r')
passwords = passwords_file.readlines()
for password in passwords:
	passwords[passwords.index(password)] = password.replace('\n', '')

twitter_consumer_key = passwords[0]
twitter_consumer_secret = passwords[1]
twitter_access_token = passwords[2]
twitter_access_secret = passwords[3]

if use_mysql:
	import mysql.connector
	mysql_password = passwords[4]

passwords_file.close()

# instantiate API
twitter_api = twitter.Api(consumer_key=twitter_consumer_key, consumer_secret=twitter_consumer_secret, 
					access_token_key=twitter_access_token, access_token_secret=twitter_access_secret,
					sleep_on_rate_limit=True)


def remove_last_word(sentence):
	# Removes the last word of a sentence (and keeps the period).
	# split sentence into a list of all the words, call it post
	post = sentence.split(' ')

	# remove the last word from post
	post = post.remove(post[-1])

	# iterate from list into string again
	new_sentence = ''
	for i in range(len(post)):
		new_sentence = new_sentence + post[i] + ' '

	# Remove extra space and add a period back onto the end of the new sentence.
	new_sentence = new_sentence[:-1] + '.'
	return new_sentence


def mimic_me(handle):
	# Takes in the other user's twitter handle and returns a tweet in the style of their tweets
	statuses = twitter_api.GetUserTimeline(screen_name = handle, count = 1000, include_rts = False)
	text = ""
	for status in statuses:
		if status.lang == 'en':
			text += status.text.encode('utf-8') + ' '


	# remove handles # take out all mentions in the generated tweet. (maybe so that random friends don't get mad)
	handles = re.findall('@[^ ]*', text)
	for handle in handles:
		text = text.replace(handle, '')

	#remove parentheses
	bad_characters = re.findall('\(', text) + re.findall('\)', text)
	for character in bad_characters:
		text = text.replace(character, '')

	if len(text.split(' ')) <= 100:
		return 0
	else:
		pass

	mc = MarkovChain()
	mc.add_string(text)
	result = mc.generate_text()

	# Capitalize the first word in the generated sentence.
	letter = result[0][0]
	rest_of_word = result[0][1:]
	capped_word = letter.upper() + rest_of_word
	result[0] = capped_word

	# Put a period at the end of the last word in the generated sentence.
	result[len(result) - 1] = result[len(result) - 1] + '.'

	new_tweet = ''
	for i in range(len(result)):
		new_tweet = new_tweet + result[i] + ' '

		# ensure that new tweet is 140 characters or less
	while len(new_tweet) > 240:
		new_tweet = remove_last_word(new_tweet)

	return new_tweet


def main():
	# get past mimics 
	if use_mysql:
		# connect to mysql for storing past_mimics data
		cnx = mysql.connector.connect(user='travis.cramer14@gmail.com', password=my_mysql_password, 
											host='127.0.0.1', database='my_database')
		# instantiate cursor for querying
		cursor = cnx.cursor()

		# get all past mimics into list
		cursor.execute("SELECT screen_name, date_time FROM past_mimics")
		past_mimics = []
		for (screen_name, date_time) in cursor:
			past_mimics.append(screen_name + ' ' + date_time)
	else:
		# open past_mimics for reading and appending
		file_1 = open('past_mimics.txt', 'r')
		file_2 = open('past_mimics.txt', 'a')

		# get all past_mimics into list
		past_mimics = file_1.readlines()
		for mimic in past_mimics:
			past_mimics[past_mimics.index(mimic)] = mimic.replace('\n', '')

	# collect 20 most recent mentions
	mentions = twitter_api.GetMentions(count=5)

	# check if new mention, check if 'mimic me' is in mention, then create mimic and post mimic of mentioner
	new_mention = False
	for mention in mentions:
		status_id = mention.id
		their_handle = mention.user.screen_name
		mention_simple = mention.user.screen_name + ' ' + mention.created_at

		if mention_simple not in past_mimics:
			new_mention = True

			if ('mimic me' in mention.text.lower()):
				#send their_handle through mimic_me function to generate tweet
				result = mimic_me(their_handle)
				
				if result != 0:
					twitter_api.PostUpdate(status=('Mimicking ' + ('@%s: ' % (their_handle)) + result),
										   in_reply_to_status_id=status_id)
					print 'New mimic: @%s' %(their_handle)
				elif result == 0:
					try:
						twitter_api.PostUpdate(status=('@%s ' % (their_handle) + ' ' + SORRY_RESPONSE),
											   in_reply_to_status_id=status_id)
						print "Made sorry response to @%s" % (their_handle)
					except twitter.error.TwitterError:
						pass
			else:
				try:
					twitter_api.PostUpdate(status=('@%s ' %(their_handle) + ' ' + INFORMATION_RESPONSE),
										   in_reply_to_status_id=status_id)
					print "Made an informational response to @%s" %(their_handle)
				except twitter.error.TwitterError:
					pass

			if use_mysql:
				# record the new mention (and correlated successful response/reply) into database
				cursor.execute("SELECT MAX(id) FROM past_mimics")
				for (id) in cursor:
					max_id = id[0]
				cursor.execute("INSERT INTO past_mimics (id, screen_name, date_time)"
							"VALUES (%d, '%s', '%s')" %(max_id + 1, their_handle, mention.created_at))
			else:
				# store new mention (in local past_mimics.txt file)
				file_2.write(mention_simple + '\n')

	if not new_mention:
		if verbose:
			print 'No new mentions.'

	# close connections
	if use_mysql:
		cnx.commit()
		cnx.close()
	else:
		file_1.close()
		file_2.close()


if forever:
	# infinitely loop while running script
	while True:
		if verbose:
			print '-----------------------------------------------------'
			print dt.datetime.now().strftime("%Y-%m-%d %H:%M")
		main()
		# sleep for 5~ minutes before checking twitter again for new mentions
		if verbose:
			print 'Now waiting 5 minutes...'
			time.sleep(300)
else:
	if verbose:
		print '-----------------------------------------------------'
		print dt.datetime.now().strftime("%Y-%m-%d %H:%M")
	main()

import tweepy
import re
import json

import sqlite3 as lite

import datetime, time, os, sys
import argparse, ConfigParser
Config = ConfigParser.ConfigParser()
Config.read('config.cnf')

litecon = lite.connect('data/twitter.db')

with litecon:

# set up SQL tables
	litecur = litecon.cursor()
	litecur.execute("CREATE TABLE IF NOT EXISTS sample (old_screen_name TEXT, max_tweet_time TEXT, stratum INT, tweet_id TEXT, user_id, current_screen_name TEXT, error TEXT, modified TEXT)")

	# index every column for good measure
	litecur.execute("CREATE INDEX IF NOT EXISTS sample_old_screen_name ON sample (old_screen_name)")
	litecur.execute("CREATE INDEX IF NOT EXISTS sample_max_tweet_time ON sample (max_tweet_time)")
	litecur.execute("CREATE INDEX IF NOT EXISTS sample_stratum ON sample (stratum)")
	litecur.execute("CREATE UNIQUE INDEX IF NOT EXISTS sample_tweet_id ON sample (tweet_id)")
	litecur.execute("CREATE INDEX IF NOT EXISTS sample_user_id ON sample (user_id)")
	litecur.execute("CREATE INDEX IF NOT EXISTS sample_current_screen_name ON sample (current_screen_name)")
	litecur.execute("CREATE INDEX IF NOT EXISTS sample_error ON sample (error)")
	litecur.execute("CREATE INDEX IF NOT EXISTS sample_modified ON sample (modified)")

	litecur.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT, screen_name TEXT, user_object TEXT)")
	litecur.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_user_id ON users (user_id)")
	litecur.execute("CREATE INDEX IF NOT EXISTS users_screen_name ON users (screen_name)")


consumer_key = Config.get('twitter', 'consumer_key')
consumer_secret = Config.get('twitter', 'consumer_secret')
access_token = Config.get('twitter', 'access_token')
access_token_secret = Config.get('twitter', 'access_token_secret')

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
# set up access to the Twitter API
api = tweepy.API(auth)

def load_file(filename):
	with open(filename, 'r') as f:
		l = f.readline()

		with litecon:
			litecur = litecon.cursor()
			for l in f:
				l = [x.strip('"') for x in l.strip().split('\t')]
				screenname = l[0]
				max_tweet_time = l[1]
				stratum = l[2]
				tweet_id = l[3]

				try:
					litecur.execute('INSERT INTO sample (old_screen_name, max_tweet_time, stratum, tweet_id) VALUES (?, ?, ?, ?)', (screenname, max_tweet_time, stratum, tweet_id))
				except lite.IntegrityError:
					# don't worry about duplicates
					pass

def get_user_from_tweet(tweet_id):
	while True:
		try:
			status = api.get_status(tweet_id)
			return {tweet_id: status.author}

		except tweepy.TweepError, error:
			if (type(error) == tweepy.RateLimitError):
				print 'Rate limited. Sleeping for 15 minutes.'
				time.sleep(15 * 60 + 10)
				continue

			return error

	print 'something else went wrong: ' + tweet_id
	return False

def get_user_from_tweet_batch(tweet_ids):
	while True:
		try:
			statuses = api.statuses_lookup(tweet_ids)
			return {tweet.id: tweet.author for tweet in statuses}

		except tweepy.TweepError, error:
			if (type(error) == tweepy.RateLimitError):
				print 'Rate limited. Sleeping for 15 minutes.'
				time.sleep(15 * 60 + 10)
				continue

			return error

	print 'something else went wrong: ' + tweet_id
	return False	

def __update_user_id_in_sample(tweet_id, user):
	'''
	Do the actual SQLite update with the info collected
	'''
	now = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
	with litecon:
		litecur = litecon.cursor()
		if (type(user) != tweepy.TweepError):
			litecur.execute('UPDATE sample SET user_id = ?, current_screen_name = ?, modified = ? WHERE tweet_id = ?', (user.id, user.screen_name, now, tweet_id))
			try:
				litecur.execute('INSERT INTO users (user_id, screen_name, user_object) VALUES (?, ?, ?)', (user.id, user.screen_name, json.dumps(user._json)))
			except lite.IntegrityError:
				# don't worry about duplicates
				pass
		else:
			print tweet_id, user
			try:
				error_message = user[0][0]['message']
			except:
				error_message = 'Unknown'

			litecur.execute('UPDATE sample SET error = ?, modified = ? WHERE tweet_id = ?', (error_message, now, tweet_id))


def update_user_id_in_sample():
	'''
	Find all the tweets in the sample that have not been fetched yet
	and make individual calls to find the users associated with them
	'''
	with litecon:
		litecur = litecon.cursor()
		litecur.execute('SELECT tweet_id FROM sample WHERE user_id IS NULL AND error IS NULL')
		sampled = litecur.fetchall()

		for s in sampled:
			tweet_id = s[0]
			for tweet_id, user in get_user_from_tweet(tweet_id):
				__update_user_id_in_sample(tweet_id, user)
			

def update_user_id_in_sample_batch():
	'''
	Find all the tweets in the sample that have not been fetched yet
	and make a batch call to find the users associated with them
	'''
	with litecon:
		litecur = litecon.cursor()
		litecur.execute('SELECT tweet_id FROM sample WHERE user_id IS NULL AND error IS NULL')

		while (True):
			tweet_ids = [t[0] for t in litecur.fetchmany(100)]
			if not tweet_ids: break

			for tweet_id, user in get_user_from_tweet_batch(tweet_ids).iteritems():
				__update_user_id_in_sample(tweet_id, user)



if __name__ == '__main__':
	ap = argparse.ArgumentParser()
	ap.add_argument("-t", "--tweet-id", required=False, help="Specify a Tweet ID of the user you are interested in")
	ap.add_argument("-s", "--screen-name", required=False, help="Screen name or user ID of twitter user")
	ap.add_argument("-f", "--input-file", required=False, help="Specify a dump file from ESBI")
	args = vars(ap.parse_args())

	tweet_id = args['tweet_id']
	screenname = args['screen_name']
	input_filename = args['input_file']

	if tweet_id: 
		get_user_from_tweet(tweet_id)
	elif input_filename:
		load_file(input_filename)

	update_user_id_in_sample_batch()
	update_user_id_in_sample()  # this will go back and fill in individual errors. The batch simply doesn't return errors

	# if not tweet_id and not screenname and not input_filename:
	# 	print "You need at least one input. "
	# 	exit(1)


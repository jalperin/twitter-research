import tweepy
import re
import json

import botornot

import sqlite3 as lite

import datetime, time, os, sys
import argparse, ConfigParser
Config = ConfigParser.ConfigParser()
Config.read('config.cnf')

litecon = lite.connect('data/bmcTwitter.db')

with litecon:

# set up SQL tables
	litecur = litecon.cursor()
	# the sample, with two columns for either the Tweet itself, or the error in trying to retrieve it
	litecur.execute("CREATE TABLE IF NOT EXISTS sample (doi TEXT, old_screen_name TEXT, tweet_id TEXT, tweet TEXT, error TEXT, modified TEXT)")

	litecur.execute("CREATE INDEX IF NOT EXISTS sample_old_screen_name ON sample (old_screen_name)")
	litecur.execute("CREATE UNIQUE INDEX IF NOT EXISTS sample_tweet_id ON sample (tweet_id)")
	litecur.execute("CREATE INDEX IF NOT EXISTS sample_modified ON sample (modified)")

	# the users that were found
	litecur.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT, screen_name TEXT, user_object TEXT, timeline TEXT, timeline_error TEXT, timeline_modified TEXT, user_modified TEXT, botornot_score REAL, botornot TEXT, botornot_modified TEXT)")
	litecur.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_user_id ON users (user_id)")
	litecur.execute("CREATE INDEX IF NOT EXISTS users_screen_name ON users (screen_name)")	

	litecur.execute("CREATE TABLE IF NOT EXISTS friends (user_id TEXT, friend_id TEXT, modified TEXT)")
	litecur.execute("CREATE INDEX IF NOT EXISTS friends_user_id ON friends (user_id)")
	litecur.execute("CREATE UNIQUE INDEX IF NOT EXISTS friends_user_friend_id ON friends (user_id, friend_id)")

	litecur.execute("CREATE TABLE IF NOT EXISTS followers (user_id TEXT, follower_id TEXT, modified TEXT)")
	litecur.execute("CREATE INDEX IF NOT EXISTS followers_user_id ON followers (user_id)")
	litecur.execute("CREATE UNIQUE INDEX IF NOT EXISTS followers_user_follower_id ON followers (user_id, follower_id)")


consumer_key = Config.get('twitterdissertation', 'consumer_key')
consumer_secret = Config.get('twitterdissertation', 'consumer_secret')
access_token = Config.get('twitterdissertation', 'access_token')
access_token_secret = Config.get('twitterdissertation', 'access_token_secret')

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
# set up access to the Twitter API
api = tweepy.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

twitter_app_auth = {
    'consumer_key': consumer_key,
    'consumer_secret': consumer_secret,
    'access_token': access_token,
    'access_token_secret': access_token_secret,
    'wait_on_rate_limit': True, 
    'wait_on_rate_limit_notify': True
  }
bon = botornot.BotOrNot(**twitter_app_auth)
bon.twitter_api.wait_on_rate_limit_notify = True

def load_file(filename):
	with open(filename, 'r') as f:
		l = f.readline()

		with litecon:
			litecur = litecon.cursor()
			for l in f:
				l = [x.strip('"') for x in l.strip().split('\t')]
				doi = l[0]
				screenname = l[1]
				tweet_id = l[2]

				try:
					litecur.execute('INSERT INTO sample (doi, old_screen_name, tweet_id) VALUES (?, ?, ?)', (doi, screenname, tweet_id))
				except lite.IntegrityError:
					# don't worry about duplicates
					pass

def __save_tweet(tweet_id, tweet, error = None):
	'''
	Do the actual SQLite update with the info collected
	'''
	now = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
	with litecon:
		litecur = litecon.cursor()

		if error: 
			try: 
				m = error[0][0]['message']
			except:
				m = str(error)
			litecur.execute('UPDATE sample SET error = ?, modified = ? WHERE tweet_id = ?', (m, now, tweet_id))	

		else: 
			litecur.execute('UPDATE sample SET tweet = ?, modified = ? WHERE tweet_id = ?', (json.dumps(tweet._json), now, tweet_id))
			try:
				litecur.execute('INSERT INTO users (user_id, screen_name, user_object, user_modified) VALUES (?, ?, ?, ?)', (tweet.user.id, tweet.user.screen_name, json.dumps(tweet.user._json), now))
			except lite.IntegrityError:
				# don't worry about duplicates
				pass

def __save_timeline(user_id, timeline, error = None):
	'''
	Do the actual SQLite update with the info collected
	'''
	now = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
	with litecon:
		litecur = litecon.cursor()

		if error: 
			try: 
				m = error[0][0]['message']
			except:
				m = str(error)
			litecur.execute('UPDATE users SET timeline_error = ?, timeline_modified = ? WHERE user_id = ?', (m, now, user_id))	

		else: 
			litecur.execute('UPDATE users SET timeline = ?, timeline_modified = ? WHERE user_id = ?', (json.dumps([s._json for s in timeline]), now, user_id))

def __save_botornot(user_id, botornot, error = None):
	'''
	Do the actual SQLite update with the info collected
	'''
	now = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
	with litecon:
		litecur = litecon.cursor()

		if error: 
			try: 
				m = error[0][0]['message']
			except:
				m = str(error)
			litecur.execute('UPDATE users SET botornot = ?, botornot_score = ?, botornot_modified = ? WHERE user_id = ?', (m, -1, now, user_id))	

		else: 
			litecur.execute('UPDATE users SET botornot = ?, botornot_score = ?, botornot_modified = ? WHERE user_id = ?', (json.dumps(botornot), botornot['score'], now, user_id))


def get_tweets_in_sample():
	'''
	Find all the tweets in the sample that have not been fetched yet
	and make individual calls to find the users associated with them
	'''
	with litecon:
		litecur = litecon.cursor()
		litecur.execute("SELECT tweet_id, old_screen_name FROM sample WHERE tweet IS NULL")
		sampled = litecur.fetchall()

		for s in sampled:
			tweet_id = s[0]
			try:
				tweet = api.get_status(tweet_id)
				__save_tweet(tweet_id, tweet)

			except tweepy.TweepError, error: 
				# bit hacky, we're passing a tweet_id instead of a tweet here
				try: 
					user = api.get_user(screen_name=s[1])
					try:
						error[0][0]['message'] += '; Found by screen_name'
						__save_tweet(tweet_id, None, error)
						now = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
						litecur.execute('INSERT INTO users (user_id, screen_name, user_object, user_modified) VALUES (?, ?, ?, ?)', (user.id, user.screen_name, json.dumps(user._json), now))
					except lite.IntegrityError:
						# don't worry about duplicates
						pass

				except tweepy.TweepError, error2: 
					__save_tweet(tweet_id, None, error) # leave the original error

		# now try all the errors one more time
		litecur.execute('SELECT tweet_id FROM sample WHERE tweet IS NULL AND error IS NOT NULL')
		sampled = litecur.fetchall()

def get_tweets_in_sample_batch():
	'''
	Find all the tweets in the sample that have not been fetched yet
	and make a batch call to find the users associated with them
	'''
	with litecon:
		litecur = litecon.cursor()
		litecur.execute('SELECT tweet_id FROM sample WHERE tweet IS NULL AND error IS NULL')

		while (True):
			tweet_ids = [t[0] for t in litecur.fetchmany(100)]
			if not tweet_ids: break

			try:
				statuses = api.statuses_lookup(tweet_ids)
				for tweet in statuses:
					__save_tweet(tweet.id, tweet)

			except tweepy.TweepError, error: 
				print error
				exit(1)

def get_timelines_batch():
	'''
	Get all the timeline JSON objects for users we know exist (we've saved)
	'''
	while (True):
		with litecon:
			litecur = litecon.cursor()
			litecur.execute('SELECT u.user_id FROM users u WHERE timeline IS NULL AND timeline_error IS NULL')

			# go 100 at a time so we're not hitting the DB so much
			user_ids = [u[0] for u in litecur.fetchmany(100)]
			if not user_ids: break

			for user_id in user_ids: 
				try:
					timeline = api.user_timeline(user_id)
					__save_timeline(user_id, timeline)

				except tweepy.TweepError, error: 
					__save_timeline(user_id, None, error)

def get_botornot():
    '''
    Query the Bot or Not API for users we know exist (we've saved)
    '''
    with litecon:
        litecur = litecon.cursor()
        litecur.execute('SELECT user_id, screen_name FROM users WHERE botornot IS NULL')

    while (True):      
    	# go 100 at a time so we're not hitting the DB so much
        users = litecur.fetchmany(100)
        if not users: break

        for (user_id, screen_name) in users:
            try:
                response = bon.check_account('@%s' % screen_name)
                __save_botornot(user_id, response)
            except tweepy.TweepError, error: 
                __save_botornot(user_id, None, error)

def __save_network(endpoint, user_id, ids, error = None):
    '''
    Do the actual SQLite update with the info collected
    '''
    now = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    with litecon:
        litecur = litecon.cursor()
        
        if error: 
            try: 
                m = error[0][0]['message']
            except:
                m = str(error)
                
            print "Error: ", user_id, m
            litecur.execute('INSERT INTO %s (user_id, %s_id, modified) VALUES (?, ?, ?)' % (endpoint, endpoint[:-1]), (user_id, -1, now))
        else:
            print 'saving', len(ids)
            for f in ids:
                try: 
                    litecur.execute('INSERT INTO %s (user_id, %s_id, modified) VALUES (?, ?, ?)' % (endpoint, endpoint[:-1]), (user_id, f, now))
                except lite.IntegrityError:
                    pass # ignore duplicates, they wont change the network
                    
def get_friends(user_id = None):
    get_network('friends', user_id)

def get_followers(user_id = None):
    get_network('followers', user_id)
            
def get_network(endpoint, user_id = None):
    '''
    Get the friends/followers list for all users (or for a specific user
    '''
    if user_id is None:       
        while (True):
            with litecon:
                litecur = litecon.cursor()
                litecur.execute('SELECT u.user_id FROM users u LEFT JOIN %s f ON (u.user_id = f.user_id) WHERE f.user_id IS NULL' % endpoint)
        
            # go 100 at a time so we're not hitting the DB so much
            users = [u[0] for u in litecur.fetchmany(100)]
            if not users: break

            for user_id in users:
                ids = get_network(endpoint, user_id)
    else: 
        try:
            ids = []
            # a user_id was passed in, fetch it and return a friends list
            if endpoint == 'friends':
                for page in tweepy.Cursor(api.friends_ids, id=user_id).pages():
                    ids.extend(page)
            elif endpoint == 'followers':
                for page in tweepy.Cursor(api.followers_ids, id=user_id).pages():
                    ids.extend(page)

            # put in something so that we know we've gone after this user
            if len(ids) == 0:
				__save_network(endpoint, user_id, None, 'No %s found' % endpoint)

            __save_network(endpoint, user_id, ids)
        except tweepy.TweepError, error: 
            __save_network(endpoint, user_id, None, error)
        
if __name__ == '__main__':
	ap = argparse.ArgumentParser()
	ap.add_argument("--tweet-id", required=False, help="Specify a Tweet ID of the user you are interested in")
	ap.add_argument("--screen-name", required=False, help="Screen name or user ID of twitter user")
	ap.add_argument("--input-file", required=False, help="Specify a dump file from ESBI")
	ap.add_argument("--batch", required=False, help="Try to fetch everything from DB in 100 tweet batches", action="store_true")
	ap.add_argument("--individual", required=False, help="Fetch tweets that have not been found, one at a time", action="store_true")
	ap.add_argument("--timelines", required=False, help="Fetch the timeslines of users", action="store_true")	
	ap.add_argument("--friends", required=False, help="Get all the friends of a user id", action="store_true")
	ap.add_argument("--followers", required=False, help="Get all the friends of a user id", action="store_true")	
	ap.add_argument("--bon", required=False, help="Get bot or not scores", action="store_true")
	args = vars(ap.parse_args())

	tweet_id = args['tweet_id']
	screenname = args['screen_name']
	input_filename = args['input_file']
	
	if input_filename:
		load_file(input_filename)

	if tweet_id: 
		tweet = api.get_status(tweet_id)
		__save_tweet(tweet_id, tweet)

	if args['batch']: 
		get_tweets_in_sample_batch()

	if args['individual']:
		# this will go back and fill in individual errors. The batch simply doesn't return errors
		get_tweets_in_sample()

	if args ['timelines']:
		get_timelines_batch()

	if args['friends']:
		get_friends()

	if args['followers']:
		get_followers()

	if args['bon']:
		get_botornot()
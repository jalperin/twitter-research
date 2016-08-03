# -*- coding: utf-8 -*-
# <nbformat>3.0</nbformat>

# <codecell>

import tweepy
import re
import json

import random

from time import sleep

import sqlite3 as lite

import datetime, time, os, sys
import argparse, ConfigParser
Config = ConfigParser.ConfigParser()
Config.read('config.cnf')

consumer_key = Config.get('twitterdissertation', 'consumer_key')
consumer_secret = Config.get('twitterdissertation', 'consumer_secret')
access_token = Config.get('twitterdissertation', 'access_token')
access_token_secret = Config.get('twitterdissertation', 'access_token_secret')

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
# set up access to the Twitter API
api = tweepy.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

# <codecell>

litecon = lite.connect('new_yorker_2.0.db')

# <codecell>

since_id = '652417479537479680' # first go at this new approach

try: 
	while True:
		mentions = api.mentions_timeline(count=200, since_id=since_id, include_rts=0)
		for i, m in enumerate(mentions):
		    tweet = api.get_status(id=m.id_str)
		    
		    with litecon:
		        litecur = litecon.cursor()        
		        try: 
			        litecur.execute('INSERT INTO response_data (user_id_str, tweet_id, time_received, tweet_text, tweet) VALUES (?,?,?,?,?)', (tweet.user.id_str, tweet.id_str, tweet.created_at, tweet.text, json.dumps(tweet._json)))
			        litecon.commit()
			    except lite.IntegrityError:
			    	# duplicates not a big deal, just not saving them is fine
			    	pass

		    if i == 0: 
		        since_id = m.id_str

		time.sleep(60*15) # once every fifteen minutes is enough

except KeyboardInterrupt, error:
    print "interrupted at since_id=" + str(since_id)
    raise 
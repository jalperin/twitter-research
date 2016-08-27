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

consumer_key = Config.get('twittersfupubresearch', 'consumer_key')
consumer_secret = Config.get('twittersfupubresearch', 'consumer_secret')
access_token = Config.get('twittersfupubresearch', 'access_token')
access_token_secret = Config.get('twittersfupubresearch', 'access_token_secret')

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
# set up access to the Twitter API
api2 = tweepy.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

def test_mentions():
    t = 'ah ah ah ah staying alive @sfupubresearch, staying alive %s %s' % ( datetime.datetime.now().isoformat(), ''.join([random.choice('abcdefghijklmnopqrstuvwxyz') for x in range(8)]))
    testtweet = api.update_status(t)

    print 'Testing mentions at: %s' % datetime.datetime.now().isoformat(), 
    sys.stdout.flush()
    for i in [1,2,3]:
        print '.'*i + ' ', 
        sys.stdout.flush()
        time.sleep(30*i)
        mentions = api2.mentions_timeline(count = 5)
        for mention in mentions: 
            if mention.id == testtweet.id:
                api.destroy_status(testtweet.id)
                print '%s was mentioned' % testtweet.id
                return True
    
    api.destroy_status(testtweet.id)
    print 
    print 'mentions not working as of %s' % datetime.datetime.now().isoformat()
    return False

litecon = lite.connect('new_yorker_2.0.db')

# <codecell>

variants = range(1,7) + range(13,19)
last_checked_mentions = datetime.datetime(1980, 5, 8) # some date in the past

with litecon:
    litecur = litecon.cursor()
    litecur.execute("SELECT DISTINCT td.user_id_str, td.screen_name, MIN(td.id_str) FROM tweet_data td LEFT JOIN question_data qd ON (td.user_id_str = qd.user_id_str) WHERE qd.variant IS NULL GROUP BY 1, 2 ORDER BY td.created_at")
    # this needs to run after harvester insert so archive_id is present
    users = litecur.fetchall()
    
    for i, user in enumerate(users): 
        #before we start, check mentions
        if (datetime.datetime.now() - last_checked_mentions > datetime.timedelta(hours=1)):
            while not test_mentions():
                time.sleep(60*60) # keep sleeping in 1 hour blocks until it works
            print 

        user_id_str = user[0]
        screen_name = user[1]
        tweet_id = user[2]

        variant = variants[i % len(variants)]

        tw = lead = question = prepend = append = ''

        if (variant <= 12):
            lead = "Please help us understand New Yorker readers."
        else:
            lead = "You recently tweeted a New Yorker article, could you tell us:"

        if (variant % 6 == 1 or variant % 6 == 2):
            question = "What format do you prefer to read it in?"
            altText = "What format do you prefer to read it in?"
            imageName = './A1.jpeg'

        elif (variant %6 == 3 or variant %6 == 4):
            question = "Do you read it primarily online?"
            altText = "Do you read it primarily online?"
            imageName = './A2.jpeg'

        elif (variant %6 == 5 or variant %6 == 0):
            question = "Do you read it online, in print, or both?"
            altText = "Do you read it online, in print, or both?"
            imageName = './A3.jpeg'

        if (variant %2 == 1):
            in_reply_to_status_id = tweet_id
            prepend = '@' + screen_name + ' '
            append = "Thanks!"

        else:
            in_reply_to_status_id = None
            append = "Thanks @" + screen_name + "!"

        if (variant % 12 <= 6 and variant % 12 > 0):
            tw = prepend + lead + " " + question + " " + append
        else:
            tw = prepend + lead + " " + append
            
    	try: 
            tweet = api.update_status(tw, in_reply_to_status_id)

            litecur.execute("INSERT INTO question_data (user_id_str, time_sent, variant, tweet_id) VALUES (?,?,?,?)", (user_id_str, datetime.datetime.now().isoformat(), variant, tweet.id_str))
            litecon.commit()

        except tweepy.TweepError, error: 
            print error
            print user_id_str, screen_name
            raise

        time.sleep(random.randrange(5*60,7*60))
        if datetime.datetime.now().hour == 2:
            # even bots go to bed
            api.update_status('Goodnight @juancommander. %s' % datetime.datetime.now().isoformat())
            time.sleep(60*60*6)
        

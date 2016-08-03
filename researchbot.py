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

variants = range(1,7) + range(13,19)

with litecon:
    litecur = litecon.cursor()
    litecur.execute("SELECT DISTINCT td.user_id_str, td.screen_name, td.id_str FROM tweet_data td LEFT JOIN question_data qd ON (td.user_id_str = qd.user_id_str) WHERE qd.variant IS NULL ORDER BY td.created_at")
    # this needs to run after harvester insert so archive_id is present
    users = litecur.fetchall()
    
    for i, user in enumerate(users): 
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

        time.sleep(random.randrange(4*60,6*60))
        
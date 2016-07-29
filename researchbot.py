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

with litecon:
    litecur = litecon.cursor()
    litecur.execute("SELECT DISTINCT td.user_id_str, td.screen_name FROM tweet_data td LEFT JOIN question_data qd ON (td.user_id_str = qd.user_id_str) WHERE qd.variant IS NULL ORDER BY td.created_at;")
    # this needs to run after harvester insert so archive_id is present
    users = litecur.fetchall()
    
    for user in users: 
        user_id_str = user[0]
        screen_name = user[1]
        
        time.sleep(random.randrange(9*60,11*60))
        
        tweet = api.update_status("This is research by @juancommander: Would you tell us, do you prefer to read the New Yorker online or in print?\n\nThanks @%s!" % screen_name);

        litecur.execute("INSERT INTO question_data (user_id_str, time_sent, variant, tweet_id) VALUES (?,?,?,?)", (user_id_str, datetime.datetime.now().isoformat(), -1, tweet.id_str))


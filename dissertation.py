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

with open('tweetabledissertation.md') as f:
    diss=f.read().strip().decode('utf8')


import nltk.data
from nltk import word_tokenize
sent_detector = nltk.data.load('tokenizers/punkt/english.pickle')

# <codecell>

diss_sent = sent_detector.tokenize(diss)

# <codecell>

#tw = "The Public Impact of Latin America's Approach to Open Access, by Juan Pablo Alperin"
#api.update_status(tw)

# <codecell>

i = 518 
try: 
    for sent in diss_sent[i:]: 
        sent = sent.strip().encode('utf8')
        tw = ''
        for token in sent.split(' '): 
            if len(token) >= 140: continue

            if len("%s %s" % (tw, token)) < 140:
                tw = "%s %s" % (tw, token)
            elif len(tw) < 140:
                try: 
                    time.sleep(random.randrange(2*60,4*60))
                    api.update_status(tw)
                except tweepy.TweepError, error:
                    print error
                    print "at sentence: %s" % i
                tw = token
            else:
                print "should not happen"
                print tw
                print token
                tw = token
      
        i = i + 1
        try:
            if len(tw) < 140: 
                time.sleep(random.randrange(2*60,4*60))
                api.update_status(tw)
        except tweepy.TweepError, error:
            print error
            print "at sentence (end of loop): %s" % i

except KeyboardInterrupt, error:
    print "interrupted at: " + str(i)
    raise 
    
            


# coding: utf-8

# In[2]:


import tweepy
import re
import json

import sqlite3 as lite

import pandas as pd

import datetime, time, os, sys
import argparse, configparser
Config = configparser.ConfigParser()
Config.read('config.cnf')

consumer_key = Config.get('twittersfupubresearch', 'consumer_key')
consumer_secret = Config.get('twittersfupubresearch', 'consumer_secret')
access_token = Config.get('twittersfupubresearch', 'access_token')
access_token_secret = Config.get('twittersfupubresearch', 'access_token_secret')

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
# set up access to the Twitter API
api = tweepy.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)


# In[24]:


litecon = lite.connect('data/swcc.db')

with litecon:

# set up SQL tables
    litecur = litecon.cursor()
    # the users that were found
    litecur.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT, screen_name TEXT, user_object TEXT, fetch_followers TEXT, error TEXT, user_modified TEXT)")
    litecur.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_user_id ON users (user_id)")
    litecur.execute("CREATE INDEX IF NOT EXISTS users_screen_name ON users (screen_name)")    

    litecur.execute("CREATE TABLE IF NOT EXISTS followers (user_id TEXT, follower_id TEXT, modified TEXT)")
    litecur.execute("CREATE INDEX IF NOT EXISTS followers_user_id ON followers (user_id)")
    litecur.execute("CREATE UNIQUE INDEX IF NOT EXISTS followers_user_follower_id ON followers (user_id, follower_id)")


# In[25]:


def get_missing_users():
    df = pd.read_excel('data/swcc-twitter.xlsx')
    seed_data = set(df['ID-Author'].str.lower())
    del df

    with litecon:
    # set up SQL tables
        litecur = litecon.cursor()
        cur = litecur.execute("SELECT screen_name FROM users")
        fetched = cur.fetchall()
        fetched = [x[0].lower() for x in fetched]

    ret = seed_data.difference(fetched)
    print("%s remaining" % len(ret))
    return ret


# In[ ]:


def __insert_user(user, fetch_followers = 0):
    now = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    with litecon:
        litecur = litecon.cursor()
        try:
            litecur.execute('INSERT INTO users (user_id, screen_name, user_object, fetch_followers, user_modified) VALUES (?, ?, ?, ?, ?)', (user.id, user.screen_name, json.dumps(user._json), fetch_followers, now))
        except lite.IntegrityError:
            # don't worry about duplicates
            pass
        
def __insert_user_error(error, user_id = None, screen_name = None):
    now = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    with litecon:
        litecur = litecon.cursor()
        try:
            litecur.execute('INSERT INTO users (user_id, screen_name, error, user_modified) VALUES (?, ?, ?, ?)', (user_id, screen_name, error, now))
        except lite.IntegrityError:
            # don't worry about duplicates
            pass

def get_user(user_id):
    try:
        user = api.get_user(user_id)
        __insert_user(user, fetch_followers=1)
    except tweepy.TweepError as error:
        __insert_user_error(error.response.reason, user_id=None, screen_name=screen_name)

for screen_name in get_missing_users():
    get_user(screen_name)



# In[31]:


def __save_followers(user_id, ids):
    '''
    Do the actual SQLite update with the info collected
    '''
    now = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    with litecon:
        litecur = litecon.cursor()
        
        print( 'saving', len(ids))
        for f in ids:
            try: 
                litecur.execute('INSERT INTO followers (user_id, follower_id, modified) VALUES (?, ?, ?)', (user_id, f, now))
            except lite.IntegrityError:
                pass # ignore duplicates, they wont change the network
            
def __save_follower_error(user_id):
    now = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    with litecon:
        litecur = litecon.cursor() 
    litecur.execute('INSERT INTO followers (user_id, follower_id, modified) VALUES (?, ?, ?)', (user_id, -1, now))
    
    
def get_followers(user_id = None):
    '''
    Get the followers list for all users (or for a specific user)
    '''
    if user_id is None:       
        while (True):
            with litecon:
                litecur = litecon.cursor()
                litecur.execute('SELECT u.user_id FROM users u LEFT JOIN followers f ON (u.user_id = f.user_id) WHERE f.user_id IS NULL and fetch_followers = 1')
        
            # go 100 at a time so we're not hitting the DB so much
            users = [u[0] for u in litecur.fetchmany(100)]
            if not users: break

            for user_id in users:
                ids = get_followers(user_id)
    else: 
        try:
            ids = []
            for page in tweepy.Cursor(api.followers_ids, id=user_id).pages():
                ids.extend(page)

            if len(ids) > 0: 
                __save_followers(user_id, ids)
            else:
                __save_follower_error(user_id)

        except tweepy.TweepError as error: 
            pass

get_followers()


# In[ ]:


def get_users_of_followers():
    while (True):
        with litecon:
            litecur = litecon.cursor()
            litecur.execute('SELECT f.follower_id FROM followers f LEFT JOIN users u ON (f.follower_id = u.user_id) WHERE u.user_id IS NULL')

        # go 100 at a time so we're not hitting the DB so much
        users = [u[0] for u in litecur.fetchmany(100)]
        if not users: break

        for user_id in users:
            get_user(user_id)



# coding: utf-8

# In[1]:

import numpy as np
import os
import pandas as pd
pd.options.display.float_format = '{:20,.4f}'.format

import sqlite3

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

import json
import re

import igraph as ig

import itertools 

from datetime import datetime 
import pytz
import time

import gc

import warnings
warnings.filterwarnings('ignore')

load_from_scratch = True

# In[2]:

cons = {}
cons['evolBio'] = sqlite3.connect("data/BMCevolBioSample.db")
cons['bio'] = sqlite3.connect("data/BMCbioSample.db")
cons['bmc'] = sqlite3.connect("data/bmcTwitter.db")
cons['comm'] = sqlite3.connect("data/communications.db")
cons['pundit'] = sqlite3.connect("data/pundits.db")

dataset = 'pundit'


# In[23]:
def load_tweet_details(con = None, min_nodes=None):
    df = pd.read_sql("SELECT doi, tweet_id, old_screen_name, tweet FROM sample WHERE tweet IS NOT NULL ", con, index_col='tweet_id')
    df = df[~df.tweet.isnull()]
    df['tweet'] = df.tweet.apply(lambda x: json.loads(x) if x is not None else None)
    
    df['created_at'] = df.tweet.apply(lambda x: time.strftime('%Y-%m-%d %H:%M:%S', time.strptime(x['created_at'],'%a %b %d %H:%M:%S +0000 %Y')))
    df['created_at'] = pd.to_datetime(df.created_at)
    df['created_at_dayofweek'] = df.tweet.apply(lambda x: x['created_at'][0:3])
    df['screen_name'] = df.tweet.apply(lambda x: x['user']['screen_name'])
    df['user_id'] = df.tweet.apply(lambda x: int(x['user']['id_str']))
    df['user_utc_offset'] = df.tweet.apply(lambda x: x['user']['utc_offset'])
    df['user_followers_count'] = df.tweet.apply(lambda x: x['user']['followers_count'])
    df['user_friends_count'] = df.tweet.apply(lambda x: x['user']['friends_count'])
    df['user_description'] = df.tweet.apply(lambda x: re.sub( '\s+', ' ', x['user']['description']).strip())
    df['is_retweet'] = df.tweet.apply(lambda x: 'retweeted_status' in x)
    df['is_retweet'] = df['is_retweet'].fillna(False)
    df['retweet_of_status_id_str'] = df.tweet.apply(lambda x: x['retweeted_status']['id_str'] if 'retweeted_status' in x else None)
    df['retweet_of_screen_name'] = df.tweet.apply(lambda x: x['retweeted_status']['user']['screen_name'] if 'retweeted_status' in x else None)
    df['is_reply'] = df.tweet.apply(lambda x: x['in_reply_to_status_id'] != None)
    df['in_reply_to_status_id_str'] = df.tweet.apply(lambda x: x['in_reply_to_status_id_str'])
    df['in_reply_to_screen_name'] = df.tweet.apply(lambda x: x['in_reply_to_screen_name'])
    df['text'] = df.tweet.apply(lambda x: re.sub( '\s+', ' ', x['text']).strip()) # remove commas for CSV simplicity
    del df['tweet']
    tweetdetails = df.sort_index()
    del df

    df = pd.read_sql("SELECT doi, tweet_id, old_screen_name, tweet FROM sample WHERE error LIKE '%screen_name%'", con, index_col='old_screen_name')
    users_df = pd.read_sql("SELECT user_id, screen_name FROM users", con, index_col = 'screen_name')
    users_df['user_id'] = users_df.user_id.astype(int)
    df = df.join(users_df, how="inner")
    df.index.name = 'screen_name'
    
    tweetdetails = tweetdetails.append(df.set_index('tweet_id', drop=False)).sort_index()
    del df
    del users_df

    if min_nodes: 
        tweetdetails = tweetdetails.groupby('doi').filter(lambda row: len(set(row['user_id'])) > min_nodes)
    return tweetdetails


def load_graphs(con, tweetdetails = None, min_nodes = None):
    try: 
        dois = list(tweetdetails.doi.unique())
    except: 
        tweetdetails = load_tweet_details(con, min_nodes)
        dois = list(tweetdetails.doi.unique())
        
    friends = pd.read_sql_query("SELECT * FROM friends", con, index_col="user_id")
    friends.index = friends.index.astype(int)
    friends.friend_id = friends.friend_id.astype(int) 
    
    followers = pd.read_sql_query("SELECT * FROM followers", con, index_col="user_id")
    followers.index = followers.index.astype(int)
    followers.follower_id = followers.follower_id.astype(int)
    
    # join the list of users with the friends to construct a one-way edge list
    df = tweetdetails[['doi', 'user_id']].drop_duplicates().set_index('user_id').join(friends)[['friend_id', 'doi']]
    df = df[df.friend_id.notnull()]
    df.friend_id = df.friend_id.astype(int)
    df = df.reset_index()
    df.columns = ['in', 'out', 'doi']
    
    # do the same thing for the followers 
    df2 = tweetdetails[['doi', 'user_id']].drop_duplicates().set_index('user_id').join(followers)[['follower_id', 'doi']]
    df2 = df2[df2.follower_id.notnull()]
    df2.follower_id = df2.follower_id.astype(int)
    df2 = df2.reset_index()
    df2.columns = ['out', 'in', 'doi']
    
    edgelist = df.append(df2).set_index('in').reset_index()
    edgelist = edgelist.drop_duplicates()

    graphs = {}
    for doi in dois: 
        e = edgelist[edgelist.doi == doi]
        if len(e) == 0: 
            continue
        del e['doi']
        
        filename = 'data/%s/%s-edgelist.csv' % (dataset, doi.replace('/','_'))
        e.columns = ['Source', 'Target']
        e.to_csv(filename, index=False, sep="\t", header=None) # this is just for reading again
        
        graphs[doi] = ig.Graph.Read_Ncol(filename, names=True, directed=True)
        e.to_csv(filename, index=False)
    
    del edgelist
    del friends
    del followers
    del df
    gc.collect()
    
    return graphs

tweetdetails = load_tweet_details(cons[dataset])
tweetdetails.to_csv('data/%s/tweetDetailsAll.csv' % dataset, encoding='utf8')

def timedelta_to_days(td):
    return td.days + td.seconds/3600.0/24

def median_timestamp(x):
    ts = list(map(lambda t: t.value/1000000000, x))
    return datetime.fromtimestamp(int(np.median(ts)), tz=pytz.utc).replace(tzinfo=None)

def lifespan(x):
    return timedelta_to_days(x.max()-x.min())

def halflife(x):
    return timedelta_to_days(median_timestamp(x)-x.min())

tweet_stats = tweetdetails[~tweetdetails.created_at.isnull()].groupby('doi').agg({'created_at': [np.min, lifespan, median_timestamp, halflife], 
                               'is_retweet': [np.size, np.sum, lambda x: 100.0*x.sum()/len(x)]})
tweet_stats.columns = ['created_at', 'tweet_lifespan', 'median_tweettime', 'tweet_halflife', 'tweets', 'retweets', 'retweets_p']


if load_from_scratch: 
    graphs = load_graphs(cons[dataset], tweetdetails)
    print (len(graphs), len(tweetdetails))
else: 
    dois = tweetdetails.doi.unique()
    
    graphs = {}
    for doi in dois: 
        filename = 'data/%s/%s-edgelist.csv' % (dataset, doi.replace('/','_'))
        e = pd.read_csv(filename)
        e.to_csv('data/tmp.tsv', index=False, sep="\t", header=None) # this is just for reading again

        graphs[doi] = ig.Graph.Read_Ncol('data/tmp.tsv', names=True, directed=True)

print (len(graphs), len(tweetdetails))

dois = graphs.keys()

subgraphs = {}

calculate_shortest = True

graph_stats = {}
shortest_paths = {}

for i, doi in enumerate(dois):
    tweets = tweetdetails[tweetdetails.doi == doi]
    tweets['event_number'] = tweets.index.map(lambda x: tweets.index.get_loc(x))
    tweets['user_id_str'] = tweets.user_id.astype(str)
    del tweets['user_id'] # delete to avoid confusion: probably should just use numeric throughout

    tweeters = tweetdetails[tweetdetails.doi == doi].user_id.unique().astype(str)

    # temporary for testing, make sure all tweeters are in the graph
    G = graphs[doi]
    for t in tweeters:
        if t not in [v['name'] for v in G.vs]:
            G.add_vertex(t)
    # end temporary
        
    G = graphs[doi].subgraph(tweeters)
    subgraphs[doi] = G
    print("%s\t%s\t%s" % (doi, G.vcount(), G.ecount()))
    
    graph_stats[doi] = {}
    graph_stats[doi]['density'] = G.density()
    graph_stats[doi]['num_nodes'] = G.vcount()
    graph_stats[doi]['num_edges'] = G.ecount()
    graph_stats[doi]['diameter'] = G.diameter()
    
    graph_stats[doi]['in_degree_mean'] = np.mean(G.indegree())
    graph_stats[doi]['out_degree_mean'] = np.mean(G.outdegree())
    graph_stats[doi]['degree_mean'] = np.mean(G.degree())
    
    wccs = sorted(G.components(mode=ig.WEAK).subgraphs(), key=lambda g: g.vcount(), reverse=True)
    graph_stats[doi]['biggest_wcc_num_nodes'] = wccs[0].vcount()
    graph_stats[doi]['biggest_wcc_num_nodes_p'] = wccs[0].vcount()*100.0/G.vcount()
    graph_stats[doi]['biggest_wcc_density'] = wccs[0].density()
    graph_stats[doi]['biggest_wcc_infomap_modularity'] = wccs[0].community_infomap().modularity
  
    if G.ecount() == 0:
        continue

    paths = G.shortest_paths(mode=ig.ALL)
    graph_stats[doi]['shortest_paths_mean'] = np.mean([item if item != np.inf else 0 for sublist in paths for item in sublist ])
    graph_stats[doi]['shortest_paths_median'] = np.median([item if item != np.inf else 0 for sublist in paths for item in sublist ])
    graph_stats[doi]['infomap_modularity'] = G.community_infomap().modularity
    
    filename = 'data/%s/%s-subgraph-edgelist.csv' % (dataset, doi.replace('/','_'))
    G.write_ncol(filename)
    df = pd.read_csv(filename, sep=" ", header=None)
    df.columns = ['Source', 'Target']
    df.to_csv(filename, index=False)

    if calculate_shortest: 
        path_lengths = []   
    
        # double check that order is preserved with .unique
        exposure_paths = []
        for t, f in itertools.combinations(tweets.user_id_str.unique(), 2):
            paths = G.get_shortest_paths(t, f, mode=ig.IN)
            
            # handle case where more than one path is returned
            if len(paths) > 0 and len(paths[0]) > 0:
                exposure_paths.append(paths[0])
                path_lengths.append(len(paths[0]))
    #         paths = G.get_shortest_paths(f, t, mode=ig.IN)
    #         path_lengths.append(len(paths[0]))

        shortest_paths[doi] = exposure_paths
    
        graph_stats[doi]['shortest_exposure_path_length_mean'] = np.mean(path_lengths)
        graph_stats[doi]['shortest_exposure_path_length_median'] = np.median(path_lengths)
        
        subG = G
        tweeters = {}
        for v in subG.vs():
            tweeters[v.index] = {}
            tweeters[v.index]['name'] = v['name']
            tweeters[v.index]['event_number'] = tweets[tweets.user_id_str == v['name']].event_number.min()
        
        edges = set()
        for p in exposure_paths:
            for v_index in range(len(p)-1):
                edges.add((p[v_index], p[v_index+1]))
        
        G = ig.Graph(directed=True)
        G.add_vertices([tweeters[v_index]['name'] for v_index in range(subG.vcount())])
        for v_index in range(subG.vcount()):
            G.vs[v_index]['event_number'] = tweeters[v_index]['event_number']
            
        for e in edges: 
            G.add_edge(e[0], e[1])

#     ax = axes[plot_map[i][0],plot_map[i][1]]
#     ax.set_title(doi)
#     pd.Series(path_lengths).plot.hist(xlim=[0,10], bins=range(-1,10), ax=ax)

graph_stats = pd.DataFrame.from_dict(graph_stats, orient='index')
graph_stats.index.name = 'doi'

graph_stats.to_csv('data/%s/graph_stats.csv' % dataset)

all_stats = graph_stats.join(tweet_stats)
all_stats.to_csv('data/%s/all_stats.csv' % dataset)

plt.rcParams['figure.figsize'] = (10,10)

print('Finished successfully!')

df = pd.DataFrame(all_stats, columns=['num_nodes', 'biggest_wcc_num_nodes_p', 'shortest_paths_mean', 'shortest_exposure_path_length_mean', 'density', 'retweets_p', 'tweet_lifespan', 'tweet_halflife', 'biggest_wcc_infomap_modularity'])
pd.tools.plotting.scatter_matrix(df, s=150, diagonal='hist')

plt.tight_layout()
plt.savefig('data/%s/scatterplot.png' % dataset)

sns.set(style="white")
sns.set(style="ticks", color_codes=True)


# and now the fancy version

df = all_stats[['num_nodes', 'biggest_wcc_num_nodes_p', 'shortest_paths_mean', 'shortest_exposure_path_length_mean', 'density', 'retweets_p', 'tweet_lifespan', 'tweet_halflife', 'biggest_wcc_infomap_modularity']]

g = sns.PairGrid(df, diag_sharey=False)
g.map_lower(sns.kdeplot, cmap="Blues_d")
g.map_upper(plt.scatter)
g.map_diag(sns.kdeplot, lw=3)

def corrfunc(x, y, **kws):
#     _, _, r_value, p_value, _ = stats.linregress(x, y)
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    ax = plt.gca()
    ax.plot(x, intercept + slope*x, 'r')
    ax.annotate("R-sq = {:.2f}".format(r_value**2),
                xy=(.68, .1), xycoords=ax.transAxes)

g.map_upper(corrfunc)

plt.savefig('data/%s/scatterplot_kde.png' % dataset)


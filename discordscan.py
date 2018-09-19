#!/usr/bin/env python3
from urllib.request import urlopen
from urllib.request import Request
from urllib.error import HTTPError
from bs4 import BeautifulSoup

import requests
import time
import praw
import json
import os.path

# MISC functions
def expo_backoff(tries):
    #sleep_time = 3600 ** tries #3600 = 1hr
    # ** = eponential; seems extremely unneeded
    # To solve the issue, changing from exponential to a smaller,
    # multiplicative-exponential backoff with 3-hour limiter.
    #if tries <= 8:
    #    sleep_time = 30 * (2 ** tries) #30 = 30sec; 30*(2**8)=128min=2.13hr
    #else:
    #    sleep_time = 10800 #10800 = 3hr
    sleep_time = 60 * tries
    print('Sleeping for', sleep_time, 'seconds')
    time.sleep(sleep_time)

redir_codes = [ 301, 302, 303, 307, 308 ]
def check_code(code, tries=1):
    req = Request('https://discordapp.com/api/invites/{0}'.format(code))
    req.add_header('Accept', 'application/json')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    req.add_header('User-Agent', 'python urllib3 reddit u/tjstretchalot')

    try:
        with urlopen(req) as res:
            serverData = json.loads(res.read().decode('utf-8')) # Convert bytes to string
            return True, serverData # Return success and server JSON
    except HTTPError as err:
        if err.code == 404:
            return False, False
        else:
            print('Got error code {0} in HTTPResponse for code {1}'.format(err.code, code))
            if tries <= 3:
                expo_backoff(tries)
            else:
                # Somehow break to the next post? Calls at 103, 130
                return True, False # Act as if code is valid, but no server data
            return check_code(code, tries + 1), False

def is_official_link(link):
    return (link.startswith('http://discord.gg')
        or link.startswith('https://discord.gg')
        or link.startswith('http://discordapp.com')
        or link.startswith('https://discordapp.com'))

def get_code_from_official_link(link):
    if link.endswith('/'): # Remove trailing slash from Django-prep (Discord.st)
        link = link[:-1]
    return link.rsplit('/', 1)[-1]

def safe_requests_get(link, tries=1):
    try:
        response = requests.get(link, allow_redirects=False, timeout=10)
        return response
    except ConnectionError as ce:
        print('Got a connection error on redirect link:')
        print(ce)
        expo_backoff(tries)
        return safe_requests_get(link, tries + 1)
    except requests.exceptions.ReadTimeout as rte:
        print('Got a read timeout on redirect link:')
        print(rte)
        expo_backoff(tries)
        return safe_requests_get(link, tries + 1)

# Returns is_redirect, new_url
def get_response_redirect(response):
    if response.status_code in redir_codes:
        print(response.url, 'uses', response.status_code, '->', response.headers['Location'])
        return True, response.headers['Location']

    soup = BeautifulSoup(response.text, 'html5lib')

    metas = soup.find_all('meta')

    for meta in metas:
        if ('property' in meta.attrs and meta.attrs['property'] == 'refresh') or ('http-equiv' in meta.attrs and meta.attrs['http-equiv'] == 'refresh'):
            content = meta.attrs['content']
            url = content.split(';')[1][4:]
            if url.startswith('='): # Fix more messy Django crap (Discord.st)
                url = url[1:]
            print(response.url, 'uses meta property ->', url)
            return True, url

    return False, None

# Returns is_valid, redirects_to_official
def check_redirect_link(link, max_redirects=5, tries=1):    
    response = safe_requests_get(link)

    num_redirects = 0
    succ, newurl = get_response_redirect(response)
    while succ:
        if is_official_link(newurl):
            code = get_code_from_official_link(newurl)
            codeCheck, serverData = check_code(code)
            return codeCheck, serverData
        else:
            num_redirects += 1
            if num_redirects > max_redirects:
                return False, False

            response = safe_requests_get(newurl)
            succ, newurl = get_response_redirect(response)

    return False, False

def is_whitelisted_redir(url):
    return (url.startswith('http://discord.plus')
        or url.startswith('https://discord.plus')
        or url.startswith('http://discord.me')
        or url.startswith('https://discord.me')
        or url.startswith('http://discord.st')
        or url.startswith('https://discord.st'))

def should_check_subm(subm):
    if subm.is_self or subm.banned_by is not None:
        return False
    return is_official_link(subm.url) or is_whitelisted_redir(subm.url)

def should_delete_subm(subm):
    url = subm.url

    if is_official_link(url):
        response, serverData = check_code(get_code_from_official_link(url))
        return response, serverData

    is_valid_code, serverData = check_redirect_link(url)
    return is_valid_code, serverData

def handle_subm(submission):
    print('Checking submission id =', submission.id, ' url =', submission.url)

    if not should_check_subm(submission):
        print('Ignoring')
        return

    # Ensure trailing slash for Django (Discord.st)
    if not submission.url.endswith('/'):
        submission.url += '/'
        
    codeCheck, serverData = should_delete_subm(submission)
    
    if not codeCheck:
        print('Link is not valid or is expired. Replying...')
        comment = submission.reply(response_message)
        comment.mod.distinguish()
        print('Done replying, removing')
        submission.mod.remove(spam=False)
        print('Done removing')
    else:
        print('Valid')
        if serverData:
            # Check if server has features (Discord partner?)
            if serverData['code'] != "10006":
                if 'VIP_REGIONS' in serverData['guild']['features']:
                    print('This server has features!')
                    if (submission.link_flair_text != 'Discord Partner'
                    or submission.link_flair_css_class != 'partner-post'):
                        submission.flair.select('3c0343d0-3daa-11e6-b5ea-0e43c84e73c3')
                        print('Flaired post as Discord Partner!')
                    else:
                        print('Post already has flair.')
                elif serverData['guild']['id'] in blacklist:
                    print('Server is blacklisted! Sending modmail...')
                    modMessage = '''The user u/{0} tried making [this post](https://www.reddit.com/r/discordservers/comments/{1}) for the banned server **{2}** ^(Server ID: {3}) in DiscordServers and was just caught by the bot.'''.format(str(submission.author),submission.id,serverData['guild']['name'],serverData['guild']['id'])
                    subreddit.modmail.create('Blacklisted server attempting to post!', modMessage, 'SubredditGuardian')
                    print('Done sending, removing')
                    submission.mod.remove(spam=False)
                    print('Done removing')
            else:
                print('Link just expired? Replying...')
                comment = submission.reply(response_message)
                comment.mod.distinguish()
                print('Done replying, removing')
                submission.mod.remove(spam=False)
                print('Done removing')


# CONFIGURATION (except authentication)
subreddit_name = 'DiscordServers'
database_file = 'discordlinktester.flatdb'
response_message = '''Your invite link has expired at r/DiscordServers.  
This means either you did not generate a permanent invite link, or you have closed the server.  
You're welcome to post your server again provided it is a [permanent link](https://support.discordapp.com/hc/en-us/articles/208866998-Instant-Invite-101).

If you think this bot has made a mistake, please contact us [here](https://www.reddit.com/message/compose?to=%2Fr%2Fdiscordservers).

Sincerely,  
The r/DiscordServers Team'''

loop_sleep_time_seconds = 30
check_sleep_time_seconds = 5
loops_per_hot_check = 10

# how many of the most recent posts do we check every loop?
# this number needs to bigger than your peak posts per loop.
# a loop worst case about:
# (loop_sleep_time_seconds
#   + check_sleep_time_seconds * max_posts_until_miss_in_new) +
# (loop_sleep_time_seconds
#   + check_sleep_time_seconds * num_hot_posts_to_rescan)
# seconds.
#
# if
#loop_sleep_time_seconds = 30
#check_sleep_time_seconds = 5
#loops_per_hot_check = 10
#max_posts_until_miss_in_new = 10
#num_hot_posts_to_rescan = 100
# then
# (30 + 5 * 10) + (30 + 5 * 100) = 80 + 530 = 610 seconds/slowest loop
# (610 seconds / slowest loop) * (1 loop / 10 posts) = 61 seconds/post
# at peak
# max 1000
max_posts_until_miss_in_new = 100

# how many hot posts we ensure are valid. Posts after this in hot
# may become invalid without the bot noticing. max 1000.
num_hot_posts_to_rescan = 1000

# AUTHENTICATION
print('Logging in')
reddit = praw.Reddit(client_id='',
                     client_secret='',
                     password='',
                     user_agent='DiscordServers bot by /u/tjstretchalot',
                     username='')

# ACTUAL BOT STUFF
subreddit = reddit.subreddit(subreddit_name)
recently_checked_subm_ids = []
hot_check_counter = 0

while True:
    # CHECK SUBREDDIT FLAIRS BEFORE STARTING
    #for template in subreddit.flair.link_templates:
    #    print(template)
    
    # Get the file containing blacklist
    print('Loading blacklist...');
    blacklist = []
    try:
        filePath = os.path.dirname(os.path.realpath(__file__)) + "/blacklist.txt"
        with open(filePath) as theList:
            for line in theList:
                listItem = line.split(',')[0].rstrip('\n')
                blacklist.append(listItem)
            print('Blacklist loaded.');
    except:
        print('Unable to load blacklist!');
    
    print('======= Scanning new... =======')
    just_checked = []
    for submission in subreddit.new(limit=max_posts_until_miss_in_new):
        just_checked.append(submission.id)
        if submission.id in recently_checked_subm_ids:
            continue
        handle_subm(submission)
        print('Sleeping for', check_sleep_time_seconds, 'seconds')
        time.sleep(check_sleep_time_seconds)

    recently_checked_subm_ids = just_checked
    print('Sleeping for 30 seconds')
    time.sleep(loop_sleep_time_seconds)

    if hot_check_counter <= 0:
        hot_check_counter = loops_per_hot_check

        print('============== Scanning hot... ==============')
        for submission in subreddit.hot(limit=num_hot_posts_to_rescan):
            handle_subm(submission)
            print('Sleeping for', check_sleep_time_seconds, 'seconds')
            time.sleep(check_sleep_time_seconds)
        print('Sleeping for', loop_sleep_time_seconds, 'seconds')
        time.sleep(loop_sleep_time_seconds)
    else:
        hot_check_counter -= 1
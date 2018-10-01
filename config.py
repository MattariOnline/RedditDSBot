import os

subreddit_name = 'DiscordServers'
response_message = '''Your invite link has expired at r/DiscordServers.
This means either you did not generate a permanent invite link or you have likely closed the server.
*Note: if you use discord.me for your server links, we do not support their bot-check service for obvious reasons.*

You're welcome to post your server again provided it is a [permanent link](https://support.discordapp.com/hc/en-us/articles/208866998-Instant-Invite-101).

If you think this bot has made a mistake, please contact us [here](https://www.reddit.com/message/compose?to=%2Fr%2Fdiscordservers).

Sincerely,
The r/DiscordServers Team'''

too_soon_response_message = '''You made [this post]({perma_link_new}) for your server before the wait period was up.

The post post for your server can be found [here]({perma_link_old}).

**Time you still need to wait before you can post again: {time_left}**

If you are certain this bot has made a mistake, and not due to reddit's time estimation, please contact us [here](https://www.reddit.com/message/compose?to=%2Fr%2Fdiscordservers).

Sincerely,
The r/DiscordServers Team'''

loop_sleep_time_seconds = 30
check_sleep_time_seconds = 5
loops_per_hot_check = 10
flair_id = '3c0343d0-3daa-11e6-b5ea-0e43c84e73c3'

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

# The time in seconds we wait before we verify a link is still working
post_update_time_seconds = 60 * 15

min_time_between_posts_seconds = 60 * 60 * 24

# DATABASE RELATED STUFF
database_file = os.path.join(os.path.dirname(__file__), 'discordservers.db')
database_prune_period_seconds = 60 * 60

# MISC
dry_run = False

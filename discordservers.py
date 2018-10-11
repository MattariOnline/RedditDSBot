#!/usr/bin/env python3.6

"""Main entrance to discord scan"""

import discord
import redirects
import retry
import config
from stringlist import StringList
import time
import praw
import string # for variable "print_safe_name"
import database
import math
from datetime import timedelta
import re

try:
    import auth_config
except ModuleNotFoundError as e:
    print('You must create a file \'auth_config.py\' with the values client_id, client_secret, password, and username')
    raise e

def is_official_link(link):
    """Determine if the given link is official.

    Verifies if the given string url is a link to discord.

    Args:
        link: A string link

    Returns:
        True if the link is a link to discord, False otherwise.
    """

    return (link.startswith('http://discord.gg')
        or link.startswith('https://discord.gg')
        or link.startswith('http://discordapp.com')
        or link.startswith('https://discordapp.com'))

def get_code_from_official_link(link):
    """Finds the code for the official invite link.

    Args:
        link: A string url that corresponds with a discord invite link.

    Returns:
        The string code that the invite link uses.
    """

    if link.endswith('/'):
        return link.rsplit('/', 2)[-2]

    return link.rsplit('/', 1)[-1]

def is_whitelisted_redir(link):
    """Determines if the given link is a whitelisted redirector.

    Args:
        link: A string url

    Returns:
        True if the url is a whitelisted redirector, False otherwise.
    """

    return (link.startswith('http://discord.plus')
        or link.startswith('https://discord.plus')
        or (link.startswith('http://discord.me') and not link.startswith('http://discord.me/password/'))
        or (link.startswith('https://discord.me') and not link.startswith('https://discord.me/password/'))
        or link.startswith('http://discord.st')
        or link.startswith('https://discord.st'))

def is_discord_or_discord_redirect_link(link):
    """Determines if the given link is either discord or redirect to discord.

    This does not actually fetch the link or follow the redirects.

    Args:
        link: A string url

    Returns:
        True if the url is a discord link or a redirect to one, False otherwise
    """

    return is_official_link(link) or is_whitelisted_redir(link)

def follow_redir_link(link):
    """Follows the redirect link until we reach the official discord link.

    This will retry forever.

    Args:
        link: A string url

    Returns:
        The string url that the original link points to.
    """

    cur_url = link
    def try_follow_redirect():
        nonlocal cur_url

        result = None
        try:
            result = redirects.follow(cur_url, is_whitelisted_redir)
        except redirects.RedirectError as re:
            cur_url = re.url if re.url else cur_url
            raise re

        return True, result

    return retry.until_success(try_follow_redirect)

def get_invite_from_code(code):
    """Get the discord invite from the code.

    This will retry unless we don't think retrying will help.

    Args:
        code: The string discord invite code

    Returns:
        The discord invite object (see discord.py)
    """

    def try_get_invite_from_code():
        nonlocal code

        succ, retry, result = discord.get_invite_from_code(code)
        if succ:
            return True, result

        return not retry, None

    return retry.until_success(try_get_invite_from_code)

def reply_and_delete_submission(subm, msg = None, indent = '   '):
    """Responds with the default message, distinguishes response, and deletes

    This is the correct course of action for a link to an invalid discord channel,
    or a link to a redirector that does not lead to a valid discord channel.

    Args:
        subm: The praw.models.reddit.Submission object
        msg: The string message to reply with, or None for config.response_message
        indent: The indent to use for logging, defaults to 4 spaces
    """

    if msg is None:
        if (subm.url.startswith('http://discord.me') or subm.url.startswith('https://discord.me')):
            msg = config.response_message_botcheck
        else:
            msg = config.response_message

    if config.dry_run:
        print(f'{indent}Would reply and remove, but dry-run is set. Waiting 2 seconds instead')
        time.sleep(2)
        return

    comment = submission.reply(msg)
    comment.mod.distinguish()
    print(f'{indent}Done replying, removing')
    submission.mod.remove(spam=False)
    print(f'{indent}Done removing')

def make_printable(str):
    """Takes a string and makes it printable

    Args:
        str: The string to make printable

    Returns:
        The string with all weird characters filtered
    """
    return ''.join(filter(lambda x: x in set(string.printable), str))

def handle_submission(subm):
    """Performs any actions that are necessary for the given submission.

    It may delete the submission, flair the submission, or otherwise perform
    moderator actions against the submission.

    Args:
        subm: The praw.models.reddit.Submission object
    """
    global blacklist

    print(f'Handling submission {subm.id} by {subm.author.name if subm.author else None}\n  Link: {subm.url}')

    if subm.is_self:
        print('  Ignoring; it is a self-post')
        return

    if subm.banned_by is not None:
        print(f'  Ignoring; the submission was removed by {subm.banned_by}')
        return

    if subm.approved_by is not None and subm.approved_by != 'AutoModerator':
        print(f'  Ignoring; the submission was approved by {subm.approved_by}')
        return

    if subm.author is not None:
        if subm.author.name in whitelist.fetch():
            print(f'  Ignoring; the submission author is {subm.author.name}')
            return

    if not is_discord_or_discord_redirect_link(subm.url):
        print(f'  Ignoring; the submission links to {subm.url} which is unrecognized')
        return

    advert = database.fetch_advert_by_fullname(subm.fullname)
    group = None
    if advert is not None:
        time_since_touched = time.time() - advert['updated_at']
        group = database.fetch_group_by_id(advert['group_id'])
        old_group_name_printable = make_printable(group['dgroup_name'])
        if time_since_touched < config.post_update_time_seconds:
            print(f'  Ignoring; We have seen this post before (goes to {old_group_name_printable}) and checked it only {time_since_touched} seconds ago')
            return

        time_since_checked_mins = round(time_since_touched / 60)
        print(f'  When we checked this about {time_since_checked_mins} minutes ago and it went to {old_group_name_printable}')

    official_link = subm.url
    if is_whitelisted_redir(official_link):
        official_link = follow_redir_link(official_link)
        print(f'  After following redirects found final url {official_link}')


        if official_link is None or not is_official_link(official_link):
            print('  Since that is not a valid discord link, replying and deleting...')
            reply_and_delete_submission(subm)
            return

    assert is_official_link(official_link)

    code = get_code_from_official_link(official_link)
    assert code is not None and code != ''

    invite = get_invite_from_code(code)
    if invite is None:
        print(f'  Found no invite corresponding with the code {code} - replying...')
        reply_and_delete_submission(subm)
        return


    guild_name = invite['guild']['name']
    guild_id = invite['guild']['id']
    print_safe_name = make_printable(guild_name)
    print(f'  Valid! Code {code} = {print_safe_name} (ID: {guild_id})')
    if guild_id in blacklist.fetch():
        print('  Server is blacklisted! Sending modmail...')

        if config.dry_run:
            print('  Would send modmail but this is a dry run; waiting 2 seconds instead')
            time.sleep(2)
            return

        msg = f'The user u/{subm.author.name if subm.author else None} tried making [this post]({subm.permalink}) for the banned server **{guild_name}** (Server ID: {guild_id}) in DiscordServers and was just caught by the bot.'
        subreddit.modmail.create('Blacklisted server attempting to post!', msg, 'SubredditGuardian')
        print('    Done sending, removing')
        submission.mod.remove(spam=False)
        print('    Done removing')
        return

    if 'VIP_REGIONS' in invite['guild']['features']:
        print(f'  Detected that the server has VIP features')
        if (    submission.link_flair_text != 'Discord Partner'
             or submission.link_flair_css_class != 'partner-post'
        ):
            if not config.dry_run:
                submission.flair.select(config.flair_id)
                print('    Flaired post as Discord Partner!')
            else:
                print('    Would have flaired as Discord Partner but this is a dry-run')
        else:
            print('    Post already has flair.')

    if not advert:
        _group = database.fetch_group_by_dgroup_id(guild_id)
        if _group is not None:
            old_adverts = database.fetch_adverts_by_group_id(_group['id'])

            for old_advert in old_adverts:
                assert(old_advert['fullname'] != subm.fullname)
                time_since = subm.created_utc - old_advert['posted_at']
                if time_since > 0 and time_since < config.min_time_between_posts_seconds:
                    old_permalink = old_advert['permalink']
                    print(f'  Detected that the post was too soon after the last post')
                    print(f'    Old permalink: {old_permalink}')
                    print(f'    Time since: {str(timedelta(seconds=time_since))}')
                    print('  Replying and deleting...')
                    reply_and_delete_submission(subm, msg = config.too_soon_response_message.format(perma_link_new = subm.permalink, perma_link_old = old_permalink, time_left = str(timedelta(seconds=(config.min_time_between_posts_seconds - time_since)))))
                    return

    if advert:
        assert(group is not None)
        old_print_safe_name = make_printable(group['dgroup_name'])
        old_guild_id = group['dgroup_id']

        if guild_id != old_guild_id:
            print(f'  Detected that this advert changed from {old_print_safe_name} to {print_safe_name}')
            print('  This shouldn\'t happen, sending modmail and deleting')

            if config.dry_run:
                print('    This is a dry-run so waiting 2 seconds instead')
                time.sleep(2)
                return

            msg = f'The user u/{subm.author.name if subm.author else None} made [this post](reddit.com{subm.permalink}) which changed from a link to {old_print_safe_name} (Server ID = {old_guild_id}) to {print_safe_name} (Server ID = {guild_id}). This is peculiar. I will delete it with no comment'
            subreddit.modmail.create('Server link changed servers', msg, 'SubredditGuardian')
            print('    Done sending, removing')
            submission.mod.remove(spam=False)
            print('    Done removing')
            return
        
        ### START - Test some janky copypasta time checks ###
        #group = database.fetch_group_by_id(advert['group_id'])
        saved_adverts = database.fetch_adverts_by_group_id(group['id'])

        for saved_advert in saved_adverts:
            time_since = saved_advert['posted_at'] - subm.created_utc
            if time_since > 0 and time_since < config.min_time_between_posts_seconds:
                    
                    saved_permalink = saved_advert['permalink']
                    newer_subm = re.search('.*\/comments\/([A-Za-z0-9]+)\/.*', saved_permalink, re.IGNORECASE)

                    if newer_subm:
                        saved_subm_id = newer_subm.group(1)
                        try:
                            saved_subm = reddit.get_submission(submission_id=saved_subm_id);
                            print(f'  Detected that this server was double-posted')
                            print(f'    Previous saved permalink: {saved_permalink}')
                            print(f'    Time since: {str(timedelta(seconds=time_since))}')
                            print('  Replying and deleting...')
                            reply_and_delete_submission(saved_subm, msg = config.double_post_response_message.format(perma_link_saved = saved_permalink, perma_link_current = subm.permalink, time_left = str(timedelta(seconds=(config.min_time_between_posts_seconds - time_since)))))
                            for _saved_advert in database.fetch_adverts_by_group_id(group['id']):
                                if (_saved_advert['permalink'] == saved_permalink):
                                    # Remove the newer record
                                    database.delete_advert(_saved_advert['id'])
                                    break
                            return
                        except Exception:
                            print(f'Error Encountered:\r\n{Exception}')
        ### END - Test some janky copypasta time checks ###

        database.touch_advert(advert['id'])
    else:
        assert(group is None)

        group = database.fetch_group_by_dgroup_id(guild_id)
        if group is None:
            database.save_group(guild_name, guild_id)
            group = database.fetch_group_by_dgroup_id(guild_id)

        assert(group is not None)
        database.save_advert(subm.fullname, subm.permalink, group['id'], subm.created_utc)


print('Connecting to database')
database.connect(config.database_file)
database.create_missing_tables()
database.prune()

print('Fetching lists')
blacklist = StringList('blacklist.txt')
whitelist = StringList('whitelist.txt')

print('Logging in')
reddit = praw.Reddit(client_id=auth_config.client_id,
                     client_secret=auth_config.client_secret,
                     password=auth_config.password,
                     user_agent='DiscordServers bot by /u/tjstretchalot',
                     username=auth_config.username)

subreddit = reddit.subreddit(config.subreddit_name)
recently_checked_subm_ids = []
hot_check_counter = 0
last_prune_time = time.time()

# CHECK SUBREDDIT FLAIRS BEFORE STARTING
#for template in subreddit.flair.link_templates:
#    print(template)

while True:
    print('======= Scanning new... =======')
    just_checked = []
    for submission in subreddit.new(limit=config.max_posts_until_miss_in_new):
        just_checked.append(submission.id)
        if submission.id in recently_checked_subm_ids:
            continue
        handle_submission(submission)
        print(f'Sleeping for {config.check_sleep_time_seconds} seconds')
        time.sleep(config.check_sleep_time_seconds)

    recently_checked_subm_ids = just_checked
    print(f'Sleeping for {config.loop_sleep_time_seconds} seconds')
    time.sleep(config.loop_sleep_time_seconds)

    if hot_check_counter <= 0:
        hot_check_counter = config.loops_per_hot_check

        print('============== Scanning hot... ==============')
        for submission in subreddit.hot(limit=config.num_hot_posts_to_rescan):
            handle_submission(submission)
            print(f'Sleeping for {config.check_sleep_time_seconds} seconds')
            time.sleep(config.check_sleep_time_seconds)
        print(f'Sleeping for {config.loop_sleep_time_seconds} seconds')
        time.sleep(config.loop_sleep_time_seconds)
    else:
        hot_check_counter -= 1

    if last_prune_time + config.database_prune_period_seconds < time.time():
        print('Pruning database')
        database.prune()
        last_prune_time = time.time()

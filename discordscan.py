#!/usr/bin/env python3.6

"""Main entrance to discord scan"""

import discord
import redirects
import retry
import config
import blacklist
import time
import praw

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
        or link.startswith('http://discord.me')
        or link.startswith('https://discord.me')
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

def reply_and_delete_submission(subm):
    """Responds with the default message, distinguishes response, and deletes

    This is the correct course of action for a link to an invalid discord channel,
    or a link to a redirector that does not lead to a valid discord channel.

    Args:
        subm: The praw.models.reddit.Submission object
    """
    
    comment = submission.reply(config.response_message)
    comment.mod.distinguish()
    print('Done replying, removing')
    submission.mod.remove(spam=False)
    print('Done removing')

def handle_submission(subm):
    """Performs any actions that are necessary for the given submission.

    It may delete the submission, flair the submission, or otherwise perform
    moderator actions against the submission.

    Args:
        subm: The praw.models.reddit.Submission object
    """

    print(f'Handling submission {subm.id} by {subm.author.name if subm.author else None}\r\n  Link: {subm.url}')

    if subm.is_self:
        print('  Ignoring; it is a self-post')
        return

    if subm.banned_by is not None:
        print(f'  Ignoring; the submission was removed by {subm.banned_by}')
        return

    if not is_discord_or_discord_redirect_link(subm.url):
        print(f'  Ignoring; the submission links to {subm.url} which is unrecognized')
        return

    official_link = subm.url
    if is_whitelisted_redir(official_link):
        succ, new_link = follow_redir_link(official_link)
        if not succ:
            print(f'  Failed to follow the redirect chain, ignoring for now.')
            return
        official_link = new_link
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
    print(f'  Valid! Code {code} = {guild_name} (ID: {guild_id})')
    if guild_id in blacklist.fetch():
        print('Server is blacklisted! Sending modmail...')
        msg = f'The user u/{subm.author.name if subm.author else None} tried making [this post]({subm.permalink}) for the banned server **{guild_name}** (Server ID: {guild_id}) in DiscordServers and was just caught by the bot.'
        subreddit.modmail.create('Blacklisted server attempting to post!', msg, 'SubredditGuardian')
        print('Done sending, removing')
        submission.mod.remove(spam=False)
        print('Done removing')
        return

    if 'VIP_REGIONS' in invite['guild']['features']:
        print(f'  Detected that the server has VIP features')
        if (    submission.link_flair_text != 'Discord Partner'
             or submission.link_flair_css_class != 'partner-post'
        ):
            submission.flair.select(config.flair_id)
            print('Flaired post as Discord Partner!')
        else:
            print('Post already has flair.')

print('Logging in')
reddit = praw.Reddit(client_id=auth_config.client_id,
                     client_secret=auth_config.client_secret,
                     password=auth_config.password,
                     user_agent='DiscordServers bot by /u/tjstretchalot',
                     username=auth_config.username)

subreddit = reddit.subreddit(config.subreddit_name)
recently_checked_subm_ids = []
hot_check_counter = 0

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

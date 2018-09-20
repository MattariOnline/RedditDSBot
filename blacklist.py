"""Loads and updates a blacklist from a text file.

Note that this is not where you store the actual blacklist - do that in
blacklist.txt"""

import os

file_path = os.path.dirname(os.path.realpath(__file__)) + "/blacklist.txt"
cached_blacklist = None
cached_stamp = None

def load():
    """Loads the blacklist.

    This ignores all globals and simply fetches the blacklist from the file.

    Returns:
        The blacklisted ids from blacklist.txt
    """
    global file_path

    result = []
    with open(file_path) as the_list:
        for line in the_list:
            list_item = line.split(',')[0].rstrip('\n').rstrip('\r')
            if list_item != '':
                result.append(list_item)
    return result

def is_stale():
    """Checks if the blacklist is stale and needs to be loaded.

    Returns:
        True if the blacklist needs to be reloaded, False otherwise.
    """
    global cached_blacklist
    global cached_stamp
    global file_path

    if cached_blacklist is None:
        return True

    stamp = os.stat(file_path).st_mtime
    if stamp != cached_stamp:
        print(f'Blacklist out of date; {stamp} vs {cached_stamp}')
        return True

    return False

def fetch():
    """Get the most up to date blacklist.

    This will load from file only if it's necessary

    Returns:
        The blacklisted ids from blacklist.txt
    """
    global cached_blacklist
    global cached_stamp
    global file_path

    if is_stale():
        cached_stamp = os.stat(file_path).st_mtime
        print('Loading blacklist...')
        cached_blacklist = load()

    return cached_blacklist

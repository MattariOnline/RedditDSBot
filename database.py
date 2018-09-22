"""Module for interacting with the sqlite database

Tables:
    groups:
        Maps discord groups to an internal representation

        id: (int, autoincrement, primary)
        dgroup_name: (text)
        dgroup_id: (text, unique)
        created_at: (real) unix time

    adverts:
        Maps submissions to the subreddit to the group they advertised

        id: (int, autoincrement, primary)
        fullname: (text, unique)
        permalink: (text)
        group_id: (int, foreign key references groups(id))
        found_at: (real) unix time
        updated_at: (real) unix time
        posted_at: (real) unix time
"""

import sqlite3
import time

connection = None
def connect(file):
    """Initiates the connection to the database

    Args:
        file: The file to connect to
    """
    global connection
    connection = sqlite3.connect(file)
    connection.row_factory = sqlite3.Row

def close():
    """Close the connection"""
    global connection
    connection.commit()
    connection.close()
    connection = None

def create_missing_tables():
    """Create all missing tables"""
    global connection
    cur = connection.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT,'\
        'dgroup_name TEXT, dgroup_id TEXT UNIQUE, created_at REAL)')
    cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS gdgid ON groups (dgroup_id)')
    cur.execute('CREATE TABLE IF NOT EXISTS adverts (id INTEGER PRIMARY KEY AUTOINCREMENT,'\
        'fullname TEXT, permalink TEXT, group_id INT, found_at REAL, updated_at REAL, posted_at REAL,'\
        'FOREIGN KEY(group_id) REFERENCES groups(id))')
    cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS afn ON adverts (fullname)')
    connection.commit()
    cur.close()

def fetch_group_by_dgroup_id(dgroup_id):
    """Fetch our internal group representation of the given discord group id

    Args:
        dgroup_id: The string identifier that discord uses for the group

    Returns:
        Dictionary of our internal representation of the group, see class
        comments for details. None if we have no saved representation.
    """
    global connection
    cur = connection.cursor()
    cur.execute('SELECT * FROM groups WHERE dgroup_id=?', (dgroup_id,))
    row = cur.fetchone()
    res = dict(row) if row != None else None
    cur.close()
    return res

def fetch_group_by_id(id):
    """Fetch our internal group representation from our internal group id

    Args:
        id: The int id we assigned to this group

    Returns:
        Dictionary of our representation of the group, see class comments
        for details. None if we have no saved representation
    """
    global connection
    cur = connection.cursor()
    cur.execute('SELECT * FROM groups WHERE id=?', (id,))
    row = cur.fetchone()
    res = dict(row) if row != None else None
    cur.close()
    return res

def save_group(dgroup_name, dgroup_id):
    """Saves the discord group and id to our internal mapping

    Args:
        dgroup_name: the string name of the discord group
        dgroup_id: the string identifier of the discord group
    """
    global connection
    cur = connection.cursor()
    cur.execute('INSERT INTO groups (dgroup_name, dgroup_id, created_at) values(?, ?, ?)', (dgroup_name, dgroup_id, time.time()))
    connection.commit()
    cur.close()

def fetch_advert_by_fullname(fullname):
    """Fetches the saved advert for the given fullname

    Args:
        fullname: the reddit fullname of the submission (ie t3_asdf)

    Returns:
        Dictionary of the advert row corresponding with the fullname, see
        class comments for details. None if we have no saved adverts for
        the submission.
    """
    global connection
    cur = connection.cursor()
    cur.execute('SELECT * FROM adverts WHERE fullname=?', (fullname,))
    row = cur.fetchone()
    res = dict(row) if row != None else None
    cur.close()
    return res

def fetch_adverts_by_group_id(group_id):
    """Fetches the adverts we know about associated with the given group

    Args:
        group_id: The group id of the row in our database

    Returns:
        A list of dictionaries of adverts. Empty list if no adverts found.
        See class comments for details on what an advert looks like.
    """
    global connection
    cur = connection.cursor()
    cur.execute('SELECT * FROM adverts WHERE group_id=?', (group_id,))
    rows = cur.fetchall()
    res = list(dict(row) for row in rows)
    cur.close()
    return res

def save_advert(fullname, permalink, group_id, posted_at):
    """Saves the advert that we just found.

    Args:
        fullname: The reddit fullname of the submission the advert is on
        permalink: A link to the submission
        group_id: The id of the row in our groups table associated with the discord group
        posted_at: When the submission was posted, in unix time seconds
    """
    global connection
    cur = connection.cursor()
    cur.execute('INSERT INTO adverts (fullname, permalink, group_id, found_at, updated_at, posted_at) VALUES (?, ?, ?, ?, ?, ?)',\
        (fullname, permalink, group_id, time.time(), time.time(), posted_at))
    connection.commit()
    cur.close()

def touch_advert(id):
    """Update the updated_at for the given advert to now

    Args:
        id: the id of the advert you want to touch
    """
    global connection
    cur = connection.cursor()
    cur.execute('UPDATE adverts SET updated_at=? WHERE id=?', (time.time(), id))
    connection.commit()
    cur.close()

def delete_advert(id):
    """Delete the advert with the given id

    Args:
        id: the id of the advert you want to delete
    """
    global connection
    cur = connection.cursor()
    cur.execute('DELETE FROM adverts WHERE id=?', (id,))
    connection.commit()
    cur.close()

def prune():
    """Prunes old entries from the database"""
    global connection

    one_day_ago = time.time() - 60 * 60 * 24
    cur = connection.cursor()
    cur.execute('DELETE FROM adverts WHERE posted_at < ?', (one_day_ago,))
    cur.execute('DELETE FROM groups WHERE id NOT IN (SELECT group_id FROM adverts a)')
    connection.commit()
    cur.close()

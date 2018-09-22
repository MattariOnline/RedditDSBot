"""Loads and updates a string list from file.

Maintains a live copy of the string list from the file by checking
the modified timestamp."""

import os

class StringList:
    """A simple file string list with commas for comments

    One line in the file corresponds with one string in the list.
    The list is reloaded automatically when the file is changed,
    but only when the list is requested.

    Attributes:
        file_name - the name of the file we are loading from
        file_path - the full path to the file we are loading
        cached_list - the current list we have in memory
        cached_stamp - the modified time of the file when we loaded it
    """

    def __init__(self, file_name):
        """Loads a string list from the given filename.

        The path will be in the same folder as this file (stringlist.py)

        Args:
            filename: The name of the file (typically with extension .txt)
        """
        self.file_name = file_name
        self.file_path = os.path.dirname(os.path.realpath(__file__)) + "/" + file_name
        self.cached_list = None
        self.cached_stamp = None

    def load(self):
        """Loads the list.

        This ignores state and simply fetches the list from the file. This
        does not cache the list. This typically does not need to be called
        externally.

        Returns:
            The list of strings from the file
        """
        result = []
        with open(self.file_path) as the_list:
            for line in the_list:
                list_item = line.split(',')[0].rstrip('\n').rstrip('\r')
                if list_item != '':
                    result.append(list_item)
        return result

    def is_stale(self):
        """Checks if the list is stale and needs to be loaded from file.

        Returns:
            True if the list needs to be reloaded, False otherwise.
        """
        if self.cached_list is None:
            return True

        stamp = os.stat(self.file_path).st_mtime
        if stamp != self.cached_stamp:
            return True

        return False

    def fetch(self):
        """Get the most up to date list.

        This will load from file only if it's necessary

        Returns:
            The list of strings contained in the file
        """
        if self.is_stale():
            self.cached_stamp = os.stat(self.file_path).st_mtime
            self.cached_list = self.load()

        return self.cached_list

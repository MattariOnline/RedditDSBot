"""Manages following redirects."""

import requests

from bs4 import BeautifulSoup

redir_codes = [ 301, 302, 303, 307, 308 ]
"""Codes that indicate a simple http redirect"""

class RedirectError(Exception):
    """An error that occurred following a redirect.

    Attributes:
        url: The string for the url we were trying to reach.
    """

    def __init__(self, message, url):
        super().__init__(message)
        self.url = url

def find_redirect(response):
    """Finds the redirect, if there is one, in the given response.

    Args:
        response: A response from the server, a requests.Response object.

    Returns:
        A string of the url the response is redirecting to, or None if no
        redirect is found.
    """
    global redir_codes

    if response.status_code in redir_codes:
        redir_url = response.headers['Location']
        print(f'{response.url} uses {response.status_code} to redirect to {redir_url}')
        return redir_url

    soup = BeautifulSoup(response.text, 'html5lib')

    metas = soup.find_all('meta')

    for meta in metas:
        if ('property' in meta.attrs and meta.attrs['property'] == 'refresh') or ('http-equiv' in meta.attrs and meta.attrs['http-equiv'] == 'refresh'):
            content = meta.attrs['content']
            url = content.split(';')[1][4:]
            if url.startswith('='): # Fix more messy Django crap (Discord.st)
                url = url[1:]
            print(response.url, 'uses meta property ->', url)
            return url

    return None


def _follow(url, predicate, tries=1, max_redirects=5):
    if tries > max_redirects:
        raise requests.exceptions.TooManyRedirects()

    response = None
    try:
        response = requests.get(url, allow_redirects=False, timeout=10)
    except requests.exceptions.ConnectionError as ce:
        raise RedirectError('Connection failure', url) from ce
    except requests.exceptions.ReadTimeout as rte:
        raise RedirectError('Read timeout', url) from rte
    except requests.exceptions.RequestException as re:
        raise RedirectError('Unusual HTTP error', url) from re

    redir_url = find_redirect(response)
    if redir_url:
        if not predicate(redir_url):
            return redir_url
        return _follow(redir_url, predicate, tries + 1, max_redirects)

    return url

def follow(url, predicate, max_redirects=10):
    """Follows redirects starting at the given url.

    Finishes either when the predicate returns False or when there are no
    redirects detected.

    Args:
        url: The string url to follow
        predicate: Function that accepts a url and returns a bool indicating
            if we should try to continue. True to continue, False to end.
        max_redirects: The maximum redirects to follow

    Returns:
        The string of the final url reached.

    Raises:
        RedirectError: If we cannot reach a URL along the way
        TooManyRedirects: If it exceeds the maximum number of redirects
    """
    return _follow(url, predicate, max_redirects=max_redirects)

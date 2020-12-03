"""
# --------------------------------------------------------------------------------------------------
# Common funcs
# --------------------------------------------------------------------------------------------------
"""

import sys
import os

import requests

from globals import LOGGER
from globals import LOG_FILE
from globals import SPACE_KEY
from globals import CONFLUENCE_API_URL

def check_for_errors(response):
    """
   Check response for errors and log help if necessary

   :param response: the received response
   :return
   """
    try:
        response.raise_for_status()
    except requests.RequestException as err:
        LOGGER.error('err.response: %s', err)
        if response.status_code == 404:
            LOGGER.error('Error: Page not found. Check the following are correct:')
            LOGGER.error('Space Key : %s', SPACE_KEY)
            LOGGER.error('Confluence URL : %s', CONFLUENCE_API_URL)
        else:
            LOGGER.error('Error: %d - %s', response.status_code, response.content)
        sys.exit(1)


def log_html(html, title):
    """
    Logs generated html to file

    :param html: html to log
    :param title: title of the logged file
    :return:
    """
    log_file = open(LOG_FILE, 'a+')
    log_file.write('\n')
    log_file.write(title)
    log_file.write('\n')
    log_file.write(html)


def get_page_as_ancestor(page_id):
    """
    Get ancestors object accepted by the API from a page id

    :param page_id: the ancestor page id
    :return: API-compatible ancestor
    """
    return [{'type': 'page', 'id': page_id}]


def does_path_contain(directory, predicate):
    """
    Determine if a directory contains any file matching a predicate,
    including within subdirectories

    :param directory: directory in which to look for matching files
    :param predicate: predicate function to determine if a file matches
    :return: True if any file in the directory or subdirectories matches the predicate
    """
    for _root, _dirs, files in os.walk(directory):
        for file in files:
            if predicate(file):
                return True
    return False

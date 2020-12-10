"""
# --------------------------------------------------------------------------------------------------
# Global variables
# --------------------------------------------------------------------------------------------------
"""

import logging
import sys
import os
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - \
%(levelname)-5s - [%(lineno)-3d] %(funcName)-18s - \
%(message)s')
LOGGER = logging.getLogger(__name__)

def _get_args():
    """
    Get command-line arguments

    :return: args
    """
    # ArgumentParser to parse arguments and options
    parser = argparse.ArgumentParser()
    parser.add_argument('spacekey', nargs='?',
                        help="Confluence Space key for the page. ")
    parser.add_argument('-u', '--username',
                        help='Confluence username if $CONFLUENCE_USERNAME not set.')
    parser.add_argument('-p', '--apikey', help='Confluence API key if $CONFLUENCE_API_KEY not set.')
    parser.add_argument('-o', '--orgname',
                        help='Confluence organisation if $CONFLUENCE_ORGNAME not set. '
                             'e.g. https://XXX.atlassian.net/wiki'
                             'If orgname contains a dot, considered as the fully qualified domain '
                             'name. e.g. https://XXX')
    parser.add_argument('-a', '--ancestor',
                        help='The id of the parent page under which every other page will be '
                             'created or updated. You can find the id in the URL.')
    parser.add_argument('-f', '--folders', nargs='*',
                        help='Full path of the documentation folder(s) to convert and upload.  '
                             'Defaults to current working directory.')
    parser.add_argument('-c', '--contents', action='store_true', default=False,
                        help='Use this option to generate a contents page.')
    parser.add_argument('-l', '--loglevel', default='INFO',
                        help='Use this option to set the log verbosity.')
    parser.add_argument('-s', '--simulate', action='store_true', default=False,
                        help='Use this option to only show conversion result.')
    parser.add_argument('-ht', '--loghtml', action='store_true', default=False,
                        help='Use this option to log generated html pages in separate files.')
    parser.add_argument('--note',
                        help='Use this option to specify a note to prepend on generated html '
                             'pages.')
    parser.add_argument('--notrack', action='store_true', default=False,
                        help='Use this option to avoid tracking / deleting children.')

    args = parser.parse_args()

    # Set log level based on command line arg
    LOGGER.setLevel(getattr(logging, args.loglevel.upper(), None))

    return args

def _get_documentation_roots(args):
    """
    Get documentation root(s)
    :param args: args
    :return: documentation root(s)
    """
    return args.folders or [os.getcwd()]

def _get_log_file(_args):
    """
    Get log file
    :param args: args
    :return: log file
    """
    log_file_name = 'logs_' + datetime.now().strftime("%Y_%m_%d-%H_%M") + '.txt'
    log_folder = 'logs/'
    return log_folder + log_file_name

def _get_user_name(args):
    """
    Get user name
    :param args: args
    :return: user name
    """
    username = args.username or os.getenv('CONFLUENCE_USERNAME')
    if username is None:
        LOGGER.error('Error: Username not specified by environment variable or option.')
        sys.exit(1)
    return username

def _get_api_key(args):
    """
    Get API key or password
    :param args: args
    :return: API key or password
    """
    api_key = args.apikey or os.getenv('CONFLUENCE_API_KEY')
    if api_key is None:
        LOGGER.error('Error: API key not specified by environment variable or option.')
        sys.exit(1)
    return api_key

def _get_space_key(args, username):
    """
    Get space key
    :param args: args
    :return: space key
    """
    space_key = args.spacekey or os.getenv('CONFLUENCE_SPACE_KEY')
    if space_key is None:
        space_key = '~%s' % (username)
    return space_key

def _get_confluence_api_url(args):
    """
    Get confluence API URL
    :param args: args
    :return: confluence API URL
    """
    orgname = args.orgname or os.getenv('CONFLUENCE_ORGNAME')
    if orgname is not None:
        if orgname.find('.') != -1:
            if orgname.startswith('http://') or orgname.startswith('https://'):
                return orgname
            else:
                return 'https://%s' % orgname
        else:
            return 'https://%s.atlassian.net/wiki' % orgname
    else:
        LOGGER.error('Error: Org Name not specified by environment variable or option.')
        sys.exit(1)

def _get_ancestor(args):
    """
    Get ancestor page id
    :param args: args
    :return: ancestor page id
    """
    ancestor = args.ancestor or os.getenv('CONFLUENCE_ANCESTOR')
    if ancestor is None:
        LOGGER.error('Error: The ancestor page is not specified under which the documentation '
                    'should be created.')
        sys.exit(1)
    return ancestor

def _get_note(args):
    """
    Get note to prefix page content with
    :param args: args
    :return: note
    """
    return args.note or os.getenv('CONFLUENCE_NOTE')


_args = _get_args()
DOCUMENTATION_ROOTS = _get_documentation_roots(_args)
LOG_FILE = _get_log_file(_args)
USERNAME = _get_user_name(_args)
API_KEY = _get_api_key(_args)
SPACE_KEY = _get_space_key(_args, USERNAME)
CONFLUENCE_API_URL = _get_confluence_api_url(_args)
ANCESTOR = _get_ancestor(_args)
NOTE = _get_note(_args)
SIMULATE = _args.simulate
LOG_HTML = _args.loghtml
CONTENTS = _args.contents
NOTRACK = _args.notrack

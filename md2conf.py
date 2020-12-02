#!/usr/bin/env python3
"""
# --------------------------------------------------------------------------------------------------
# Rittman Mead Markdown to Confluence Tool
# --------------------------------------------------------------------------------------------------
# Create or Update Atlas pages remotely using markdown files.
"""

import logging
import sys
import os
import tempfile
import re
import json
import collections
import mimetypes
import codecs
import argparse
import urllib
import webbrowser
from pathlib import Path

import requests
import markdown
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - \
%(levelname)s - %(funcName)s [%(lineno)d] - \
%(message)s')
LOGGER = logging.getLogger(__name__)

# ArgumentParser to parse arguments and options
PARSER = argparse.ArgumentParser()
PARSER.add_argument('spacekey',
                    help="Confluence Space key for the page. ")
PARSER.add_argument('-u', '--username', help='Confluence username if $CONFLUENCE_USERNAME not set.')
PARSER.add_argument('-p', '--apikey', help='Confluence API key if $CONFLUENCE_API_KEY not set.')
PARSER.add_argument('-o', '--orgname',
                    help='Confluence organisation if $CONFLUENCE_ORGNAME not set. '
                         'e.g. https://XXX.atlassian.net/wiki'
                         'If orgname contains a dot, considered as the fully qualified domain name.'
                         'e.g. https://XXX')
PARSER.add_argument('-a', '--ancestor',
                    help='The id of the parent page under which every other page will be created '
                         'or updated. You can find the id in the URL.')
PARSER.add_argument('-f', '--folder',
                    help='Full path of the documentation folder to convert and upload.  Defaults '
                         'to current working directory.')
PARSER.add_argument('-c', '--contents', action='store_true', default=False,
                    help='Use this option to generate a contents page.')
PARSER.add_argument('-n', '--nossl', action='store_true', default=False,
                    help='Use this option if NOT using SSL. Will use HTTP instead of HTTPS.')
PARSER.add_argument('-d', '--delete', action='store_true', default=False,
                    help='Use this option to delete the page instead of create it.')
PARSER.add_argument('-l', '--loglevel', default='INFO',
                    help='Use this option to set the log verbosity.')
PARSER.add_argument('-s', '--simulate', action='store_true', default=False,
                    help='Use this option to only show conversion result.')
PARSER.add_argument('-ht', '--loghtml', action='store_true', default=False,
                    help='Use this option to log generated html pages in separate files.')
PARSER.add_argument('--note',
                    help='Use this option to specify a note to prepend on generated html pages.')

ARGS = PARSER.parse_args()

# Assign global variables
try:
    # Set log level
    LOGGER.setLevel(getattr(logging, ARGS.loglevel.upper(), None))

    DOCUMENTATION_ROOT = ARGS.folder
    LOG_FILE_NAME = 'logs_' + datetime.now().strftime("%Y_%m_%d-%H_%M") + '.txt'
    LOG_FOLDER = 'logs/'
    LOG_FILE = LOG_FOLDER + LOG_FILE_NAME

    SPACE_KEY = ARGS.spacekey
    API_KEY = os.getenv('CONFLUENCE_API_KEY', ARGS.apikey)
    USERNAME = os.getenv('CONFLUENCE_USERNAME', ARGS.username)
    ORGNAME = os.getenv('CONFLUENCE_ORGNAME', ARGS.orgname)
    ANCESTOR = ARGS.ancestor
    NOSSL = ARGS.nossl
    DELETE = ARGS.delete
    SIMULATE = ARGS.simulate
    LOG_HTML = ARGS.loghtml
    CONTENTS = ARGS.contents
    NOTE = ARGS.note

    if DOCUMENTATION_ROOT is None:
        DOCUMENTATION_ROOT = os.getcwd()

    if USERNAME is None:
        LOGGER.error('Error: Username not specified by environment variable or option.')
        sys.exit(1)

    if API_KEY is None:
        LOGGER.error('Error: API key not specified by environment variable or option.')
        sys.exit(1)

    if SPACE_KEY is None:
        SPACE_KEY = '~%s' % (USERNAME)

    if ANCESTOR is None:
        LOGGER.error('Error: The ancestor page is not specified under which the documentation '
                     'should be created.')
        sys.exit(1)

    if ORGNAME is not None:
        if ORGNAME.find('.') != -1:
            CONFLUENCE_API_URL = 'https://%s' % ORGNAME
        else:
            CONFLUENCE_API_URL = 'https://%s.atlassian.net/wiki' % ORGNAME
    else:
        LOGGER.error('Error: Org Name not specified by environment variable or option.')
        sys.exit(1)

    if NOSSL:
        CONFLUENCE_API_URL.replace('https://', 'http://')

    RESOLVE_REFS_AGAIN = []
    CACHED_PAGE_INFO = {}

except Exception as err: # pylint: disable=broad-except
    LOGGER.error('\n\nException caught:\n%s ', err)
    LOGGER.error('\nFailed to process command line arguments. Exiting.')
    sys.exit(1)


def convert_comment_block(html):
    """
    Convert markdown code block to Confluence hidden comment

    :param html: string
    :return: modified html string
    """
    open_tag = '<ac:placeholder>'
    close_tag = '</ac:placeholder>'

    html = html.replace('<!--', open_tag).replace('-->', close_tag)

    return html


def convert_code_block(html):
    """
    Convert html code blocks to Confluence macros

    :param html: string
    :return: modified html string
    """
    code_blocks = re.findall(r'<pre><code.*?>.*?</code></pre>', html, re.DOTALL)
    if code_blocks:
        for tag in code_blocks:

            conf_ml = '<ac:structured-macro ac:name="code">'
            conf_ml = conf_ml + '<ac:parameter ac:name="theme">Midnight</ac:parameter>'
            conf_ml = conf_ml + '<ac:parameter ac:name="linenumbers">true</ac:parameter>'

            lang = re.search('code class="(.*)"', tag)
            if lang:
                lang = lang.group(1)
            else:
                lang = 'none'

            conf_ml = conf_ml + '<ac:parameter ac:name="language">' + lang + '</ac:parameter>'
            content = re.search(r'<pre><code.*?>(.*?)</code></pre>', tag, re.DOTALL).group(1)
            content = '<ac:plain-text-body><![CDATA[' + content + ']]></ac:plain-text-body>'
            conf_ml = conf_ml + content + '</ac:structured-macro>'
            conf_ml = conf_ml.replace('&lt;', '<').replace('&gt;', '>')
            conf_ml = conf_ml.replace('&quot;', '"').replace('&amp;', '&')

            html = html.replace(tag, conf_ml)

    return html


def convert_info_macros(html):
    """
    Converts html for info, note or warning macros

    :param html: html string
    :return: modified html string
    """
    info_tag = '<p><ac:structured-macro ac:name="info"><ac:rich-text-body><p>'
    note_tag = info_tag.replace('info', 'note')
    warning_tag = info_tag.replace('info', 'warning')
    close_tag = '</p></ac:rich-text-body></ac:structured-macro></p>'

    # Custom tags converted into macros
    html = html.replace('<p>~?', info_tag).replace('?~</p>', close_tag)
    html = html.replace('<p>~!', note_tag).replace('!~</p>', close_tag)
    html = html.replace('<p>~%', warning_tag).replace('%~</p>', close_tag)

    # Convert block quotes into macros
    quotes = re.findall('<blockquote>(.*?)</blockquote>', html, re.DOTALL)
    if quotes:
        for quote in quotes:
            note = re.search('^<.*>Note', quote.strip(), re.IGNORECASE)
            warning = re.search('^<.*>Warning', quote.strip(), re.IGNORECASE)

            if note:
                clean_tag = strip_type(quote, 'Note')
                macro_tag = clean_tag.replace('<p>', note_tag).replace('</p>', close_tag).strip()
            elif warning:
                clean_tag = strip_type(quote, 'Warning')
                macro_tag = clean_tag.replace('<p>', warning_tag).replace('</p>', close_tag).strip()
            else:
                macro_tag = quote.replace('<p>', info_tag).replace('</p>', close_tag).strip()

            html = html.replace('<blockquote>%s</blockquote>' % quote, macro_tag)

    # Convert doctoc to toc confluence macro
    html = convert_doctoc(html)

    return html


def convert_doctoc(html):
    """
    Convert doctoc to confluence macro

    :param html: html string
    :return: modified html string
    """

    toc_tag = '''<p>
    <ac:structured-macro ac:name="toc">
      <ac:parameter ac:name="printable">true</ac:parameter>
      <ac:parameter ac:name="style">disc</ac:parameter>
      <ac:parameter ac:name="maxLevel">7</ac:parameter>
      <ac:parameter ac:name="minLevel">1</ac:parameter>
      <ac:parameter ac:name="type">list</ac:parameter>
      <ac:parameter ac:name="outline">clear</ac:parameter>
      <ac:parameter ac:name="include">.*</ac:parameter>
    </ac:structured-macro>
    </p>'''

    html = re.sub(r'\<\!\-\- START doctoc.*END doctoc \-\-\>', toc_tag, html, flags=re.DOTALL)

    return html


def strip_type(tag, tagtype):
    """
    Strips Note or Warning tags from html in various formats

    :param tag: tag name
    :param tagtype: tag type
    :return: modified tag
    """
    tag = re.sub(r'%s:\s' % tagtype, '', tag.strip(), re.IGNORECASE)
    tag = re.sub(r'%s\s:\s' % tagtype, '', tag.strip(), re.IGNORECASE)
    tag = re.sub(r'<.*?>%s:\s<.*?>' % tagtype, '', tag, re.IGNORECASE)
    tag = re.sub(r'<.*?>%s\s:\s<.*?>' % tagtype, '', tag, re.IGNORECASE)
    tag = re.sub(r'<(em|strong)>%s:<.*?>\s' % tagtype, '', tag, re.IGNORECASE)
    tag = re.sub(r'<(em|strong)>%s\s:<.*?>\s' % tagtype, '', tag, re.IGNORECASE)
    tag = re.sub(r'<(em|strong)>%s<.*?>:\s' % tagtype, '', tag, re.IGNORECASE)
    tag = re.sub(r'<(em|strong)>%s\s<.*?>:\s' % tagtype, '', tag, re.IGNORECASE)
    string_start = re.search('<.*?>', tag)
    tag = upper_chars(tag, [string_start.end()])
    return tag


def upper_chars(string, indices):
    """
    Make characters uppercase in string

    :param string: string to modify
    :param indices: character indice to change to uppercase
    :return: uppercased string
    """
    upper_string = "".join(c.upper() if i in indices else c for i, c in enumerate(string))
    return upper_string


def process_refs(html):
    """
    Process references

    :param html: html string
    :return: modified html string
    """
    refs = re.findall(r'\n(\[\^(\d)\].*)|<p>(\[\^(\d)\].*)', html)

    if refs:

        for ref in refs:
            if ref[0]:
                full_ref = ref[0].replace('</p>', '').replace('<p>', '')
                ref_id = ref[1]
            else:
                full_ref = ref[2]
                ref_id = ref[3]

            full_ref = full_ref.replace('</p>', '').replace('<p>', '')
            html = html.replace(full_ref, '')
            href = re.search('href="(.*?)"', full_ref).group(1)

            superscript = '<a id="test" href="%s"><sup>%s</sup></a>' % (href, ref_id)
            html = html.replace('[^%s]' % ref_id, superscript)

    return html


def get_page(title):
    """
     Retrieve page details by title

    :param title: page tile
    :return: Confluence page info
    """
    if title in CACHED_PAGE_INFO:
        return CACHED_PAGE_INFO[title]

    LOGGER.info('\tRetrieving page information: %s', title)
    url = '%s/rest/api/content?title=%s&spaceKey=%s&expand=version,ancestors' % (
        CONFLUENCE_API_URL, urllib.parse.quote_plus(title), SPACE_KEY)

    session = requests.Session()
    session.auth = (USERNAME, API_KEY)

    response = session.get(url)
    check_for_errors(response)
    data = response.json()
    LOGGER.debug("data: %s", str(data))

    if len(data[u'results']) >= 1:
        page_id = data[u'results'][0][u'id']
        version_num = data[u'results'][0][u'version'][u'number']
        link = '%s%s' % (CONFLUENCE_API_URL, data[u'results'][0][u'_links'][u'webui'])
        ancestor = data[u'results'][0][u'ancestors'][-1][u'id']

        page_info = collections.namedtuple('PageInfo', ['id', 'version', 'link', 'ancestor'])
        page = page_info(page_id, version_num, link, ancestor)
        CACHED_PAGE_INFO[title] = page
        return page

    return False


CHILD_PAGES_CACHE = {}
def get_child_pages(page_id):
    """
     Retrieve details of the child pages by page id

    :param page_id: page id
    :return: the ids of all the child pages
    """
    if page_id in CHILD_PAGES_CACHE:
        return CHILD_PAGES_CACHE[page_id]

    LOGGER.info('\tRetrieving information of original child pages: %s', page_id)
    page_ids = get_direct_child_pages(page_id)

    for page_id in page_ids:
        child_pages = get_child_pages(page_id)
        if child_pages:
            page_ids = page_ids + list(set(child_pages) - set(page_ids))

    CHILD_PAGES_CACHE[page_id] = page_ids
    return page_ids


def get_direct_child_pages(page_id):
    """
     Retrieve every direct child page id

    :param page_id: page id
    :return: ids of immediate child pages
    """
    url = '%s/rest/api/content/search?cql=parent=%s' % \
          (CONFLUENCE_API_URL, urllib.parse.quote_plus(page_id))

    session = requests.Session()
    session.auth = (USERNAME, API_KEY)

    response = session.get(url)
    check_for_errors(response)

    data = response.json()
    LOGGER.debug("data: %s", str(data))

    page_ids = []
    for result in data[u'results']:
        page_ids.append(result[u'id'])

    return page_ids


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
            LOGGER.error('\tSpace Key : %s', SPACE_KEY)
            LOGGER.error('\tOrganisation Name: %s', ORGNAME)
        else:
            LOGGER.error('Error: %d - %s', response.status_code, response.content)
        sys.exit(1)


def add_images(page_id, html, filepath):
    """
    Scan for images and upload as attachments if found

    :param page_id: Confluence page id
    :param html: html string
    :param filepath: markdown file full path
    :return: html with modified image reference
    """
    source_folder = os.path.dirname(os.path.abspath(filepath))

    for tag in re.findall('<img(.*?)/>', html):
        rel_path = re.search('src="(.*?)"', tag).group(1)
        alt_text = re.search('alt="(.*?)"', tag).group(1)
        abs_path = os.path.join(source_folder, rel_path)
        basename = os.path.basename(rel_path)
        upload_attachment(page_id, abs_path, alt_text)
        if re.search('http.*', rel_path) is None:
            if CONFLUENCE_API_URL.endswith('/wiki'):
                html = html.replace('%s' % (rel_path),
                                    '/wiki/download/attachments/%s/%s' % (page_id, basename))
            else:
                html = html.replace('%s' % (rel_path),
                                    '/download/attachments/%s/%s' % (page_id, basename))
    return html


def add_contents(html):
    """
    Add contents page

    :param html: html string
    :return: modified html string
    """
    contents_markup = '<ac:structured-macro ac:name="toc">\n<ac:parameter ac:name="printable">' \
                      'true</ac:parameter>\n<ac:parameter ac:name="style">disc</ac:parameter>'
    contents_markup += '<ac:parameter ac:name="maxLevel">5</ac:parameter>\n' \
                       '<ac:parameter ac:name="minLevel">1</ac:parameter>'
    contents_markup += '<ac:parameter ac:name="class">rm-contents</ac:parameter>\n' \
                       '<ac:parameter ac:name="exclude"></ac:parameter>\n' \
                       '<ac:parameter ac:name="type">list</ac:parameter>'
    contents_markup += '<ac:parameter ac:name="outline">false</ac:parameter>\n' \
                       '<ac:parameter ac:name="include"></ac:parameter>\n' \
                       '</ac:structured-macro>'

    html = contents_markup + '\n' + html
    return html


def create_or_update_page(title, body, ancestors, filepath):
    """
    Create a new page

    :param title: confluence page title
    :param body: confluence page content
    :param ancestors: confluence page ancestor
    :param filepath: markdown file full path
    :return: created or updated page id
    """
    page = get_page(title)
    if page:
        return update_page(page.id, title, body, page.version, ancestors, filepath)
    else:
        LOGGER.info('Creating page %s...', title)

        url = '%s/rest/api/content/' % CONFLUENCE_API_URL

        session = requests.Session()
        session.auth = (USERNAME, API_KEY)
        session.headers.update({'Content-Type': 'application/json'})

        new_page = {'type': 'page',
                    'title': title,
                    'space': {'key': SPACE_KEY},
                    'body': {
                        'storage': {
                            'value': body,
                            'representation': 'storage'
                        }
                    },
                    'ancestors': ancestors
                    }

        LOGGER.debug("data: %s", json.dumps(new_page))

        response = session.post(url, data=json.dumps(new_page))
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as excpt:
            LOGGER.error("error: %s - %s", excpt, response.content)
            exit(1)

        if response.status_code == 200:
            data = response.json()
            space_name = data[u'space'][u'name']
            page_id = data[u'id']
            version = data[u'version'][u'number']
            link = '%s%s' % (CONFLUENCE_API_URL, data[u'_links'][u'webui'])

            LOGGER.info('Page created in %s with ID: %s.', space_name, page_id)
            LOGGER.info('URL: %s', link)

            img_check = re.search(r'<img(.*?)\/>', body)
            if img_check:
                LOGGER.info('\tAttachments found, update procedure called.')
                update_page(page_id, title, body, version, ancestors, filepath)
            return page_id
        else:
            LOGGER.error('Could not create page.')
            sys.exit(1)


def delete_page(page_id):
    """
    Delete a page

    :param page_id: confluence page id
    :return: None
    """
    LOGGER.info('Deleting page %s...', page_id)
    url = '%s/rest/api/content/%s' % (CONFLUENCE_API_URL, page_id)

    session = requests.Session()
    session.auth = (USERNAME, API_KEY)
    session.headers.update({'Content-Type': 'application/json'})

    response = session.delete(url)
    response.raise_for_status()

    if response.status_code == 204:
        LOGGER.info('Page %s deleted successfully.', page_id)
    else:
        LOGGER.error('Page %s could not be deleted.', page_id)


def update_page(page_id, title, body, version, ancestors, filepath):
    """
    Update a page

    :param page_id: confluence page id
    :param title: confluence page title
    :param body: confluence page content
    :param version: confluence page version
    :param ancestors: confluence page ancestor
    :param filepath: markdown file full path
    :return: updated page id
    """
    LOGGER.info('Updating page...')
    CACHED_PAGE_INFO.pop(title, None)

    # Add images and attachments
    body = add_images(page_id, body, filepath)

    url = '%s/rest/api/content/%s' % (CONFLUENCE_API_URL, page_id)

    session = requests.Session()
    session.auth = (USERNAME, API_KEY)
    session.headers.update({'Content-Type': 'application/json'})

    page_json = {
        "id": page_id,
        "type": "page",
        "title": title,
        "space": {"key": SPACE_KEY},
        "body": {
            "storage": {
                "value": body,
                "representation": "storage"
            }
        },
        "version": {
            "number": version + 1,
            "minorEdit": True
        },
        'ancestors': ancestors
    }

    response = session.put(url, data=json.dumps(page_json))
    response.raise_for_status()

    if response.status_code == 200:
        data = response.json()
        link = '%s%s' % (CONFLUENCE_API_URL, data[u'_links'][u'webui'])

        LOGGER.info("Page updated successfully.")
        LOGGER.info('URL: %s', link)
        return data[u'id']
    else:
        LOGGER.error("Page could not be updated.")


def update_page_refs_only(filepath):
    """
    Update refs on a page without changing anything else about it

    :param filepath: markdown file full path
    """
    title = get_title(filepath)
    LOGGER.info('Updating page refs %s...', title)

    # update the page
    page = get_page(title)
    html = get_html(filepath)
    version = page.version
    ancestors = get_page_as_ancestor(page.ancestor)

    LOGGER.info('.. title: %s .. version: %d .. ancestor: %s ..', title, version, page.ancestor)

    update_page(page.id, title, html, version, ancestors, filepath)

def get_attachment(page_id, filename):
    """
    Get page attachment

    :param page_id: confluence page id
    :param filename: attachment filename
    :return: attachment info in case of success, False otherwise
    """
    url = '%s/rest/api/content/%s/child/attachment?filename=%s' % \
          (CONFLUENCE_API_URL, page_id, filename)

    session = requests.Session()
    session.auth = (USERNAME, API_KEY)

    response = session.get(url)
    response.raise_for_status()
    data = response.json()

    if len(data[u'results']) >= 1:
        att_id = data[u'results'][0]['id']
        att_info = collections.namedtuple('AttachmentInfo', ['id'])
        attr_info = att_info(att_id)
        return attr_info

    return False


def upload_attachment(page_id, file, comment):
    """
    Upload an attachment

    :param page_id: confluence page id
    :param file: attachment file
    :param comment: attachment comment
    :return: boolean
    """
    if re.search('http.*', file):
        return False

    content_type = mimetypes.guess_type(file)[0]
    filename = os.path.basename(file)

    if not os.path.isfile(file):
        LOGGER.error('File %s cannot be found --> skip ', file)
        return False

    file_to_upload = {
        'comment': comment,
        'file': (filename, open(file, 'rb'), content_type, {'Expires': '0'})
    }

    attachment = get_attachment(page_id, filename)
    if attachment:
        url = '%s/rest/api/content/%s/child/attachment/%s/data' % \
              (CONFLUENCE_API_URL, page_id, attachment.id)
    else:
        url = '%s/rest/api/content/%s/child/attachment/' % (CONFLUENCE_API_URL, page_id)

    session = requests.Session()
    session.auth = (USERNAME, API_KEY)
    session.headers.update({'X-Atlassian-Token': 'no-check'})

    LOGGER.info('\tUploading attachment %s...', filename)

    response = session.post(url, files=file_to_upload)
    response.raise_for_status()

    return True


def remove_collapsible_headings(read):
    """
    Removes collapsible headings from markdown read from file
    :param read: raw markdown read from file
    :return: markdown without tags for collapsible headings
    """
    read = read.replace('<details>', '')
    read = read.replace('</details>', '')
    read = read.replace('<summary>', '')
    read = read.replace('</summary>', '')
    return read


def get_html(filepath):
    """
    Generate html from md file

    :param filepath: the file to translate to html
    :return: html translation
    """
    with codecs.open(filepath, 'r', 'utf-8') as mdfile:
        read = mdfile.read()
        read = remove_collapsible_headings(read)
        html = markdown.markdown(read, extensions=['markdown.extensions.tables',
                                                   'markdown.extensions.fenced_code',
                                                   'markdown.extensions.sane_lists'])
    html = '\n'.join(html.split('\n')[1:])
    html = add_note(html)
    html = convert_info_macros(html)
    html = convert_comment_block(html)
    html = convert_code_block(html)
    if CONTENTS:
        html = add_contents(html)

    html = process_refs(html)
    html = resolve_refs(html, filepath)
    if LOG_HTML:
        title = get_title(filepath)
        html_log_file = open(LOG_FOLDER + title + '.html', 'w+')
        html_log_file.write('<h1>' + title + '</h1>')
        html_log_file.write(html)
    else:
        LOGGER.debug('\tfile: %s \n\thtml: %s', filepath, html)

    return html


def resolve_refs(html, filepath):
    """
    Translates relative links in html, but keeps absolute links

    :param html: html
    :param filepath: path to markdown file
    :return: html file with relative links
    """
    refs = re.findall('(href="([^"]+)")', html)
    if refs:
        for ref in refs:
            if not ref[1].startswith(('http', '/')) and ref[1].endswith('.md'):
                with open(os.path.dirname(filepath) + "/" + ref[1], 'r') as mdfile:
                    title = mdfile.readline().lstrip('#').strip()
                page = get_page(title)
                if page:
                    html = html.replace(ref[0], "href=\"" + page.link + "\"")
                else:
                    if not filepath in RESOLVE_REFS_AGAIN:
                        RESOLVE_REFS_AGAIN.append(filepath)
    return html


def add_note(html):
    """
    Adds a warning to the top of the html page

    :param html: the raw html
    :return: html with warning
    """
    if NOTE:
        warning = '<p>~!' + NOTE + '!~</p>'
        html = warning + html
    return html


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


def get_title(filepath):
    """
    Returns confluence page title extracted from the markdown file

    :param filepath: full path to  markdown file
    :return: confluence page title
    """
    with open(filepath, 'r') as mdfile:
        title = mdfile.readline().lstrip('#').strip()
        mdfile.seek(0)
    LOGGER.info('Title:\t\t%s', title)
    return title


def get_landing_page_doc_file(directory):
    """
    Get full file path to the markdown file corresponding to the directory

    :param directory: the directory
    :return: full path to corresponding landing page markdown file
    """

    # if the directory contains a README.md, use that
    file = Path(directory) / 'README.md'
    if os.path.exists(file):
        return file

    # look for a file in the root directory, with a name matching the directory
    root = Path(DOCUMENTATION_ROOT)
    md_file = os.path.basename(directory) + '.md'
    file = root / md_file
    if os.path.exists(file):
        return file

    # fall back on creating a file containing only the directory name
    file = tempfile.NamedTemporaryFile(mode='w', delete=False)
    file.write('# ' + os.path.basename(directory) + '\n')
    file.close()
    return Path(file.name)


def get_page_as_ancestor(page_id):
    """
    Get ancestors object accepted by the API from a page id

    :param page_id: the ancestor page id
    :return: API-compatible ancestor
    """
    return [{'type': 'page', 'id': page_id}]


def create_dir_landing_page(dir_landing_page_file, ancestors):
    """
    Create landing page for a directory

    :param dir_landing_page_file: the raw markdown file to use for landing page html generation
    :param ancestors: the ancestor pages of the new landing page
    :return: the created landing page id
    """
    landing_page_title = get_title(dir_landing_page_file)
    html = get_html(dir_landing_page_file)
    if SIMULATE:
        log_html(html, landing_page_title)
        return []

    page_id = create_or_update_page(landing_page_title, html, ancestors, dir_landing_page_file)

    return page_id


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


def upload_folder(directory, ancestors):
    """
    Upload everything under a folder, recursively

    :param directory: folder to upload
    :param ancestors: parent page in ancestors format
    :return: list of page ids that are active in this folder
    """
    LOGGER.info('\t\tFolder:\t%s', directory)
    active_pages = []

    # there must be at least one .md file under this folder or a
    # subfolder in order for us to proceed with processing it
    if not does_path_contain(directory, lambda file : os.path.splitext(file)[1] == '.md'):
        LOGGER.info('\t\tSkipping folder; no files found')
        return active_pages

    # Walk through all .md files in this directory and upload them all with
    # the same ancestors (i.e. as siblings)
    dir_landing_as_ancestors = None
    for file in os.scandir(directory):
        if file.is_file() and os.path.splitext(file)[1] == '.md':
            LOGGER.info('Markdown file:\t%s', file.name)
            title = get_title(file.path)
            html = get_html(file.path)

            if SIMULATE:
                log_html(html, title)
            else:
                page_id = create_or_update_page(title, html, ancestors, file.path)
                active_pages.append(page_id)
                if dir_landing_as_ancestors is None or \
                    os.path.basename(file).lower() == 'readme.md':
                    dir_landing_as_ancestors = get_page_as_ancestor(page_id)

    # If we didn't get any landing page at all, then we must create one
    if dir_landing_as_ancestors is None and not SIMULATE:
        doc_file = get_landing_page_doc_file(directory)
        dir_landing_page_id = create_dir_landing_page(doc_file, ancestors)
        active_pages.append(dir_landing_page_id)
        dir_landing_as_ancestors = get_page_as_ancestor(dir_landing_page_id)

    # Walk through all subdirectories and recursively upload them,
    # using this directory's landing page as the ancestor for them
    for folder in os.scandir(directory):
        if folder.is_dir():
            child_active_pages = upload_folder(folder.path, dir_landing_as_ancestors)
            active_pages.extend(child_active_pages)

    return active_pages


def main():
    """
    Main program

    :return:
    """
    LOGGER.info('\t\t----------------------------------')
    LOGGER.info('\t\tMarkdown to Confluence Upload Tool')
    LOGGER.info('\t\t----------------------------------\n\n')

    LOGGER.info('Space Key:\t%s', SPACE_KEY)

    # get the pages that are currently under the ancestor
    original_child_pages = {}
    direct_child_pages = get_direct_child_pages(ANCESTOR)
    for child in direct_child_pages:
        original_child_pages[child] = get_child_pages(child)

    LOGGER.info("child pages done")

    # upload everything under the ancestor
    root_ancestors = get_page_as_ancestor(ANCESTOR)
    active_pages = upload_folder(DOCUMENTATION_ROOT, root_ancestors)

    # for any pages with refs that could not be resolved,
    # revisit them and try again
    if len(RESOLVE_REFS_AGAIN) > 0:
        LOGGER.info('-- Attempting to resolve cross-references --')
        for page in RESOLVE_REFS_AGAIN:
            update_page_refs_only(page)

    # remove any pages that are no longer needed; any top-level
    # page under the ancestor, and its children, are spared; but
    # any children under any page that we have touched are fair
    # game to be removed
    for original_child_page in original_child_pages:
        if original_child_page not in active_pages:
            LOGGER.info("Sparing original page: %s", original_child_page)
        else:
            for child in original_child_pages[original_child_page]:
                if child not in active_pages:
                    if SIMULATE:
                        LOGGER.info('Original page with page id %s has no markdown file to '
                                    'update from, so it will be deleted.', child)
                    else:
                        delete_page(child)

    if SIMULATE:
        LOGGER.info("Simulate mode completed successfully.")
    else:
        LOGGER.info('Markdown Converter completed successfully.')


if __name__ == "__main__":
    main()

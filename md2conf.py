#!/usr/bin/python3
"""
# --------------------------------------------------------------------------------------------------
# Rittman Mead Markdown to Confluence Tool
# --------------------------------------------------------------------------------------------------
# Create or Update Atlas pages remotely using markdown files.
#
# --------------------------------------------------------------------------------------------------
# Usage: rest_md2conf.py markdown spacekey
# --------------------------------------------------------------------------------------------------
"""

import logging
import sys
import os
import re
import json
import collections
import mimetypes
import codecs
import argparse
import urllib
import webbrowser
import requests
import markdown

logging.basicConfig(level=logging.INFO, format='%(asctime)s - \
%(levelname)s - %(funcName)s [%(lineno)d] - \
%(message)s')
LOGGER = logging.getLogger(__name__)

# ArgumentParser to parse arguments and options
PARSER = argparse.ArgumentParser()
PARSER.add_argument('spacekey',
                    help="Confluence Space key for the page. If omitted, will use user space.")
PARSER.add_argument('-u', '--username', help='Confluence username if $CONFLUENCE_USERNAME not set.')
PARSER.add_argument('-p', '--apikey', help='Confluence API key if $CONFLUENCE_API_KEY not set.')
PARSER.add_argument('-o', '--orgname',
                    help='Confluence organisation if $CONFLUENCE_ORGNAME not set. '
                         'e.g. https://XXX.atlassian.net/wiki'
                         'If orgname contains a dot, considered as the fully qualified domain name.'
                         'e.g. https://XXX')
PARSER.add_argument('-t', '--attachment', nargs='+',
                    help='Attachment(s) to upload to page. Paths relative to the markdown file.')
PARSER.add_argument('-c', '--contents', action='store_true', default=False,
                    help='Use this option to generate a contents page.')
PARSER.add_argument('-g', '--nogo', action='store_true', default=False,
                    help='Use this option to skip navigation after upload.')
PARSER.add_argument('-n', '--nossl', action='store_true', default=False,
                    help='Use this option if NOT using SSL. Will use HTTP instead of HTTPS.')
PARSER.add_argument('-d', '--delete', action='store_true', default=False,
                    help='Use this option to delete the page instead of create it.')
PARSER.add_argument('-l', '--loglevel', default='INFO',
                    help='Use this option to set the log verbosity.')
PARSER.add_argument('-s', '--simulate', action='store_true', default=False,
                    help='Use this option to only show conversion result.')

ARGS = PARSER.parse_args()

# Assign global variables
try:
    # Set log level
    LOGGER.setLevel(getattr(logging, ARGS.loglevel.upper(), None))

    DOCUMENTATION_ROOT = '..\\dagrofa-merkur\\docs'
    DOCUMENTATION_TEMPLATE = 'template.md'
    LOG_FILE = 'logs\\logs.txt'

    SPACE_KEY = ARGS.spacekey
    USERNAME = os.getenv('CONFLUENCE_USERNAME', ARGS.username)
    API_KEY = os.getenv('CONFLUENCE_API_KEY', ARGS.apikey)
    ORGNAME = os.getenv('CONFLUENCE_ORGNAME', ARGS.orgname)
    NOSSL = ARGS.nossl
    DELETE = ARGS.delete
    SIMULATE = ARGS.simulate
    ATTACHMENTS = ARGS.attachment
    GO_TO_PAGE = not ARGS.nogo
    CONTENTS = ARGS.contents

    if USERNAME is None:
        LOGGER.error('Error: Username not specified by environment variable or option.')
        sys.exit(1)

    if API_KEY is None:
        LOGGER.error('Error: API key not specified by environment variable or option.')
        sys.exit(1)

    if SPACE_KEY is None:
        SPACE_KEY = '~%s' % (USERNAME)

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

except Exception as err:
    LOGGER.error('\n\nException caught:\n%s ', err)
    LOGGER.error('\nFailed to process command line arguments. Exiting.')
    sys.exit(1)


def convert_comment_block(html):
    """
    Convert markdown code bloc to Confluence hidden comment

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

    html = re.sub('\<\!\-\- START doctoc.*END doctoc \-\-\>', toc_tag, html, flags=re.DOTALL)

    return html


def strip_type(tag, tagtype):
    """
    Strips Note or Warning tags from html in various formats

    :param tag: tag name
    :param tagtype: tag type
    :return: modified tag
    """
    tag = re.sub('%s:\s' % tagtype, '', tag.strip(), re.IGNORECASE)
    tag = re.sub('%s\s:\s' % tagtype, '', tag.strip(), re.IGNORECASE)
    tag = re.sub('<.*?>%s:\s<.*?>' % tagtype, '', tag, re.IGNORECASE)
    tag = re.sub('<.*?>%s\s:\s<.*?>' % tagtype, '', tag, re.IGNORECASE)
    tag = re.sub('<(em|strong)>%s:<.*?>\s' % tagtype, '', tag, re.IGNORECASE)
    tag = re.sub('<(em|strong)>%s\s:<.*?>\s' % tagtype, '', tag, re.IGNORECASE)
    tag = re.sub('<(em|strong)>%s<.*?>:\s' % tagtype, '', tag, re.IGNORECASE)
    tag = re.sub('<(em|strong)>%s\s<.*?>:\s' % tagtype, '', tag, re.IGNORECASE)
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
    refs = re.findall('\n(\[\^(\d)\].*)|<p>(\[\^(\d)\].*)', html)

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

        page_info = collections.namedtuple('PageInfo', ['id', 'version', 'link'])
        page = page_info(page_id, version_num, link)
        return page

    return False


def get_child_page_ids(page_id):
    """
     Retrieve details of the child pages by page id

    :param page_id: page id
    :return: ids of child pages
    """
    LOGGER.info('\tRetrieving information of original child pages: %s', page_id)
    page_ids = get_child_pages_recursively(page_id)

    for page_id in page_ids:
        child_pages = get_child_pages_recursively(page_id)
        if child_pages:
            page_ids.extend(child_pages)

    return page_ids


def get_child_pages_recursively(page_id):
    url = '%s/rest/api/content/search?cql=parent=%s' % (CONFLUENCE_API_URL, urllib.parse.quote_plus(page_id))

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


# Scan for images and upload as attachments if found
def add_images(page_id, html, filepath):
    """
    Scan for images and upload as attachments if found

    :param page_id: Confluence page id
    :param html: html string
    :param filepath: markdown file full path
    :return: html with modified image reference
    """
    source_folder = os.path.dirname(os.path.abspath(filepath))

    for tag in re.findall('<img(.*?)\/>', html):
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
    contents_markup = contents_markup + '<ac:parameter ac:name="maxLevel">5</ac:parameter>\n' \
                                        '<ac:parameter ac:name="minLevel">1</ac:parameter>'
    contents_markup = contents_markup + '<ac:parameter ac:name="class">rm-contents</ac:parameter>\n' \
                                        '<ac:parameter ac:name="exclude"></ac:parameter>\n' \
                                        '<ac:parameter ac:name="type">list</ac:parameter>'
    contents_markup = contents_markup + '<ac:parameter ac:name="outline">false</ac:parameter>\n' \
                                        '<ac:parameter ac:name="include"></ac:parameter>\n' \
                                        '</ac:structured-macro>'

    html = contents_markup + '\n' + html
    return html


def add_attachments(page_id, files, filepath):
    """
    Add attachments for an array of files

    :param page_id: Confluence page id
    :param files: list of files to attach to the given Confluence page
    :param filepath: markdown file full path
    :return: None
    """
    source_folder = os.path.dirname(os.path.abspath(filepath))

    if files:
        for file in files:
            upload_attachment(page_id, os.path.join(source_folder, file), '')


def create_page(title, body, ancestors, filepath):
    """
    Create a new page

    :param title: confluence page title
    :param body: confluence page content
    :param ancestors: confluence page ancestor
    :param filepath: markdown file full path
    :return: created page id
    """
    LOGGER.info('Creating page...')

    url = '%s/rest/api/content/' % CONFLUENCE_API_URL

    session = requests.Session()
    session.auth = (USERNAME, API_KEY)
    session.headers.update({'Content-Type': 'application/json'})

    new_page = {'type': 'page', \
                'title': title, \
                'space': {'key': SPACE_KEY}, \
                'body': { \
                    'storage': { \
                        'value': body, \
                        'representation': 'storage' \
                        } \
                    }, \
                'ancestors': ancestors \
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

        img_check = re.search('<img(.*?)\/>', body)
        if img_check or ATTACHMENTS:
            LOGGER.info('\tAttachments found, update procedure called.')
            update_page(page_id, title, body, version, ancestors, ATTACHMENTS, filepath)
        else:
            if GO_TO_PAGE:
                webbrowser.open(link)
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
    LOGGER.info('Deleting page...')
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


def update_page(page_id, title, body, version, ancestors, attachments, filepath):
    """
    Update a page

    :param page_id: confluence page id
    :param title: confluence page title
    :param body: confluence page content
    :param version: confluence page version
    :param ancestors: confluence page ancestor
    :param attachments: confluence page attachments
    :param filepath: markdown file full path
    :return: None
    """
    LOGGER.info('Updating page...')

    # Add images and attachments
    body = add_images(page_id, body, filepath)
    add_attachments(page_id, attachments, filepath)

    url = '%s/rest/api/content/%s' % (CONFLUENCE_API_URL, page_id)

    session = requests.Session()
    session.auth = (USERNAME, API_KEY)
    session.headers.update({'Content-Type': 'application/json'})

    page_json = { \
        "id": page_id, \
        "type": "page", \
        "title": title, \
        "space": {"key": SPACE_KEY}, \
        "body": { \
            "storage": { \
                "value": body, \
                "representation": "storage" \
                } \
            }, \
        "version": { \
            "number": version + 1, \
            "minorEdit": True \
            }, \
        'ancestors': ancestors \
        }

    response = session.put(url, data=json.dumps(page_json))
    response.raise_for_status()

    if response.status_code == 200:
        data = response.json()
        link = '%s%s' % (CONFLUENCE_API_URL, data[u'_links'][u'webui'])

        LOGGER.info("Page updated successfully.")
        LOGGER.info('URL: %s', link)
        if GO_TO_PAGE:
            webbrowser.open(link)
    else:
        LOGGER.error("Page could not be updated.")


def get_attachment(page_id, filename):
    """
    Get page attachment

    :param page_id: confluence page id
    :param filename: attachment filename
    :return: attachment info in case of success, False otherwise
    """
    url = '%s/rest/api/content/%s/child/attachment?filename=%s' % (CONFLUENCE_API_URL, page_id, filename)

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
    Upload an attachement

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
        url = '%s/rest/api/content/%s/child/attachment/%s/data' % (CONFLUENCE_API_URL, page_id, attachment.id)
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
    read = read.replace('<details>', '')
    read = read.replace('</details>', '')
    read = read.replace('<summary>', '')
    read = read.replace('</summary>', '')
    return read


def get_html(filepath):
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
    LOGGER.debug('html: %s', html)

    return html


def add_note(html):
    warning = '<p>~!This is a generated file. Any modifications to it will be lost upon next update. Please use the documentation files in the project repository. !~</p>'
    html = warning + html
    return html


def get_title(filepath):
    with open(filepath, 'r') as mdfile:
        title = mdfile.readline().lstrip('#').strip()
        mdfile.seek(0)
    LOGGER.info('Title:\t\t%s', title)
    return title


def get_landing_page_doc_file(directory):
    root = os.path.abspath(DOCUMENTATION_ROOT)
    md_file = directory.split('\\')[-1] + '.md'
    return root + '\\' + md_file


def get_page_as_ancestor(page_id):
    return [{'type': 'page', 'id': page_id}]


def create_dir_landing_page(dir_landing_page_file, directory, ancestors):
    landing_page_title = get_title(dir_landing_page_file)
    parent_page = get_page(landing_page_title)
    landing_page_doc_file = get_landing_page_doc_file(directory)
    html = get_html(landing_page_doc_file)
    if SIMULATE:
        log_html(html)
        return []
    elif parent_page:
        update_page(parent_page.id, landing_page_title, html, parent_page.version, ancestors, [], landing_page_doc_file)
        page_as_ancestor = get_page_as_ancestor(parent_page.id)
    else:
        page_id = create_page(landing_page_title, html, ancestors, landing_page_doc_file)
        page_as_ancestor = get_page_as_ancestor(page_id)
    return page_as_ancestor


def log_html(html):
    log_file = open(LOG_FILE, 'a')
    log_file.write(html)


def get_subfolders_recursively(dirname):
    subfolders = [f.path for f in os.scandir(dirname) if f.is_dir()]
    for dirname in list(subfolders):
        subfolders.extend(get_subfolders_recursively(dirname))

    return subfolders


def create_dir_landing_page_recursively(dir_landing_page_file, directory):
    ancestor_landing_page_dir = os.path.abspath(os.path.join(directory, os.pardir))
    ancestor_landing_page_file = get_landing_page_doc_file(ancestor_landing_page_dir)
    ancestor_landing_page_title = get_title(ancestor_landing_page_file)
    ancestor_page = get_page(ancestor_landing_page_title)

    if ancestor_page:
        page_as_ancestor = create_dir_landing_page(dir_landing_page_file, directory, get_page_as_ancestor(ancestor_page.id))
    else:
        page_as_ancestor = create_dir_landing_page_recursively(ancestor_landing_page_file, ancestor_landing_page_dir)

    return page_as_ancestor


def main():
    """
    Main program

    :return:
    """
    LOGGER.info('\t\t----------------------------------')
    LOGGER.info('\t\tMarkdown to Confluence Upload Tool')
    LOGGER.info('\t\t----------------------------------\n\n')

    LOGGER.info('Space Key:\t%s', SPACE_KEY)

    doc_file = get_landing_page_doc_file(DOCUMENTATION_ROOT)
    doc_landing_page_title = get_title(doc_file)
    doc_landing_page = get_page(doc_landing_page_title)
    original_child_pages = []
    if doc_landing_page:
        original_child_pages.append(doc_landing_page_title)
        original_child_pages = get_child_page_ids(doc_landing_page.id)
    LOGGER.info('Original documentation pages before the tool has run:\t%s', original_child_pages)

    [delete_page(page_id) for page_id in original_child_pages]
    if DELETE:
        sys.exit(1)

    create_dir_landing_page(doc_file, DOCUMENTATION_ROOT, [])

    directories = get_subfolders_recursively(DOCUMENTATION_ROOT)

    for directory in directories:
        dir_landing_page_file = get_landing_page_doc_file(directory)
        dir_landing_as_ancestor = create_dir_landing_page_recursively(dir_landing_page_file, directory)

        for file in os.scandir(directory):
            if file.path.endswith('.md') and not (file.path.endswith(DOCUMENTATION_TEMPLATE) or file.path.endswith(dir_landing_page_file)):
                LOGGER.info('Markdown file:\t%s', file.name)
                title = get_title(file.path)

                LOGGER.info('Checking if Atlas page exists...')
                page = get_page(title)

                html = get_html(file.path)
                if SIMULATE:
                    log_html(html)
                else:
                    if page:
                        update_page(page.id, title, html, page.version, dir_landing_as_ancestor, ATTACHMENTS, file.path)
                    else:
                        create_page(title, html, dir_landing_as_ancestor, file.path)
                continue

    if SIMULATE:
        LOGGER.info("Simulate mode completed successfully.")
    else:
        LOGGER.info('Markdown Converter completed successfully.')


if __name__ == "__main__":
    main()

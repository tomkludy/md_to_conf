"""
# --------------------------------------------------------------------------------------------------
# Page APIs
# --------------------------------------------------------------------------------------------------
"""

import sys
import os
import tempfile
import re
import json
import collections
import mimetypes
import urllib
import urllib.parse
import requests

import common
from file_api import FILE_API
from child_pages import CHILD_PAGES
from page_cache import PAGE_CACHE

from globals import LOGGER
from globals import USERNAME
from globals import API_KEY
from globals import SPACE_KEY
from globals import CONFLUENCE_API_URL
from globals import SIMULATE
from globals import ANCESTOR


class _PageApi:
    """
    APIs for dealing with pages in Confluence
    """

    __IMAGE_LINK_PAGES = {}

    def __add_images(self, page_id, html, filepath):
        """
        Scan for images and upload as attachments or child pages if found

        :param page_id: Confluence page id
        :param html: html string
        :param filepath: markdown file full path
        :return: html with modified image reference
        """
        source_folder = os.path.dirname(os.path.abspath(filepath))

        # <img/> tags turn into attachments
        for tag in re.findall('<img(.*?)/>', html):
            orig_rel_path = re.search('src="(.*?)"', tag).group(1)
            alt_text = re.search('alt="(.*?)"', tag).group(1)
            rel_path = urllib.parse.unquote(orig_rel_path)
            abs_path = os.path.join(source_folder, rel_path)
            basename = os.path.basename(rel_path)
            self.__upload_attachment(page_id, abs_path, alt_text)
            if re.search('http.*', rel_path) is None:
                if CONFLUENCE_API_URL.endswith('/wiki'):
                    html = html.replace('%s' % (orig_rel_path),
                                        '/wiki/download/attachments/%s/%s' % (page_id, basename))
                else:
                    html = html.replace('%s' % (orig_rel_path),
                                        '/download/attachments/%s/%s' % (page_id, basename))

        # <a href="<image>">[Name]</a> turns into a sub-page
        ancestors = common.get_page_as_ancestor(page_id)
        for ref in re.findall(r'<a href=\"([^\"]+)\">([^<]+)</a>', html):
            if not ref[0].startswith(('http', '/')) and ref[0].endswith('.png'):
                dirname = os.path.abspath(os.path.dirname(filepath))
                rel_image_from_page = os.path.join(dirname, ref[0])
                image = os.path.normpath(rel_image_from_page)
                alt = ref[1]
                if image in self.__IMAGE_LINK_PAGES:
                    page = self.__IMAGE_LINK_PAGES[image]
                else:
                    file = tempfile.NamedTemporaryFile(mode='w', delete=False)
                    title = urllib.parse.unquote(os.path.basename(image))
                    title = "%s - Diagram" % (os.path.splitext(title)[0])
                    file.write('# %s\n' % title)
                    temp_dirname = os.path.abspath(os.path.dirname(file.name))
                    rel_image_from_temp = os.path.relpath(image, temp_dirname)
                    file.write('![%s](%s)\n' % (alt, rel_image_from_temp))
                    file.close()
                    title = FILE_API.get_title(file.name)
                    subhtml = FILE_API.get_html(file.name)
                    self.create_or_update_page(title, subhtml, ancestors, file.name)
                    os.remove(file.name)
                    page = PAGE_CACHE.get_page(title)
                    self.__IMAGE_LINK_PAGES[image] = page
                CHILD_PAGES.mark_page_active(page.id)
                html = html.replace(ref[0], page.link)

        return html


    def create_or_update_page(self, title, body, ancestors, filepath):
        """
        Create a new page

        :param title: confluence page title
        :param body: confluence page content
        :param ancestors: confluence page ancestor
        :param filepath: markdown file full path
        :return: created or updated page id
        """
        page = PAGE_CACHE.get_page(title)
        if page:
            return self.update_page(page.id, title, body, page.version, ancestors, filepath)
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

                # label the page
                self.__label_page(page_id)

                img_check = re.search(r'<img(.*?)\/>', body)
                if img_check:
                    LOGGER.info('Attachments found, update procedure called.')
                    return self.update_page(page_id, title, body, version, ancestors, filepath)
                else:
                    return page_id
            else:
                LOGGER.error('Could not create page.')
                sys.exit(1)


    def update_page(self, page_id, title, body, version, ancestors, filepath):
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
        PAGE_CACHE.forget_page(title)

        # Add images and attachments
        body = self.__add_images(page_id, body, filepath)

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


    def __label_page(self, page_id):
        """
        Attach a label to the page to indicate it was auto-generated
        """
        LOGGER.info("Labeling page %s", page_id)
        session = requests.Session()
        session.auth = (USERNAME, API_KEY)
        session.headers.update({'Content-Type': 'application/json'})

        url = '%s/rest/api/content/%s/label' % (CONFLUENCE_API_URL, page_id)

        page_json = [{ "name": "md_to_conf" }]

        response = session.post(url, data=json.dumps(page_json))
        response.raise_for_status()



    def __get_attachment(self, page_id, filename):
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


    def __upload_attachment(self, page_id, file, comment):
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

        attachment = self.__get_attachment(page_id, filename)
        if attachment:
            url = '%s/rest/api/content/%s/child/attachment/%s/data' % \
                (CONFLUENCE_API_URL, page_id, attachment.id)
        else:
            url = '%s/rest/api/content/%s/child/attachment/' % (CONFLUENCE_API_URL, page_id)

        session = requests.Session()
        session.auth = (USERNAME, API_KEY)
        session.headers.update({'X-Atlassian-Token': 'no-check'})

        LOGGER.info('Uploading attachment %s...', filename)

        response = session.post(url, files=file_to_upload)
        response.raise_for_status()

        return True


    def create_dir_landing_page(self, dir_landing_page_file, ancestors):
        """
        Create landing page for a directory

        :param dir_landing_page_file: the raw markdown file to use for landing page html generation
        :param ancestors: the ancestor pages of the new landing page
        :return: the created landing page id
        """
        landing_page_title = FILE_API.get_title(dir_landing_page_file)
        html = FILE_API.get_html(dir_landing_page_file)
        if SIMULATE:
            common.log_html(html, landing_page_title)
            return []

        return self.create_or_update_page(landing_page_title, html, \
                                          ancestors, dir_landing_page_file)


    def create_trash(self):
        """
        Create a __ORPHAN__ folder under the root ancestor
        """
        file = tempfile.NamedTemporaryFile(mode='w', delete=False)
        file.write('''# __ORPHAN__

<p>~!Files under this folder are NOT present in the source repo and and were moved here in lieu of deletion.!~</p>

If these files are no longer needed, it is safe to delete this folder.
''')
        file.close()
        title = FILE_API.get_title(file.name)
        html = FILE_API.get_html(file.name)
        root_ancestors = common.get_page_as_ancestor(ANCESTOR)
        page_id = self.create_or_update_page(title, html, root_ancestors, file.name)
        return page_id


PAGE_API = _PageApi()

"""
# --------------------------------------------------------------------------------------------------
# APIs to get child pages
# --------------------------------------------------------------------------------------------------
"""

import urllib
import urllib.parse
import json

import common

from globals import LOGGER
from globals import CONFLUENCE_API_URL
from globals import ANCESTOR
from globals import SIMULATE

class _ChildPageTracker:
    """
    Track child pages under the ANCESTOR
    """

    __ORIGINAL_CHILD_PAGES = {}
    __ACTIVE_PAGES = []
    __CHILD_PAGES_CACHE = {}

    def track_child_pages(self):
        """
        Start tracking child pages under the ANCESTOR
        """
        # get the pages that are currently under the ancestor
        direct_child_pages = self.__get_direct_child_pages(ANCESTOR)
        for child in direct_child_pages:
            self.__ORIGINAL_CHILD_PAGES[child] = self.__get_child_pages(child)


    def mark_page_active(self, page):
        """
        Mark pages as "active"; meaning, the page has been
        created or updated based on the upload process

        :param page: Page which is known to be active
        """
        if not page in self.__ACTIVE_PAGES:
            self.__ACTIVE_PAGES.append(page)


    def trash_needed(self):
        """
        Return True if a "trash can" folder is needed
        """
        for original_child_page in self.__ORIGINAL_CHILD_PAGES:
            if original_child_page in self.__ACTIVE_PAGES:
                for child in self.__ORIGINAL_CHILD_PAGES[original_child_page]:
                    if child not in self.__ACTIVE_PAGES:
                        return True
        return False



    def trim_child_pages(self, trash_ancestor):
        """
        Trim (delete) any child pages under the "active"
        children of the ANCESTOR which are not "active"
        """
        # remove any pages that are no longer needed; any top-level
        # page under the ancestor, and its children, are spared; but
        # any children under any page that we have touched are fair
        # game to be removed
        for original_child_page in self.__ORIGINAL_CHILD_PAGES:
            if original_child_page not in self.__ACTIVE_PAGES:
                LOGGER.info("Sparing original page: %s", original_child_page)
            else:
                for child in self.__ORIGINAL_CHILD_PAGES[original_child_page]:
                    if child not in self.__ACTIVE_PAGES:
                        if SIMULATE:
                            LOGGER.info('Original page with page id %s has no markdown file to '
                                        'update from, so it will be deleted.', child)
                        else:
                            self.__delete_page(child, trash_ancestor)


    def __get_child_pages(self, page_id):
        """
        Retrieve details of the child pages by page id

        :param page_id: page id
        :return: the ids of all the child pages
        """
        if page_id in self.__CHILD_PAGES_CACHE:
            return self.__CHILD_PAGES_CACHE[page_id]

        LOGGER.info('Retrieving information of original child pages: %s', page_id)
        page_ids = self.__get_direct_child_pages(page_id)

        for page_id in page_ids:
            child_pages = self.__get_child_pages(page_id)
            if child_pages:
                page_ids = page_ids + list(set(child_pages) - set(page_ids))

        self.__CHILD_PAGES_CACHE[page_id] = page_ids
        return page_ids


    def __get_direct_child_pages(self, page_id):
        """
        Retrieve every direct child page id

        :param page_id: page id
        :return: ids of immediate child pages
        """
        url = '%s/rest/api/content/search?cql=parent=%s' % \
            (CONFLUENCE_API_URL, urllib.parse.quote_plus(page_id))

        response = common.make_request_get(url)
        data = response.json()
        LOGGER.debug("data: %s", str(data))

        page_ids = []
        for result in data[u'results']:
            page_ids.append(result[u'id'])

        return page_ids


    def __delete_page(self, page_id, trash_ancestor):
        """
        Delete a page by moving it to the orphan folder

        :param page_id: confluence page id
        :return: None
        """
        LOGGER.info('Moving page %s to ORPHAN...', page_id)
        url = '%s/rest/api/content/%s?expand=version' % (
            CONFLUENCE_API_URL, page_id)

        response = common.make_request_get(url)
        data = response.json()
        LOGGER.debug("data: %s", str(data))

        page_id = data[u'id']
        version = data[u'version'][u'number']
        title = data[u'title']
        ancestors = common.get_page_as_ancestor(trash_ancestor)

        url = '%s/rest/api/content/%s' % (CONFLUENCE_API_URL, page_id)
        page_json = {
            "id": page_id,
            "type": "page",
            "title": title,
            "version": {
                "number": version + 1,
                "minorEdit": True
            },
            'ancestors': ancestors
        }
        LOGGER.debug("data: %s", json.dumps(page_json))

        common.make_request_put(url, data=json.dumps(page_json))


CHILD_PAGES = _ChildPageTracker()

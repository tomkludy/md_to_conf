#!/usr/bin/env python3
"""
# --------------------------------------------------------------------------------------------------
# Reference resolvers
# --------------------------------------------------------------------------------------------------
"""

import os
import re
import collections
import urllib
import urllib.parse

from globals import LOGGER
from globals import SPACE_KEY
from globals import CONFLUENCE_API_URL
import common


class _PageCache:
    """
    Reference resolver functions
    """

    __RESOLVE_REFS_AGAIN = []
    __CACHED_PAGE_INFO = {}

    def resolve_refs(self, html, filepath):
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
                    page = self.get_page(title)
                    if page:
                        html = html.replace(ref[0], "href=\"" + page.link + "\"")
                    else:
                        if not filepath in self.__RESOLVE_REFS_AGAIN:
                            self.__RESOLVE_REFS_AGAIN.append(filepath)
        return html


    def get_page(self, title):
        """
        Retrieve page details by title

        :param title: page tile
        :return: Confluence page info
        """
        if title in self.__CACHED_PAGE_INFO:
            return self.__CACHED_PAGE_INFO[title]

        LOGGER.info('Retrieving page information: %s', title)
        url = '%s/rest/api/content?title=%s&spaceKey=%s' \
              '&expand=version,ancestors,metadata.labels,body.storage' \
              % (CONFLUENCE_API_URL, urllib.parse.quote_plus(title), SPACE_KEY)

        response = common.make_request_get(url)
        data = response.json()
        LOGGER.debug("data: %s", str(data))

        if len(data[u'results']) >= 1:
            data = data[u'results'][0]
            page_id = data[u'id']
            version_num = data[u'version'][u'number']
            link = '%s%s' % (CONFLUENCE_API_URL, data[u'_links'][u'webui'])
            ancestor = data[u'ancestors'][-1][u'id']
            labels = map(lambda r: r[u'name'],
                         data[u'metadata'][u'labels'][u'results'])
            body = data[u'body'][u'storage'][u'value']

            # These properties do not round-trip; confluence adds them, so strip them out
            body = re.sub(' ac:schema-version="[^"]+"', '', body)
            body = re.sub(' ac:macro-id="[^"]+"', '', body)
            # Confluence replaces some quotes (but not all) with xml quotes
            body = re.sub('&quot;', '"', body)

            title = data[u'title']

            page_info = collections.namedtuple('PageInfo',
                            ['id', 'version', 'link', 'ancestor', 'labels', 'body', 'title'])
            page = page_info(page_id, version_num, link, ancestor, labels, body, title)
            self.__CACHED_PAGE_INFO[title] = page
            return page

        return False


    def is_page_unowned(self, title):
        page = self.get_page(title)
        if not page:
            return False
        return not 'md_to_conf' in page.labels


    def forget_page(self, title):
        """
        Drop a page from the cache; need to call this if a page
        has been updated, so that its new metadata can be requeried
        """
        self.__CACHED_PAGE_INFO.pop(title, None)


    def get_refs_to_resolve_again(self):
        return self.__RESOLVE_REFS_AGAIN


PAGE_CACHE = _PageCache()

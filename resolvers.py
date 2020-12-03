#!/usr/bin/env python3
"""
# --------------------------------------------------------------------------------------------------
# Reference resolvers
# --------------------------------------------------------------------------------------------------
"""

from globals import LOGGER
from page_api import PAGE_API
import common
from file_api import FILE_API
from page_cache import PAGE_CACHE


class _Resolvers:
    """
    Reference resolver functions
    """

    def resolve_missing_refs(self):
        """
        Resolve missing refs
        """
        refs_to_resolve = PAGE_CACHE.get_refs_to_resolve_again()
        if len(refs_to_resolve) > 0:
            LOGGER.info('-- Attempting to resolve cross-references --')
            for page in refs_to_resolve:
                self.__update_page_refs_only(page)


    def __update_page_refs_only(self, filepath):
        """
        Update refs on a page without changing anything else about it

        :param filepath: markdown file full path
        """
        title = FILE_API.get_title(filepath)
        LOGGER.info('Updating page refs %s...', title)

        # update the page
        page = PAGE_CACHE.get_page(title)
        html = FILE_API.get_html(filepath)
        version = page.version
        ancestors = common.get_page_as_ancestor(page.ancestor)

        LOGGER.info('.. title: %s .. version: %d .. ancestor: %s ..', title, version, page.ancestor)

        PAGE_API.update_page(page.id, title, html, version, ancestors, filepath)


RESOLVERS = _Resolvers()

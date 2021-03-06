"""
# --------------------------------------------------------------------------------------------------
# APIs that deal with local files
# --------------------------------------------------------------------------------------------------
"""

import os
import tempfile
import codecs
from pathlib import Path
import hashlib
import markdown

from globals import LOGGER
from globals import LOG_FILE
from globals import LOG_HTML
from globals import CONTENTS

import macros
from page_cache import PAGE_CACHE

class _FileApi:
    """
    APIS that deal with local files
    """

    __TITLE_CACHE_BY_FILE = {}
    __SHA_HASH_BY_FILE = {}

    def get_html(self, filepath):
        """
        Generate html from md file

        :param filepath: the file to translate to html
        :return: html translation
        """
        with codecs.open(filepath, 'r', 'utf-8') as mdfile:
            read = mdfile.read()
            read = macros.remove_collapsible_headings(read)
            html = markdown.markdown(read, extensions=['markdown.extensions.tables',
                                                    'markdown.extensions.fenced_code',
                                                    'markdown.extensions.sane_lists'])
        html = '\n'.join(html.split('\n')[1:])
        html = macros.add_note(html)
        html = macros.convert_info_macros(html)
        html = macros.convert_comment_block(html)
        html = macros.convert_code_block(html)
        html = macros.remove_empty_list_items(html)
        if CONTENTS:
            html = macros.add_contents(html)

        html = macros.process_refs(html)
        html = PAGE_CACHE.resolve_refs(html, filepath)
        if LOG_HTML:
            title = self.get_title(filepath)
            html_log_file = open(os.path.dirname(LOG_FILE) + title + '.html', 'w+')
            html_log_file.write('<h1>' + title + '</h1>')
            html_log_file.write(html)
        else:
            LOGGER.debug('file: %s\n\nhtml: %s\n\n', filepath, html)

        return html


    def get_title(self, filepath):
        """
        Returns confluence page title extracted from the markdown file

        :param filepath: full path to  markdown file
        :return: confluence page title
        """
        if filepath in self.__TITLE_CACHE_BY_FILE:
            return self.__TITLE_CACHE_BY_FILE[filepath]
        with open(filepath, 'r') as mdfile:
            title = mdfile.readline().lstrip('#').strip()
            mdfile.seek(0)

        basetitle = title
        i = 0
        while (title in self.__TITLE_CACHE_BY_FILE.values()) or \
              (PAGE_CACHE.is_page_unowned(title)):
            i += 1
            title = '%s (%d)' % (basetitle, i)

        self.__TITLE_CACHE_BY_FILE[filepath] = title

        LOGGER.info('Title: %s', title)
        return title


    def get_landing_page_doc_file(self, directory):
        """
        Get full file path to the markdown file corresponding to the directory

        :param directory: the directory
        :return: full path to corresponding landing page markdown file
        """

        # if the directory contains a README.md, use that
        file = Path(directory) / 'README.md'
        if os.path.exists(file):
            return file

        # fall back on creating a file containing only the directory name
        file = tempfile.NamedTemporaryFile(mode='w', delete=False)
        file.write('# ' + os.path.basename(directory) + '\n')
        file.close()
        return Path(file.name)


    def get_sha_hash(self, file):
        """
        Get the SHA hash of a file's contents

        :param file: file to hash the contents of
        """
        if file in self.__SHA_HASH_BY_FILE:
            return self.__SHA_HASH_BY_FILE[file]

        sha256 = hashlib.sha256()
        with open(file, 'rb') as handle:
            while True:
                data = handle.read(65536)
                if not data:
                    break
                sha256.update(data)

        digest = sha256.hexdigest()
        self.__SHA_HASH_BY_FILE[file] = digest
        return digest


FILE_API = _FileApi()

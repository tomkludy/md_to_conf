#!/usr/bin/env python3
"""
# --------------------------------------------------------------------------------------------------
# Rittman Mead Markdown to Confluence Tool
# --------------------------------------------------------------------------------------------------
# Create or Update Atlas pages remotely using markdown files.
"""

import os

from globals import LOGGER
from globals import DOCUMENTATION_ROOTS
from globals import SPACE_KEY
from globals import ANCESTOR
from globals import SIMULATE

import common
from file_api import FILE_API
from resolvers import RESOLVERS
from page_api import PAGE_API
from child_pages import CHILD_PAGES


def upload_folder(directory, ancestors):
    """
    Upload everything under a folder, recursively

    :param directory: folder to upload
    :param ancestors: parent page in ancestors format
    """
    LOGGER.info('Folder: %s', directory)

    # there must be at least one .md file under this folder or a
    # subfolder in order for us to proceed with processing it
    if not common.does_path_contain(directory, lambda file : os.path.splitext(file)[1] == '.md'):
        LOGGER.info('Skipping folder; no files found')
        return

    # Make sure there is a landing page for the directory
    doc_file = FILE_API.get_landing_page_doc_file(directory)
    dir_landing_page_id = PAGE_API.create_dir_landing_page(doc_file, ancestors)
    CHILD_PAGES.mark_page_active(dir_landing_page_id)
    dir_landing_as_ancestors = common.get_page_as_ancestor(dir_landing_page_id)

    # Walk through all other .md files in this directory and upload them all with
    # the landing page as its ancestor
    for file in os.scandir(directory):
        if file.is_file() and os.path.splitext(file)[1] == '.md':
            if os.path.normpath(file.path) != os.path.normpath(doc_file):
                LOGGER.info('Markdown file: %s', file.name)
                title = FILE_API.get_title(file.path)
                html = FILE_API.get_html(file.path)

                if SIMULATE:
                    common.log_html(html, title)
                else:
                    page_id = \
                        PAGE_API.create_or_update_page(title, html, \
                            dir_landing_as_ancestors, file.path)
                    CHILD_PAGES.mark_page_active(page_id)

    # Walk through all subdirectories and recursively upload them,
    # using this directory's landing page as the ancestor for them
    for folder in os.scandir(directory):
        if folder.is_dir():
            upload_folder(folder.path, dir_landing_as_ancestors)


def main():
    """
    Main program

    :return:
    """
    LOGGER.info('----------------------------------')
    LOGGER.info('Markdown to Confluence Upload Tool')
    LOGGER.info('----------------------------------')

    LOGGER.info('Space Key: %s', SPACE_KEY)

    CHILD_PAGES.track_child_pages()

    # upload everything under the ancestor
    root_ancestors = common.get_page_as_ancestor(ANCESTOR)

    for root in DOCUMENTATION_ROOTS:
        upload_folder(root, root_ancestors)

    # for any pages with refs that could not be resolved,
    # revisit them and try again
    RESOLVERS.resolve_missing_refs()

    if CHILD_PAGES.trash_needed():
        trash = PAGE_API.create_trash()
        CHILD_PAGES.trim_child_pages(trash)

    if SIMULATE:
        LOGGER.info("Simulate mode completed successfully.")
    else:
        LOGGER.info('Markdown Converter completed successfully.')


if __name__ == "__main__":
    main()

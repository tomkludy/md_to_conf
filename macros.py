"""
# --------------------------------------------------------------------------------------------------
# Special markdown conversions to Confluence macros
# --------------------------------------------------------------------------------------------------
"""

import re

from globals import NOTE


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
                clean_tag = _strip_type(quote, 'Note')
                macro_tag = clean_tag.replace('<p>', note_tag).replace('</p>', close_tag).strip()
            elif warning:
                clean_tag = _strip_type(quote, 'Warning')
                macro_tag = clean_tag.replace('<p>', warning_tag).replace('</p>', close_tag).strip()
            else:
                macro_tag = quote.replace('<p>', info_tag).replace('</p>', close_tag).strip()

            html = html.replace('<blockquote>%s</blockquote>' % quote, macro_tag)

    # Convert doctoc to toc confluence macro
    html = _convert_doctoc(html)

    return html


def _convert_doctoc(html):
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


def _strip_type(tag, tagtype):
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
    tag = _upper_chars(tag, [string_start.end()])
    return tag


def _upper_chars(string, indices):
    """
    Make characters uppercase in string

    :param string: string to modify
    :param indices: character indice to change to uppercase
    :return: uppercased string
    """
    upper_string = "".join(c.upper() if i in indices else c for i, c in enumerate(string))
    return upper_string

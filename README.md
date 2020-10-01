# Documentation
## Markdown to Confluence Converter

A script to import every markdown document under the dagrofa-merkur/docs folder into Confluence.
It handles inline images as well as code blocks.
Also there is support for some custom markdown tags for use with commonly used Confluence macros.

Each file will be converted into HTML or Confluence storage markup when required.
Then a page will be created or updated in the space.
The hierarchy of the Confluence pages will mirror the folder structure under docs.
Every folder has to have a markdown file under docs with the same name as the folder, to allow generating a corresponding page in the hierarchy.
If a file is deleted, then running the tool will also remove the Confluence page.
When a file is moved, then it takes about 24 hours for Confluence to rebuild the ancestor tree, so the change does not show up immediately.

### Configuration

[Download](https://github.com/rittmanmead/md_to_conf)

### Requirements

Python 3.6+

#### Python venv

The project code and dependencies can be used based on python virtualenv.

Create a new python virtualenv:

```less
> python3 -m venv venv
```

Make the virtualenv active:

```less
> source venv/bin/activate
```

#### Dependencies

Required python dependencies can be installed using:

```less
pip3 install -r requirements.txt
```

#### Environment Variables

To use it, you will need your Confluence username, API key and organisation name.
To generate an API key go to [https://id.atlassian.com/manage/api-tokens](https://id.atlassian.com/manage/api-tokens).

You will also need the organization name that is used in the subdomain.
For example the URL: `https://fawltytowers.atlassian.net/wiki/` would indicate an organization name of **fawltytowers**.

If the organization name contains a dot, it will be considered as a Fully Qualified Domain Name.
For example the URL: `https://fawltytowers.mydomain.com/` would indicate an organization name of **fawltytowers.mydomain.com**.

These can be specified at runtime or set as Confluence environment variables
(e.g. add to your `~/.profile` or `~/.bash_profile` on Mac OS):

``` bash
export CONFLUENCE_USERNAME='basil'
export CONFLUENCE_API_KEY='abc123'
export CONFLUENCE_ORGNAME='fawltytowers'
```

On Windows, this can be set via system properties.

### Use

#### Basic

The minimum accepted parameters are the username, the API key, the organisation name as well as the Confluence space key you wish to upload to. 
Mandatory Confluence parameters can also be set here if not already set as environment variables:

* **-u** **--username**: Confluence User
* **-p** **--apikey**: Confluence API Key
* **-o** **--orgname**: Confluence Organisation

```less
python3 md2conf.py Test-Space --username your.username@aliz.ai --orgname sgjira
```

Use **-h** to view a list of all available options.

#### Other Uses

Use **-a** or **--ancestor** to specify a parent page by its id, under which every other page will be created or updated.

Use **-d** or **--delete** to delete pages that are under the parent folder specified by the **--ancestor** parameter.

Use **-c** or **--contents** to generate a contents page.

Use **-n** or **--nossl** to specify a non-SSL url, i.e. **<http://>** instead of **<https://>**.

Use **-l** or **--loglevel** to specify a different logging level, i.e **DEBUG**.

Use **-s** or **--simulate** to stop processing before interacting with confluence API, i.e. only converting the markdown documents to confluence format and writing the html to a log file.

### Markdown

The original markdown to HTML conversion is performed by the Python **markdown** library.
Additionally, the page name is taken from the first line of each markdown file, usually assumed to be the title.
In the case of this document, the page would be called: **Documentation**.

Standard markdown syntax for images and code blocks will be automatically converted.
The images are uploaded as attachments and the references updated in the HTML.
The code blocks will be converted to the Confluence Code Block macro and also supports syntax highlighting.

### Doctoc

If present, what is between the [doctoc](https://github.com/thlorenz/doctoc) anchor format:

```less
<!-- START doctoc ...
...
... END doctoc -->
```

will be replaced by confluence "toc" macro leading to something like:

```html
<h2>Table of Content</h2>
<p>
    <ac:structured-macro ac:name="toc">
      <ac:parameter ac:name="printable">true</ac:parameter>
      <ac:parameter ac:name="style">disc</ac:parameter>
      <ac:parameter ac:name="maxLevel">7</ac:parameter>
      <ac:parameter ac:name="minLevel">1</ac:parameter>
      <ac:parameter ac:name="type">list</ac:parameter>
      <ac:parameter ac:name="outline">clear</ac:parameter>
      <ac:parameter ac:name="include">.*</ac:parameter>
    </ac:structured-macro>
    </p>
```

#### Information, Note and Warning Macros

> **Warning:** Any blockquotes used will implement an information macro. This could potentially harm your formatting.

Block quotes in Markdown are rendered as information macros.

```less
> This is an info
```

![macros](images/infoMacro.png)

```less
> Note: This is a note
```

![macros](images/noteMacro.png)

```less
> Warning: This is a warning
```

![macros](images/warningMacro.png)

Alternatively, using a custom Markdown syntax also works:

```less
~?This is an info.?~

~!This is a note.!~

~%This is a warning.%~
```

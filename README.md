# Documentation
## Markdown to Confluence Converter

A script to import every markdown document under a specified folder into Confluence.
It handles inline images as well as code blocks.
Also there is support for some custom markdown tags for use with commonly used Confluence macros.

Each file will be converted into HTML or Confluence storage markup when required.
Then a page will be created or updated in the space.
The hierarchy of the Confluence pages will mirror the folder structure under docs.
Every folder has to have a markdown file under docs with the same name as the folder, to allow generating a corresponding page in the hierarchy.
If a file is deleted, then running the tool will also remove the Confluence page.
When a file is moved, then it takes about 24 hours for Confluence to rebuild the ancestor tree, so the change does not show up immediately.

### Use

#### Prerequisites

Windows:
* [Windows Subsystem for Linux 2 (WSL2)](https://docs.microsoft.com/en-us/windows/wsl/install-win10)
* [Docker Desktop](https://docker.com)

macOS:
* [Docker Desktop](https://docker.com)

Linux:
* [Docker Engine](https://docker.com)

#### Set up authentication

You will need your Confluence username, and either your password or an API key.
To generate an API key go to [https://id.atlassian.com/manage/api-tokens](https://id.atlassian.com/manage/api-tokens).

These can be set as command-line parameters; however, it is recommended that these instead should be set in a `confluence.env` file and passed into the `docker run --env-file confluence.env ...` command.  The `confluence.env` file should then be excluded from checking into source control in order to keep the credentials secret.  This also prevents the credentials from appearing in your shell history.

Additionally, you will need to know your organization name.
* If you are using Confluence Cloud, you will need the organization name that is used in the subdomain.
For example, if you normally access the URL: `https://fawltytowers.atlassian.net/wiki/` then the organization name is **fawltytowers**.
* If you are using Confluence On-Prem, you will need the Fully Qualified Domain Name of your server.
For example, if you normally access the URL: `https://fawltytowers.mydomain.com/` then the organization name is **fawltytowers.mydomain.com**.

The `confluence.env` file should look like:
``` bash
CONFLUENCE_USERNAME='basil'
CONFLUENCE_API_KEY='abc123'
CONFLUENCE_ORGNAME='fawltytowers`
```

#### Additional requirements

Within Confluence, you will need to know a parent page ID under which to publish the pages that are uploaded.  Finding this in the Confluence web UI can be a bit tricky; here's how you can do it:

1. Navigate to the page that you want to be the root page in your browser
2. Click the "three dots" menu near the upper right of the page
3. Right-click and _Copy Link_ (don't left-click) the "Page History" link; this should be something like `https://fawltytowers.mydomain.com/pages/viewpreviousversions.action?pageId=1234567890`
4. Extract the `pageId` query parameter; in this example it is **1234567890**

### Use

#### Basic

The minimum accepted parameters are:

* The authentication parameters, preferably contained within a `.env` file (see above)
* The folder containing .md files to upload; this must be mapped into the container as a volume at the `/publish` mount point
* The Confluence space key you wish to upload to
* The ancestor page id, under which all files will be uploaded

```bash
docker run --rm \
    --env-file confluence.env `# authentication parameters in confluence.env file` \
    -v $(cwd):/publish        `# publishes current working directory and subdirectories` \
    tomkludy/md_to_conf \
    Test-Space                `# Confluence space key to publish to` \
    -a 1234567890             `# ancestor page id`
```

#### Command line arguments

|  | Parameter | Usage |
|-|-|-|
| &#8209;u | &#8209;&#8209;username | *Required*. Confluence username if `CONFLUENCE_USERNAME` is not set in the environment file. |
| &#8209;p | &#8209;&#8209;apikey | *Required*. Confluence password or API key if `CONFLUENCE_API_KEY` is not set in the environment file. |
| &#8209;o | &#8209;&#8209;orgname | *Required*. Confluence organization name if `CONFLUENCE_ORGNAME` is not set in the environment file.  If orgname contains a dot, it will be considered as the fully qualified domain name. |
| &#8209;a | &#8209;&#8209;ancestor | *Required*. The id of the parent page under which every other page will be created or updated. |
|  | &#8209;&#8209;note | Specifies a note to prepend on generated html pages.  Useful to indicate to the user that the page is generated. |
| &#8209;n | &#8209;&#8209;nossl | If specified, will use HTTP instead of HTTPS. |
| &#8209;l | &#8209;&#8209;loglevel | Set the log verbosity.  Default: `INFO` |
| &#8209;s | &#8209;&#8209;simulate | Only show conversion result, without uploading. |

> Note: There are some additional undocumented options available, which may be complex to use from within docker.  Use `docker run --rm tomkludy/md_to_conf -h` to view a list of all available options.

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

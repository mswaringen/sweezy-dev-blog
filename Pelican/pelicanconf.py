AUTHOR = 'Mark Swaringen'
SITENAME = 'sweezy.dev'
SITEURL = ""

PATH = "content"

TIMEZONE = 'Europe/Lisbon'
AUTHOR_SAVE_AS = ''
# DISPLAY_CATEGORIES_ON_MENU = False

DEFAULT_LANG = 'en'

THEME = "simple"
## more style sheet URLS - https://www.paulox.net/2023/11/30/pelican-4.9-classless-simple-theme/

# STYLESHEET_URL = "https://cdn.simplecss.org/simple.min.css"
# STYLESHEET_URL = "https://cdn.jsdelivr.net/npm/@exampledev/new.css@1.1.2/new.min.css"
# STYLESHEET_URL = "https://cdn.jsdelivr.net/npm/water.css@2/out/water.min.css"
STYLESHEET_URL = "https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.classless.min.css"

# Feed generation is usually not desired when developing
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

# Blogroll
LINKS = (
    ("Pelican", "https://getpelican.com/"),
    ("Python.org", "https://www.python.org/"),
    ("Jinja2", "https://palletsprojects.com/p/jinja/"),
    ("You can modify those links in your config file", "#"),
)

# Social widget
SOCIAL = (
    ("You can add links in your config file", "#"),
    ("Another social link", "#"),
)

GITHUB_URL = "https://github.com/mswaringen"

DEFAULT_PAGINATION = 10

# Uncomment following line if you want document-relative URLs when developing
# RELATIVE_URLS = True
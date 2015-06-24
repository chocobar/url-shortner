#!/usr/bin/env python

import web
import shelve
import time
import re
import hashlib
from random import choice
import base64
import urllib2
import pickle
from signal import signal, SIGQUIT, SIGINT, SIGTERM
import os

SHELVE_FILENAME =  'shelfshorturl-v8.bg'
SERVICE_URL = "localhost"
LENGTH = 4
STATIC_DIR = "/static"
PICKLE_FILE = "url-logger.pkl"
REDIRECT_PREFIX = "r"
SHRINK_PATH = "shrink"

urls = (
    "/",                                "Admin",
    "/done/(.*)",                       "AdminDone",
    "/favicon.ico",                     "Favicon",
    "/log",                             "ListUrl",
    "/" + SHRINK_PATH,                  "Shrink",
    "/" + REDIRECT_PREFIX + "/(.*)",    "RedirectToOthers",
)

#Messages
HOME_MESSAGE = '''Welcome to URL shortenner. Please go to /admin to get controls'''
FAIL_MESSAGE = 'Redirection failed, verify your link...'  # Messages

TERMSIGS = (SIGQUIT, SIGINT, SIGTERM,)

#first run requires a logger to be defined.
#logger = []
#subsequent runs use logger object already created.

def open_pickle():
    if (os.path.isfile(PICKLE_FILE)):
        contents = open(PICKLE_FILE, 'r+')
        return pickle.load(contents)
    else:
        return []

logger = open_pickle()
app = web.application(urls, globals())


# Forms a hash of the url and appends the short code with a predefined character.
def random_shortcut(mylink):
    hashed = hashlib.sha256()
    hashed.update(mylink)
    digested_b64 = base64.b64encode(hashed.hexdigest())
    digested_short = digested_b64[:LENGTH]
    digested_short = re.sub("(^)[0-9]", "x", digested_short)
    return digested_short

def append_title_for_logging(url):
    urlhandle_full = urllib2.urlopen(url)
    try:
        htmlsource = urlhandle_full.read();
    except (IOError, AttributeError, TypeError, NameError):
        return u'Unable to retrieve title'
    try:
        title_s = re.search(r"(?i)<title>\s*(.*?)\s*</title>", htmlsource)
        title = title_s and title_s.groups()[0] or "NO TITLE"
        return title
    except (IOError, AttributeError, TypeError, NameError):
        return u'Unable to retrieve title'



def prepend_http_if_required(link):
    if (re.match("(^)https://", link, re.IGNORECASE)):
        return link
    elif (re.match("(^)data:", link, re.IGNORECASE)):
        return link
    elif not (re.match("(^)http://", link, re.IGNORECASE)):
        link = "http://" + link
    return link

def do_logging(loggingUrl, shortcut):
    global logger
    check_for_duplicates(shortcut)
    logging = []
    logging.append(loggingUrl.urlStamp)
    logging.append(loggingUrl.title)
    logging.append(loggingUrl.longurl)
    logging.append(shortcut)
    if len(logger) > 20:
        logger.pop()
    logger.insert(0,logging)
    save_logger()

def check_for_duplicates(shorthash):
    global logger
    for loggedurl in logger:
        if loggedurl[3] == shorthash:
            logger.remove(loggedurl)

# TODO implement class logger for betterness.

class urlClass:
    def __init__(self, longurl, mytitle):
        self.longurl =  longurl
        if mytitle is "":
            self.title = append_title_for_logging(longurl)
        else:
            self.title = mytitle
        self.urlStamp = time.strftime('%X-%x')

    def getLongUrl(self):
        return self.longurl

    def getTime(self):
        return self.urlStamp

class Favicon:
    def GET(self):
        return web.seeother(STATIC_DIR + "/favicon.ico")

class RedirectToOthers:
    def GET(self, short_name):
        storage = shelve.open(SHELVE_FILENAME)
        short_name = str(short_name) # shelve does not allow unicode keys
        if storage.has_key(short_name):
            destination = storage[short_name]
            response = web.redirect(destination.getLongUrl())
        else:
            response = FAIL_MESSAGE
        storage.close()
        return response

class Admin:
    def GET(self):
        web.header("Content-Type","text/html; charset=utf-8")
        admin_form = web.form.Form(
            web.form.Textbox("url",     description="Long URL"),
            web.form.Textbox("shortcut",description="(optional) Your own short word"),
            web.form.Textbox("title",description="(optional) URL Title"),
            )
        admin_template = web.template.Template("""$def with(form, SERVICE_URL, SHRINK_PATH)
        <!DOCTYPE HTML>
        <html lang="en">
          <head>
            <meta charset=utf-8>
            <title>jpb.li</title>
            <h3>Welcome to the url shortening service.</h3>
	    <h4>You can either use the form below or the following query string:</h4>
	    <pre>http://localhost:8080/$SHRINK_PATH?url=your_long_url&[title=your_customised_short_title]</pre>
	    <h4>Recently shortened url's can be found at <a href="/log">http://$SERVICE_URL/log</a></h4>
          </head>
          <body onload="document.getElementById('url').focus()">
            <form method="POST" action=/>
              $:form.render()
              <input type="submit" value="Shorten this long URL">
            </form>
          </body>
        </html>
        """)
        return admin_template(admin_form(), SERVICE_URL, SHRINK_PATH)

    def POST(self):
        data = web.input()
        data.url = prepend_http_if_required(data.url)
        if str(data.shortcut):
            data.shortcut = str(data.shortcut)
        shortcut = str(data.shortcut) or random_shortcut(data.url)
        if str(data.title):
            siteTitle = data.title
        else:
            siteTitle = ""
        storage = shelve.open(SHELVE_FILENAME)
        if not data.url:
            response = web.badrequest()
        elif storage.has_key(shortcut):
            myUrl = urlClass(data.url, siteTitle)
            response = web.seeother('/done/'+shortcut)
        else :
            myUrl = urlClass(data.url, siteTitle)
            storage[shortcut] = myUrl
            response = web.seeother('/done/'+shortcut)
        do_logging(myUrl, "/" + REDIRECT_PREFIX + "/" + shortcut)
        storage.close()
        return response

class Shrink:
    def GET(self):
        variables = web.input()
        web.header("Content-Type","text/html; charset=utf-8")
        if 'url' in variables:
            long_url = variables.url
        else:
            return "No URL Specified"
        if 'title' in variables:
            urlTitle = variables.title
        else:
            urlTitle = ""
        long_url = prepend_http_if_required(long_url)
        short_url = random_shortcut(long_url)
        storage = shelve.open(SHELVE_FILENAME)
        myUrl = urlClass(long_url, urlTitle)
        if storage.has_key(short_url):
            response = web.seeother('/done/'+short_url)
        else:
            storage[short_url] = myUrl
            response = short_url
        do_logging(myUrl, response)
        storage.close()
        return web.seeother('/done/'+short_url)

class ListUrl:
    def GET(self):
        web.header("Content-Type","text/html; charset=utf-8")
        table = ""
        placeholder_top = """
       <!DOCTYPE HTML>
        <html lang="en">
          <head>
            <meta charset=utf-8>
            <title>URL Logger</title>
          </head>
          <body>
            <header><h2>URL's shortenned:</h2></header>
	<table>
"""

        placeholder_bottom = """
	</table>
          </body>
        </html>
"""
        for loggedurl in logger:
            table_element = "<tr><td>%s</td> <td> <a href=%s>%s</a></td> </tr>" %(loggedurl[0], loggedurl[3], loggedurl[1].decode("utf-8", "ignore").encode('ascii','replace'))
            #TODO set up the right short url
            table = table + table_element
        placeholder = placeholder_top + table + placeholder_bottom
        list_template = web.template.Template(placeholder)
        return placeholder

class AdminDone:
    def GET(self, short_name):
        web.header("Content-Type","text/html; charset=utf-8")
        admin_done_template = web.template.Template("""$def with(new_url, SERVICE_URL, REDIRECT_PREFIX)
       <!DOCTYPE HTML>
        <html lang="en">
          <head>
            <meta charset=utf-8>
            <title>URL shortener administration</title>
          </head>
          <body>
            <header><h1>Done!</h1></header>
            <p>You created: <a href=/$REDIRECT_PREFIX/$new_url>http://$SERVICE_URL/$REDIRECT_PREFIX/$new_url</a> </p>
          </body>
        </html>
        """)
        return admin_done_template(short_name, SERVICE_URL, REDIRECT_PREFIX)

def terminate(sig, frame):
    print 'Received Signal:', sig
    print "exiting and printing logger :: terminate"
    os._exit(0)

def save_logger():
    global logger
    print "print logger :: save_logger"
    print logger
    output = open('url-logger.pkl', 'w')
    pickle.dump(logger, output)
    output.close()

if __name__ == "__main__":
    try:
        for sig in TERMSIGS:
            signal(sig, terminate)
    except:
        pass

    app.run()


##
##TODO   failures
## http://www.gmail.com and www.butterfly.com
## save logger b/w restarts

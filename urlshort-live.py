#!/usr/bin/python

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
SERVICE_URL = "http://jpb.li"
ADMIN = '/g'
LENGTH = 4
STATIC_DIR = "/static"

urls = (
    "/",                "Home",
    ADMIN +"/done/(.*)", "AdminDone",
    ADMIN,              "Admin",
    "/favicon.ico",     "Favicon",
    ADMIN + "/log", "ListUrl",
    ADMIN +"/api",           "GET_API",
    "/geniecal",           "GenieCal",
    "/git",                "GenieGit",
    "/g([0-9].*)",           "Trac",
    "/g(.*)",            "RedirectToOthers",
)

#Messages
HOME_MESSAGE = '''Welcome to URL shortenner. 
		/admin to get controls'''
FAIL_MESSAGE = 'Redirection failed, verify your link...'  # Messages

TERMSIGS = (SIGQUIT, SIGINT, SIGTERM,)

#first run requires a logger to be defined.
#logger = [] 
#subsequent runs use logger object already created.

output = open('url-logger.pkl', 'r')
logger = pickle.load(output)
output.close()

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
	print "debug: logger"
	print loggedurl[3]
	print shorthash
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
        self.urlStamp = time.asctime(time.gmtime())

    def getLongUrl(self):
        return self.longurl

    def getTime(self):
        return self.urlStamp


class Home:
    def GET(self):
	web.header("Content-Type","text/html; charset=utf-8")
        return HOME_MESSAGE

class Trac:
    def GET(self, number):
	return web.seeother("http://aladdin.geniedb.com:8000/xos/ticket/%s" %number)

class GenieCal:
    def GET(self):
        return web.seeother("https://www.google.com/calendar/hosted/geniedb.com/render")

class GenieGit:
    def GET(self):
        variables = web.input()
        response = "http://aladdin.geniedb.com/git/?"
        if ('p' in variables):
                response = "%sp=%s;" % (response, variables.p)
        if ('a' in variables):
                response = "%sa=%s;" % (response, variables.a)
        if ('f' in variables):
                response = "%sf=%s;" % (response, variables.f)
        if ('hb' in variables):
                response = "%shb=%s;" % (response, variables.hb)
        return web.seeother(response)

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
        admin_template = web.template.Template("""$def with(form)
        <!DOCTYPE HTML>
        <html lang="en">
          <head>
            <meta charset=utf-8>
            <title>jpb.li</title>
            <h3>Welcome to the jpb.li url shortening service.</h3>
	    <h4>You can either use the form below or the following query string:</h4>
	    <pre>http://jpb.li/g/api?url=your_long_url&[title=your_customised_short_title]</pre>
	    <h4>Recently shortened url's can be found at <a href="http://jpb.li/g/log">http://jpb.li/g/log</a></h4>
          </head>
          <body onload="document.getElementById('url').focus()">
            <header><h4>Web Form:</h4></header>
            <form method="POST" action=/g>
              $:form.render()
              <input type="submit" value="Shorten this long URL">
            </form>
          </body>
        </html>
        """)
        return admin_template(admin_form())

    def POST(self):
        data = web.input()
        data.url = prepend_http_if_required(data.url)
	if str(data.shortcut):
		data.shortcut = "g/" + str(data.shortcut)
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
            response = web.seeother(SERVICE_URL+ADMIN+'/done/'+shortcut)
	else :
            myUrl = urlClass(data.url, siteTitle)
            storage[shortcut] = myUrl
            response = web.seeother(SERVICE_URL+ADMIN+'/done/'+shortcut)
        responseurl = SERVICE_URL+ADMIN+shortcut
        do_logging(myUrl, responseurl)
        storage.close()
        return response

class GET_API:
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
            response = SERVICE_URL + ADMIN + short_url
        else:
            storage[short_url] = myUrl
            response = SERVICE_URL + ADMIN + short_url
        do_logging(myUrl, response)
        storage.close()
        return response

class ListUrl:
    def GET(self):
	web.header("Content-Type","text/html; charset=utf-8")
        urllist = ""
        placeholder_top = """
       <!DOCTYPE HTML>
        <html lang="en">
          <head>
            <meta charset=utf-8>
            <title>URL Logger</title>
          </head>
          <body>
            <header><h2>URL's created on http://jpb.li</h2></header>
	<table>
"""

        placeholder_bottom = """
	</table>
          </body>
        </html>
"""
        for loggedurl in logger:
            urllist_string = "<tr><td><pre>%s</pre></td> <td><pre> <a href=%s>%s</a></pre></td> </tr>" %(loggedurl[0], loggedurl[3], loggedurl[1])
            #TODO set up the right short url
            urllist = urllist + urllist_string
        placeholder = placeholder_top + urllist + placeholder_bottom
        list_template = web.template.Template(placeholder)
        return placeholder

class AdminDone:
    def GET(self, short_name):
	web.header("Content-Type","text/html; charset=utf-8")
        admin_done_template = web.template.Template("""$def with(new_url)
       <!DOCTYPE HTML>
        <html lang="en">
          <head>
            <meta charset=utf-8>
            <title>URL shortener administration</title>
          </head>
          <body>
            <header><h1>Done!</h1></header>
            <p>You created: <a href=$new_url>$new_url</a> </p>
          </body>
        </html>
        """)
        return admin_done_template(SERVICE_URL + ADMIN + short_name)

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

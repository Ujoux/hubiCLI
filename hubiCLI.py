#!/usr/bin/env python

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. 
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, 
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, 
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# Licensed under the Creative Commons Attribution-ShareAlike 3.0 Unported License
#
# hubiC is a product of OVH ( http://www.ovh.fr/hubiC/ )
#
# Author of this script : Ujoux ( http://forum.ovh.com ), i'm not affiliated with OVH

"""
hubiCLI.py : Command Line Interface to hubiC

Usage:
  hubiCLI.py [-v] [-l LOGIN] [-p PASSWORD] --list [SRC]
  hubiCLI.py [-v] [-l LOGIN] [-p PASSWORD] --download FILES ...
  hubiCLI.py [-v] [-l LOGIN] [-p PASSWORD] --download-folder SRC
  hubiCLI.py [-v] [-l LOGIN] [-p PASSWORD] --download-zip SRC FILES ...
  hubiCLI.py [-v] [-l LOGIN] [-p PASSWORD] --upload DEST FILES ...
  hubiCLI.py [-v] [-l LOGIN] [-p PASSWORD] --upload-folder SRC DEST
  hubiCLI.py [-v] [-l LOGIN] [-p PASSWORD] --move SRC DEST FILE
  hubiCLI.py [-v] [-l LOGIN] [-p PASSWORD] --rename SRC OLD NEW
  hubiCLI.py [-v] [-l LOGIN] [-p PASSWORD] --delete SRC NAME
  hubiCLI.py [-v] [-l LOGIN] [-p PASSWORD] --create-folder SRC NAME
  hubiCLI.py [-v] [-l LOGIN] [-p PASSWORD] --publish SRC NAME [DURATION] [MESSAGE]
  hubiCLI.py [-v] [-l LOGIN] [-p PASSWORD] --unpublish SRC NAME
  hubiCLI.py -h | --help
  hubiCLI.py --version

Arguments:
  DURATION                                  duration of publication in days

Options:
  -v --verbose                              print status messages
  -l=<LOGIN> --login=<LOGIN>                use specified login
  -p=<PASSWORD> --password=<PASSWORD>       use specified password

Examples:
   hubiCLI.py -v --list "/remote/folder"
   hubiCLI.py -v --download "/folder/file1.ext" "/folder/file2.ext" "/folder/file3.ext"
   hubiCLI.py -v --download-zip "/folder" "/folder/file1.ext" "/folder/file2.ext" "/folder/file3.ext"
   hubiCLI.py -v --upload "/remote/folder" "/local/file1.ext" "/local/file2.ext" "/local/file3.ext"
   hubiCLI.py -v --upload-folder "/my/local/folder" "/remote/folder"

"""

# do not edit before

# modify with your username and password
username = ''
password = ''
userAgent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.97 Safari/537.11'

# do not edit beyond

import  sys, copy
import sched, time, math, mimetypes, datetime
import os, random, json
from pprint import pprint
import multiprocessing
from multiprocessing import Value, Lock, Process, Array
from ctypes import c_int, c_char_p
import ctypes
import re
import urllib
import urllib2
import curses
import time
import codecs

# you will probably have to install those modules (docopt, requests, progressbar)

from docopt import docopt
import requests
import progressbar
from progressbar import Bar, FileTransferSpeed, Percentage, ProgressBar

# fix unicode printing
streamWriter = codecs.lookup('utf-8')[-1]
sys.stdout = streamWriter(sys.stdout)

__author__ = "Ujoux"
__copyright__ = "Copyleft"
__credits__ = ["Ujoux"]
__license__ = "CC-BY-SA 3.0"
__version__ = "0.1"
__maintainer__ = "Ujoux"
__status__ = "Development"

headers = ''
oldSize = ''
sessionHash = ''
used = ''
quota = ''
accountType = ''
version = ''
email = ''
maxFileSize = ''
filesList = ''
filesCount = ''
fileFound = False
foundFile = None
PHPSESSID = None
HUBICID = None
stdscr = None
FILESTODOWN = []
FILESTOUP = []

DLTOGO = Value(c_int)
DLTOGO_LOCK = Lock()

UPTOGO = Value(c_int)
UPTOGO_LOCK = Lock()

if __name__ != '__main__':
   sys.exit(0)

arguments = docopt(__doc__, version='0.1')

if arguments['--login'] != None:
   username = arguments['--login']

if arguments['--password'] != None:
   password = arguments['--password']

class UnknownLength: pass

class CustProgressBar(ProgressBar):
    
    def updateBuffer(self, i, arr, msg, lock):
        
        global stdscr
        
        now = time.time()
        self.seconds_elapsed = now - self.start_time
        self.next_update = self.currval + self.update_interval
        
        with lock:
           arr[i] = msg
           
           stdscr.clear()
           
           j = 0
           for dlmsg in arr:
              if dlmsg != '':
                 stdscr.addstr(j, 0, dlmsg)
                 j += 1
          
           stdscr.refresh()
  
           self.last_update_time = now
        
        return

    def update(self, value=None, pid=None, arr=None, lock=None):
        """Updates the ProgressBar to a new value."""
        
        if value is not None and value is not UnknownLength:
            if (self.maxval is not UnknownLength
                and not 0 <= value <= self.maxval):
                
                if value >= self.maxval:
                   self.finish()
                else:
                   raise ValueError('Value out of range')

            self.currval = value

        if not self._need_update(): return
        
        if self.start_time is None:
            raise RuntimeError('You must call "start" before calling "update"')

        if pid != None:
           self.updateBuffer(pid, arr, self._format_line(), lock)

class Consumer(multiprocessing.Process):

    def __init__(self, task_queue, result_queue, arr, lock):
        multiprocessing.Process.__init__(self)
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.arr = arr
        self.lock = lock

    def run(self):
        proc_name = self.name
        while True:
            next_task = self.task_queue.get()
            if next_task is None:
                self.task_queue.task_done()
                break            
            answer = next_task(arr=self.arr, lock=self.lock)
            self.task_queue.task_done()
            self.result_queue.put(answer)
        return

class Task(object):
    def __init__(self, a, pid):
        self.a = a
        self.pid = pid

    def __call__(self, arr=None, lock=None):
        
        realDownload(self.a, self.pid, arr, lock)

        return self.a

    def __str__(self):
        return 'ARC'
    def run(self):
        print 'IN'

class TaskUpload(object):
    def __init__(self, folder, a, pid):
        self.a = a
        self.pid = pid
        self.folder = folder

    def __call__(self, arr=None, lock=None):
        
        realUpload(self.folder, self.a, self.pid, arr, lock)

        return self.a

    def __str__(self):
        return 'ARC'
    def run(self):
        print 'IN'

# Session() to keep authentication cookies
sess = requests.Session()

print "Starting hubiCLI..."
print ""

def get_cookie_by_name(cj, name):
    return [cookie for cookie in cj if cookie.name == name][0]

def login():
   global PHPSESSID
   global HUBICID
   
   if username == '' or password == '':
      print "No username or password specified"
      sys.exit(0)
   
   headers = {'User-Agent': userAgent, 'Origin': 'https://app.hubic.me'}
   payload = {'sign-in-email': username, 'sign-in-password': password, 'sign-in-action': 'true'}
   r = sess.post("https://app.hubic.me/v2/actions/nasLogin.php", data=payload, headers=headers)
   
   logResp = ''
   
   for cookie in sess.cookies:
      if cookie.name == 'PHPSESSID':
         PHPSESSID = cookie.value
      if cookie.name == 'app.hubic.me':
         HUBICID = cookie.value
      if cookie.name == 'HUBIC_ACTION_RETURN':
         logResp = cookie.value
   
   logResp = urllib2.unquote(logResp.encode("utf8"))
   
   if logResp != '':
      logResp = json.JSONDecoder('utf8').decode(logResp)
      
      statusCode = logResp['answer']['status']
      message = logResp['answer']['login']['message']
      
      message = message.replace('+', ' ')
      
      print "Login failed -> %s (%d)" % (message, statusCode)
      
      sys.exit(0)
   
   if arguments['--verbose'] == True :
      print "* Successfuly logged into hubiC"
      print ""
   
   return;

def getSettings():
   global userAgent
   
   headers = {'User-Agent': userAgent, 'Origin': 'https://app.hubic.me'}
   r = sess.post("https://app.hubic.me/v2/actions/ajax/getSettings.php", headers=headers)
   
   resp = r.json()
   
   if resp['answer'] and resp['answer']['status'] and resp['answer']['status'] == 200:
      print "* Successfuly retrieved settings"
      print ""
      
      global email
      email = resp['answer']['settings']['hubic']['email']
      
      global sessionHash
      sessionHash = resp['answer']['settings']['hubic']['sessionHash']
      
      global accountType
      accountType = resp['answer']['settings']['hubic']['offer']
      
      global used
      used = int(resp['answer']['settings']['hubic']['used'])
      global quota
      quota = int(resp['answer']['settings']['hubic']['quota'])
      
      global version
      version = resp['answer']['settings']['hubic']['version']
      
      global maxFileSize
      maxFileSize = int(resp['answer']['settings']['settings']['MAX_FILE_SIZE'])
      
      if arguments['--verbose'] == True :
         print "Email : %s" % (email)
         print "Account type : %s" % (accountType)
         print "Used : %s out of %s (%d%%)" % (sizeof_fmt(used), sizeof_fmt(quota), (used * 100) / quota)
         print "Version : %s" % (version)
         print "Max file size : %s" % (sizeof_fmt(maxFileSize))
      
      print ""
   else :
      print "* Retrieving settings failed !"
      print ""
   
   return;

def listFiles(folder = '/', filesOnly=False):
   global FILESTODOWN
   global filesList
   
   data = filesList
   
   FILESTODOWN = []
   
   walkDict(data, filterFor, folder)
   
   for f in FILESTODOWN:
      if filesOnly and f['type'] == 'application/directory':
         continue
      
      if arguments['--verbose'] == True:
         print ', '.join([f['uri'], f['type'], f['creation'], f['modified'], str(f['size'])])
      else:
         print f['uri']
   
   return FILESTODOWN;

def getFilesList(folder = '/'):
   global filesList
   
   headers = {'User-Agent': userAgent, 'Origin': 'https://app.hubic.me'}
   payload = {'action': 'get', 'folder': folder, 'container': '', 'init': 'true'}
   r = sess.post("https://app.hubic.me/v2/actions/ajax/hubic-browser.php", data=payload, headers=headers)
   
   if r.status_code != 200:
      print "* Get files list NOT OK !!!"
      print ""
      return
   
   filesList = json.JSONDecoder('latin1').decode(r.text)
   
   if filesList['answer'] and filesList['answer']['status'] and filesList['answer']['status'] == 200:

      print "* Get files list OK"
      print ""

      global filesCount
      filesCount = filesList['answer']['hubic']['list']['default']['props']['count']

      if arguments['--verbose'] == True :
         print "Files count : ", filesCount
         print ""
   
   else :
      print "* Get files list NOT OK !!!"
      print ""
      return;
   
   return;

def uploadBunch(folder, names):
   global stdscr
   global UPTOGO
   global UPTOGO_LOCK

   stdscr = curses.initscr()
   curses.noecho()
   curses.cbreak()
   
   with UPTOGO_LOCK:
      UPTOGO.value = len(names)
   
   tasks = multiprocessing.JoinableQueue()
   results = multiprocessing.Queue()
   manager = multiprocessing.Manager()
   
   arr = manager.list(['']*len(names))
   
   lock = multiprocessing.Lock()
   
   num_consumers = multiprocessing.cpu_count() * 2
   consumers = [Consumer(tasks, results, arr, lock) for i in xrange(num_consumers)]
   
   for w in consumers:
      w.start()
   
   pid=0
   for name in names:
      tasks.put(TaskUpload(os.path.join(folder, os.path.dirname(name)), os.path.basename(name), pid))
      pid += 1

   for i in xrange(num_consumers):
      tasks.put(None)

   tasks.join()
   
   return

def upload(folder, names):
   global stdscr
   global UPTOGO
   global UPTOGO_LOCK

   stdscr = curses.initscr()
   curses.noecho()
   curses.cbreak()
   
   with UPTOGO_LOCK:
      UPTOGO.value = len(names)
   
   tasks = multiprocessing.JoinableQueue()
   results = multiprocessing.Queue()
   manager = multiprocessing.Manager()
   arr = manager.list(['']*len(names))
   
   lock = multiprocessing.Lock()
   
   num_consumers = multiprocessing.cpu_count() * 2
   consumers = [Consumer(tasks, results, arr, lock) for i in xrange(num_consumers)]
   
   for w in consumers:
      w.start()
   
   pid=0
   for name in names:
      tasks.put(TaskUpload(folder, name, pid))
      pid += 1

   for i in xrange(num_consumers):
      tasks.put(None)

   tasks.join()
   
   return

class Progress(object):
    def __init__(self):
        self._seen = 0.0

    def update(self, total, size, bar, pid, arr, lock):
        self._seen += size
        bar.update(self._seen, pid, arr, lock)
        
        if self._seen >= total:
           bar.finish()

class file_with_callback(file):
    def __init__(self, path, mode, callback, bar, pid, arr, lock, *args):
        file.__init__(self, path, mode)
        self.seek(0, os.SEEK_END)
        self._total = self.tell()
        self.seek(0)
        self._callback = callback
        self._args = args
        self.bar = bar
        self.pid = pid
        self.arr = arr   
        self.lock = lock

    def __len__(self):
        return self._total

    def read(self, size):
        data = file.read(self, size)
        self._callback(self._total, len(data), self.bar, self.pid, self.arr, self.lock, *self._args)
        return data

def uploadAll(folderSrc, folderDst):
   global FILESTOUP

   stdscr = curses.initscr()
   curses.noecho()
   curses.cbreak()
   
   FILESTOUP = []
   
   dirs = []
   
   createFolder(os.path.dirname(os.path.join(folderDst, folderSrc)), os.path.basename(folderSrc), True)
   
   for (dirpath, dirnames, filenames) in os.walk(folderSrc):
      for dirname in dirnames:
         dirs.append(os.path.join(dirpath, dirname))
      
      for filename in filenames:
         FILESTOUP.append(os.path.join(dirpath, filename))
      
   for d in dirs:
      createFolder(os.path.join(folderDst, os.path.dirname(d)), os.path.basename(d), True)
   
   uploadBunch(folderDst, FILESTOUP)
   
   return

def realUpload(folder, name, pid, arr, lock):
   global sessionHash
   global foundFile
   global PHPSESSID
   global HUBICID
   global UPTOGO
   global UPTOGO_LOCK
   
   filename = "%s%s" % (folder, name)
   in_file = open(name, "r")
   fileData = in_file.read()
   in_file.close()
   
   fileSize = getLocalFileSize(name)
   
   mime = mimetypes.guess_type(name)[0]
   realFilename = os.path.basename(name)
   
   headers = {'User-Agent': userAgent, 'Origin': 'https://app.hubic.me', 'Host': 'app.hubic.me'}
   cookies = {'PHPSESSID': PHPSESSID, 'app.hubic.me': HUBICID}
   
   conn = requests.Session()
   
   cs = sizeof_fmt(fileSize)
   widgets = [name, ": ", Bar(marker="|", left="[", right=" "), ' ', Percentage(), ' ',  FileTransferSpeed(), "] ", " of ", cs," "]

   pbar = CustProgressBar(widgets=widgets, maxval=fileSize).start()
   
   path = name
   progress = Progress()
   
   stream = file_with_callback(path, 'r', progress.update, pbar, pid, arr, lock)
   
   headers = {'User-Agent': userAgent, 'Origin': 'https://app.hubic.me', 'X-File-Size': fileSize, 'X-File-Dest': folder, 'X-Action': 'upload', 'X-File-Container': 'default', 'X-File-Name': realFilename, 'X-File-Type': mime, 'Content-Type': mime}
   
   r = conn.put("http://app.hubic.me/v2/actions/ajax/hubic-browser.php", data=stream, headers=headers, cookies=cookies, stream=True)
   
   answer = r.json()
   
   if answer['answer'] and answer['answer']['status'] and answer['answer']['status'] == 201:
      
      with UPTOGO_LOCK:
         UPTOGO.value -= 1
      
         if UPTOGO.value == 0:
            time.sleep(1)
            stdscr.erase()
            curses.echo()
            curses.nocbreak()
            curses.endwin()
            os.system('reset')
            logout()
   
   return;

def realDownload(name, pid, arr, lock):
   global sessionHash
   global foundFile
   global PHPSESSID
   global HUBICID
   global DLTOGO
   global DLTOGO_LOCK
   
   foundFile = getFile(name)
   
   filename = os.path.basename(name)
   
   #if foundFile is None or foundFile['size'] is UnknownLength:
      #print "* Download of %s failed ! -> file not found" % filename
      #print ""
      #return
   
   fsize = foundFile['size']
   thetype = foundFile['type']
   
   key = int(math.floor(random.random()*(time.time())))
   headers = {'User-Agent': userAgent, 'Origin': 'https://app.hubic.me', 'Host': 'app.hubic.me'}
   cookies = {'PHPSESSID': PHPSESSID, 'app.hubic.me': HUBICID}
   
   conn = requests.Session()
   
   folder = ''
   
   r = conn.get("https://app.hubic.me/v2/actions/ajax/hubic-browser.php?action=download&folder=%s&container=default&name=%s&key=%s&isFile=true&size=%s&type=%s&secret=%s" % (folder, name, key, fsize, thetype, sessionHash), headers=headers, stream=True, cookies=cookies)
   
   progress = Progress()
   
   dsize = int(r.headers['Content-Length'].strip())
   bytes = 0
   cs = sizeof_fmt(dsize)
   widgets = [name, ": ", Bar(marker="|", left="[", right=" "), Percentage(), " ",  FileTransferSpeed(), "] ", '', " of ", cs," "]
   pbar = CustProgressBar(widgets=widgets, maxval=dsize).start()
   
   realFilename = os.path.basename(filename)
   realFile = open(realFilename, 'wb')
   
   for buf in r.iter_content(1024, True):
       if buf:
          realFile.write(buf)
          bytes += len(buf)
          
          progress.update(dsize, 1024, pbar, pid, arr, lock)
      
   realFile.close()
   
   statinfo = os.stat(realFilename)
   savedSize = statinfo.st_size
   
   with DLTOGO_LOCK:
      DLTOGO.value -= 1
      
      if DLTOGO.value == 0:
         time.sleep(1)
         stdscr.erase()
         curses.echo()
         curses.nocbreak()
         curses.endwin()
         os.system('reset')
         logout()
   
   return;

def downloadAll(folder):
   global DLTOGO
   global DLTOGO_LOCK
   global FILESTODOWN
   global filesList
   
   data = filesList
   
   walkDict( data, filterFor, folder)
   
   names = []
   
   for f in FILESTODOWN:
      names.append(f['uri'])
   
   download(names)
   
   return

def encodeURI(aString):
   return urllib.quote(unicode(aString).encode('utf-8'), safe='~@#$&()*!+=:;,.?/\'');

def downloadZipped(folder, names):
   global sessionHash
   global foundFile
   global PHPSESSID
   global HUBICID
   global DLTOGO
   global DLTOGO_LOCK
   
   key = int(round(time.time() * 1000))
   headers = {'User-Agent': userAgent, 'Origin': 'https://app.hubic.me', 'Host': 'app.hubic.me'}
   cookies = {'PHPSESSID': PHPSESSID, 'app.hubic.me': HUBICID}
   
   conn = requests.Session()
   
   folderSize = 0
   
   for name in names:
           foundFile = getFile(name)
           
           if foundFile == None:
              print "Skipping file not found : %s" % (name)
              continue
           
           filename = os.path.basename(name)
           
           fsize = foundFile['size']
           thetype = 'image/jpeg'
           
           payload = {'action': 'download', 'dlname': encodeURI(folder), 'sub': 'launch', 'name': encodeURI(filename), 'uri': encodeURI(name), 'container': 'default', 'size': fsize, 'type': thetype, 'isFile': 'true', 'key': key}
           
           r = conn.post("https://app.hubic.me/v2/actions/ajax/hubic-browser.php", data=payload, headers=headers, cookies=cookies)
           
           a = json.JSONDecoder('utf8').decode(r.text)
	   
           if a['answer']['status'] and a['answer']['status'] == 200:
              folderSize += a['answer']['download']['loaded']
   
   zipName = os.path.basename(folder) + ".zip"
   
   payload = {'action': 'download', 'sub': 'zip', 'dlPath': encodeURI(folder), 'dlName': zipName, 'isFile': 'true', 'key': key}
   
   r = conn.post("https://app.hubic.me/v2/actions/ajax/hubic-browser.php", data=payload, headers=headers, cookies=cookies)
   
   r = conn.get("https://app.hubic.me/v2/actions/ajax/hubic-browser.php?&action=download&name=%s&key=%s&isFile=false&size=%s&type=%s&secret=%s" % (encodeURI(folder), key, folderSize, 'application/zip', sessionHash), headers=headers, stream=True, cookies=cookies)
   
   dsize = int(r.headers['Content-Length'].strip())
   bytes = 0
   cs = sizeof_fmt(dsize)
   widgets = [zipName, ": ", Bar(marker="|", left="[", right=" "), Percentage(), " ",  FileTransferSpeed(), "] ", '', " of ", cs," "]
   pbar = ProgressBar(widgets=widgets, maxval=dsize).start()
   
   realFilename = os.path.basename(zipName)
   realFile = open(realFilename, 'wb')
   
   for buf in r.iter_content(1024, True):
       if buf:
          realFile.write(buf)
          bytes += len(buf)
          pbar.update(bytes)
          
          if bytes >= dsize:
             pbar.finish()
   
   pbar.finish()
      
   realFile.close()
   
   return

def download(names):
   global stdscr
   global DLTOGO
   global DLTOGO_LOCK

   stdscr = curses.initscr()
   curses.noecho()
   curses.cbreak()
   
   with DLTOGO_LOCK:
      DLTOGO.value = len(names)
   
   tasks = multiprocessing.JoinableQueue()
   results = multiprocessing.Queue()
   manager = multiprocessing.Manager()
   arr = manager.list(['']*len(names))

   lock = multiprocessing.Lock()
   
   num_consumers = multiprocessing.cpu_count() * 2
   consumers = [Consumer(tasks, results, arr, lock) for i in xrange(num_consumers)]
   
   for w in consumers:
      w.start()
   
   pid=0
   for name in names:
      tasks.put(Task(name, pid))
      pid += 1

   for i in xrange(num_consumers):
      tasks.put(None)

   tasks.join()
   
   return

def move(src, dest, name):
   
   oldFileURI = os.path.join(src, name)
   newFileURI = os.path.join(dest, name)
   
   oldFile = getFile(oldFileURI)
   
   if oldFile == None:
      print "File not found : %s" % (oldFileURI)
      return
   
   mime = oldFile['type']
   
   headers = {'User-Agent': userAgent, 'Origin': 'https://app.hubic.me'}
   payload = {'action': 'move', 'src' : src, 'srcContainer' : 'default', 'dest': dest, 'destContainer' : 'default', 'name': name, 'type': mime, 'isFile': 'true', 'force': 'false', 'isParentFolder': 'true', 'finalize' : 'false'}
   r = sess.post("https://app.hubic.me/v2/actions/ajax/hubic-browser.php", data=payload, headers=headers)
      
   resp = r.json()
   
   if resp['answer'] and resp['answer']['status'] and resp['answer']['status'] == 201:
      print "* Moved %s to %s OK" % (oldFileURI, newFileURI)
   else :
      print "* Move of %s to %s failed !" % (oldFileURI, newFileURI)
   
   return;

def rename(src, old, new):
   oldFileURI = os.path.join(src, old)
   newFileURI = os.path.join(src, new)
   
   oldFile = getFile(oldFileURI)
   
   if oldFile == None:
      print "File not found : %s" % (oldFileURI)
      return
   
   headers = {'User-Agent': userAgent, 'Origin': 'https://app.hubic.me'}
   payload = {'action': 'rename', 'folder': src, 'container' : 'default', 'old': old, 'new': new, 'finalize' : 'false', 'itemIndex' : 'undefined', 'isParentFolder' : 'true', 'isFile': 'true'}
   r = sess.post("https://app.hubic.me/v2/actions/ajax/hubic-browser.php", data=payload, headers=headers)
      
   resp = r.json()
   
   if resp['answer'] and resp['answer']['status'] and resp['answer']['status'] == 201:
      print "* Rename of %s to %s OK" % (oldFileURI, newFileURI)
   else :
      print "* Rename of %s to %s failed !" % (oldFileURI, newFileURI)
   
   return;

def createFolder(folder, name, quiet=False):
   
   folderURI = os.path.join(folder, name)
   
   headers = {'User-Agent': userAgent, 'Origin': 'https://app.hubic.me'}
   payload = {'action': 'create', 'folder' : folder, 'container' : 'default', 'name': name}
   r = sess.post("https://app.hubic.me/v2/actions/ajax/hubic-browser.php", data=payload, headers=headers)
   
   resp = r.json()
   
   if quiet == False:
      if resp['answer'] and resp['answer']['status'] and resp['answer']['status'] == 201:
         print "* Created folder %s OK" % folderURI
      else :
         print "* Creation of %s failed !" % folderURI
   
   return;

def delete(folder, name):
   fileURI = os.path.join(folder, name)
   
   theFile = getFile(fileURI)
   
   if theFile == None:
      print "File not found : %s" % (fileURI)
      return
   
   mime = theFile['type']
   
   isFile = (mime != 'application/directory')
   
   headers = {'User-Agent': userAgent, 'Origin': 'https://app.hubic.me'}
   payload = {'action': 'remove', 'folder' : folder, 'container' : 'default', 'name': name, 'type': mime, 'isFile': isFile}
   r = sess.post("https://app.hubic.me/v2/actions/ajax/hubic-browser.php", data=payload, headers=headers)
   
   resp = r.json()
   
   if resp['answer'] and resp['answer']['status'] and resp['answer']['status'] == 204:
      print "* Deleted %s OK" % fileURI
   else :
      print "* Deletion of %s failed !" % fileURI
   
   return;

def publish(folder, name, duration = 10, message = ''):
   fileURI = os.path.join(folder, name)
   
   theFile = getFile(fileURI)
   
   if theFile == None:
      print "File not found : %s" % (fileURI)
      return
   
   mime = theFile['type']
   
   isFile = (mime != 'application/directory')
   
   headers = {'User-Agent': userAgent, 'Origin': 'https://app.hubic.me'}
   payload = {'action': 'publish', 'folder': folder, 'name': name, 'container' : 'default', 'isFile': isFile, 'duration': duration, 'message': message}
   r = sess.post("https://app.hubic.me/v2/actions/ajax/hubic-browser.php", data=payload, headers=headers)
      
   resp = r.json()
   
   if resp['answer'] and resp['answer']['status'] and resp['answer']['status'] == 200:
      creation = resp['answer']['publicationItem']['creation']
      expire = resp['answer']['publicationItem']['expire']
      url = resp['answer']['publicationItem']['url']
      
      creationF = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(creation)))
      expireF = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(expire)))
      
      print "* Publishing of %s OK" % fileURI
      
      print "Created on %s, expires on %s" % (creationF, expireF)
      print "URL : %s" % (url)
   else :
      print "* Publishing of %s failed ! (is it already published ?)" % fileURI
   
   return;

def unpublish(folder, name):
   fileURI = os.path.join(folder, name)
   
   theFile = getFile(fileURI)
   
   if theFile == None:
      print "File not found : %s" % (fileURI)
      return
   
   mime = theFile['type']
   
   isFile = (mime != 'application/directory')
   
   headers = {'User-Agent': userAgent, 'Origin': 'https://app.hubic.me'}
   payload = {'action': 'unpublish', 'folder': folder, 'name': name, 'container' : 'default', 'isFile': isFile}
   r = sess.post("https://app.hubic.me/v2/actions/ajax/hubic-browser.php", data=payload, headers=headers)
      
   if r.status_code != 200:
      print "* Unpublish of %s failed !" % fileURI
      return
   
   resp = r.json()
   
   if resp['answer'] and resp['answer']['status'] and resp['answer']['status'] == 200:
      print "* Unpublish of %s OK" % fileURI
   else :
      print "* Unpublish of %s failed ! (is it really published ?)" % fileURI
   
   return;

def walkDict( aDict, visitor, filename, path=() ):
    global fileFound
    
    if fileFound == True:
        return;
    
    for  k in aDict:
        if k == 'props':
            visitor( path, aDict[k], filename )
        elif type(aDict[k]) != dict:
            pass
        else:
            walkDict( aDict[k], visitor, filename, path+(k,) )

def getFileInfos(filename):
   global filesList
   
   data = filesList
   
   walkDict( data, filterFor, filename )
   
   if foundFile :
      return True
   else:
      return False

def fileExists(filename):
   f = getFile(filename)
   
   if f != None:
      return true
   else:
      return false

def getFile(filename):
   global filesList
   
   data = filesList
   
   return searchForFilename(data, searchForFilenameSub, filename)

def searchForFilename(aDict, visitor, filename, path=(), key='props'):
    for k in aDict:
        if k == 'props':
            f = visitor(path, aDict[k], filename)
            
            if f != None:
               return f
        elif type(aDict[k]) != dict:
            pass
        else:
            f = searchForFilename(aDict[k], visitor, filename, path+(k,))
            if f != None:
               return f

def searchForFilenameSub(path, element, filename, key='uri'):
    try:
       element['uri']
    except KeyError:
       pass
    else:
       if element['uri'] == filename:
          return element
       else:
          return None;

def filterFor(path, element, filename):
    global FILESTODOWN
    
    try:
       element['uri']
    except KeyError:
       pass
    else:
       if element['uri'].startswith(filename):
          FILESTODOWN.append(element)
          return

def checkDownload(folder, name):
   global sessionHash
   
   filename = "%s%s" % (folder, name)
   
   headers = {'User-Agent': userAgent, 'Origin': 'https://app.hubic.me'}
   payload = {'action': 'checkDl', 'folder': folder, 'name': filename, 'isFile': 'true', 'secret': sessionHash}
   r = sess.post("https://app.hubic.me/v2/actions/ajax/hubic-browser.php", data=payload, headers=headers)
   
   resp = r.json()
   
   if resp['answer']['status'] == 200:
      print "* Download check of %s OK" % (filename)
      print ""
   else :
      print "* Download check of %s NOT OK !!!" % (filename)
      print ""
   
   return

def logout():
   payload = {'action': 'unload'}
   r = sess.post("https://app.hubic.me/v2/actions/ajax/logoff.php", data=payload, headers=headers)
   
   print
   print "* Successfuly logged out"
   print
   print "* Stopping hubiCLI..."
   print
   
   return

def getLocalFileSize(filename): 
    statinfo = os.stat(filename)
    return statinfo.st_size

def sizeof_fmt(num):
    for x in ['bytes','KB','MB','GB']:
        if num < 1024.0:
            return "%3.1f%s" % (num, x)
        num /= 1024.0
    return "%3.1f%s" % (num, 'TB')

login()
getSettings()
getFilesList()

if arguments['--download'] == True:
   download(arguments['FILES'])

if arguments['--download-zip'] == True:
   downloadZipped(arguments['SRC'], arguments['FILES'])

if arguments['--download-folder'] == True:
   downloadAll(arguments['SRC'])

if arguments['--upload'] == True:
   upload(arguments['DEST'], arguments['FILES'])

if arguments['--upload-folder'] == True:
   uploadAll(arguments['SRC'], arguments['DEST'])

if arguments['--move'] == True:
   move(arguments['SRC'], arguments['DEST'], arguments['FILE'])

if arguments['--rename'] == True:
   rename(arguments['SRC'], arguments['OLD'], arguments['NEW'])

if arguments['--create-folder'] == True:
   createFolder(arguments['SRC'], arguments['NAME'])

if arguments['--delete'] == True:
   delete(arguments['SRC'], arguments['NAME'])

if arguments['--publish'] == True:
   publish(arguments['SRC'], arguments['NAME'], arguments['DURATION'], arguments['MESSAGE'])

if arguments['--unpublish'] == True:
   unpublish(arguments['SRC'], arguments['NAME'])

if arguments['--list'] == True:
   listFiles(arguments['SRC'])

if arguments['--download'] == False and arguments['--upload'] == False and arguments['--download-folder'] == False and arguments['--upload-folder'] == False:
   logout()

#CS 455 Homework 2 - HTTP PRoxy Server
#David Parrott
#Fall 2014

import threading, sys, socket, select, time
from collections import deque

#Global variables uesd to customize script defaults
#DEFAULT_PORT is used as the port to listen on if one is not specified when executing the script
#BACKLOG is how many connections allowed in the queue
#BUFFER is passed to recv()
DEFAULT_PORT = 8080
BACKLOG = 10
BUFFER = 1024

#Custom dictionary class that will hold the cache as well as information about it. Custom methods
#added to increase script readability.
#Upon declaration of a new Dictionary an empty cache and deque are created along with a lock
#insert checks if the cache is 'full' and removes the oldest entry if so
#delete is used to remove an entry from both the cache and the deque
#exists simply checks if a given url is listed in the cache
#get returns the entry associated with a given url
#remove_lru pops the oldest entry off the deque and then also removes it from the cache
class Dictionary(object):
    def __init__(self):
        self.cache = {}
        self.deck = deque([], maxlen=100)
        self.lock = threading.Lock()

    def insert(self, url, entry):
        self.lock.acquire()
        if len(self.deck) == self.deck.maxlen:
            print "MAX CACHE LENGTH REACHED"
            self.remove_lru()
        self.cache[url] = entry
        self.deck.appendleft(url)
        self.lock.release()

    def delete(self, url):
        self.lock.acquire()
        self.cache.pop(url, None)
        self.deck.remove(url)
        self.lock.release()

    def exists(self, url):
        return url in self.cache

    def get(self, url):
        return self.cache[url]

    def remove_lru(self):
        self.lock.acquire()
        url = self.deck.pop()
        self.cache.pop(url, None)
        self.lock.release()

#Entry was created to hold relevant data about a cached item
#time_cached holds the time that the script last cached the url
#content holds the entire response from the server
#url is the url
class Entry:
    def __init__(self, time_cached, content, url):
        self.time_cached = time_cached
        self.content = content
        self.url = url
    description = "Empty cache entry"

#create a new cache. Stored globally instead of being passed since there will not
#be more than one cache in use at a time
cache = Dictionary()

#recvall takes a socket and reads all data sent, accumulating it in whole before returning it.
#select is used to determine when the socket can be read from
#this function originally authored Frankie Primerano
#https://github.com/Max00355/PyProxy/blob/master/pyproxy.py
def recvall(sock):
    whole = b""
    while True:
        read, write, error = select.select([sock], [], [], 0.5)
        if read:
            piece = sock.recv(BUFFER)
            if piece:
                whole += piece
            else:
                break
        else:
            break
    return whole

#parses a given request to return the hostname, IP of the host, request from the client and the page url
#split is used to break the original request into parts which are then also broken up.
#split_request holds each line of the original request delimited on the newline character
#first_line holds the request from the client found in split_request[0]
#host starts as the second oine of the original request found in split_request[1]. The extraneous
#characters are stripped leaving just the host name
#url is extracted from the first_line and assumes that the original request is formatted as a standard
#HTTP header
def parse_request(request):
    try:
        split_request = request.split('\n')
        first_line = split_request[0]
        host = split_request[1]
        host = host.split(':')[1]
        host = host[1:-1]
        url = first_line.split(' ')[1]
    except:
        return
    try:
        ip = socket.gethostbyname(host)
    except socket.gaierror as e:
#        print "EXCEPTION IN PARSE: ", str(e)
        host = "UNRESOLVED"
    return host, ip, first_line, url

#this is the main workhorse of the script. When a new thread is started in main a socket is passed to
#handler. The entire request is read from the client and stored in raw_request. This is then parsed
#to eliminate any artifacts in the event that the client has not turned off their browser's cache.
#the altered request is passed to parse_request and the relevant data is stored before the
#request from the client is displayed on STDOUT.

#If the entry is not found in the cache then the altered request is sent to the server and the response
#is both stored in a new entry and also passed on to the client before closing the sockets with both
#the client and server

#If the entry is found in the cache the time that it was cached at is put into an If-Modified-Since
#before the new request is sent to the server. If the server responds with a 304 indicating that the
#page has not been modified since the date cached the content is retrieved and sent to the client.
#If the page has changed since it was last cached then the page is requested from the server. The
#response is stored in a new entry and the entry containing the stale content is removed from the
#cache. Finally the response is sent to the client before the server and client sockets are closed
def handler(client, addr):
    raw_request = recvall(client)
    split = raw_request.split('\n')
    for line in split:
        if "If-Modified-Since" in line:
            split.remove(line)
            break
    for line in split:
        if "If-None-Match" in line:
            split.remove(line)
            break
    my_request = '\n'.join(split)
    try:
        host, ip, request, url = parse_request(my_request)
        print "[-]",request
    except BaseException as e:
#        print "EXCEPTION: ", str(e)
        client.close()
        return
    if not cache.exists(url):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, 80))
            sock.send(my_request)
            response = recvall(sock)
            if response:
                client.send(response)
                entry = Entry(time.asctime(time.localtime(time.time())), response, url)
                cache.insert(url, entry)
            sock.close()
            client.close()
        except socket.gaierror:
            client.close()

    else:
        entry = cache.get(url)
        split = raw_request.split('\n')
        for line in split:
            if "If-None-Match" in line:
                split.remove(line)
                break
        i = 0
        for line in split:
            if "If-Modified-Since" in line:
                index = line.find(': ')
                line = line[:index+2]
                split[i] = line + str(entry.time_cached) + '\r\n'
                print split[i]
                break
            i += 1
        cache_request = '\n'.join(split)
        #print cache_request

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, 80))
            sock.send(cache_request)
            response = recvall(sock)
            if response:
                if "304" in response:
                    #print "GOT 304 SENDING CACHED CONTENT"
                    #print response
                    content = entry.content
                    client.send(content)
                else:
                    #print "REQUESTED PAGE ALTERED RECACHING CONTENT"
                    cache.delete(entry.url)
                    client.send(response)
                    entry = Entry(time.asctime(time.localtime(time.time())), response, url)
                    cache.insert(url, entry)
            sock.close()
            client.close()
        except socket.gaierror:
            client.close()

#Handles initial socket creation and thread creation. Listens on either a port passed during
#script execution or, if none is provided, the default port is used instead.
def main():
    if len(sys.argv) < 2:
        print "No port specified. Using default port: ", DEFAULT_PORT
        port = DEFAULT_PORT
    else:
        port = int(sys.argv[1])

    print "Proxy Server running on port: ", port

    proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy_socket.bind(('', port))
    proxy_socket.listen(BACKLOG)
    while 1:
        try:
            client_socket, addr = proxy_socket.accept()
            t = threading.Thread(target=handler, args=(client_socket,addr))
            t.daemon = True
            t.start()
        except KeyboardInterrupt:
            break
    proxy_socket.close()


if __name__ == '__main__':
    main()
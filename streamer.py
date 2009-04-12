import mad
import ao
import socket
import urlparse
import urllib

class FileTypeHandler:
    def __init__(self, path, isStream):
        self.path = path
        self.isStream = isStream

    def loadFile(self):
        if self.isStream:
            return self.loadStreamFile()
        else:
            return self.loadNormalFile()

    def loadStreamFile(self):
        raise NotImplementedError

    def loadNormalFile(self):
        raise NotImplementedError

class MP3Handler(FileTypeHandler):
    def setupSocket(self, host, port, requestLoc):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, int(port)))
        sock.send('GET %s HTTP/1.0\r\n\r\n' % requestLoc)
        idata = sock.recv(1500)
        return sock

    def loadStreamFile(self):
        scheme, dest, realpath, params, query, frag = urlparse.urlparse(self.path)
        try:
            host, port = dest.split(":")
        except ValueError:
            host, port = dest, 80
        if not realpath:
            realpath = '/'
        sockfile = self.setupSocket(host, port, realpath).makefile()
        madfile = mad.MadFile(sockfile)
        return ((madfile.bitrate, madfile.samplerate()), madfile)

    def loadNormalFile(self):
        fsfile = urllib.urlopen(self.path)
        madfile = mad.MadFile(sockfile)
        return ((madfile.bitrate, madfile.samplerate()), madfile)

class AudioHandler:
    def __init__(self, handlerInst):
        self.handle = handlerInst

    def doPlay(self):
        dev = open("/dev/sound", "wb")
        fdtuple = self.handle.loadFile()
        while True:
            b = fdtuple[1].read()
            if b is None:
                break
            dev.write(b)

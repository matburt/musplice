import mad
import socket
import urlparse
import urllib
import optparse
import sys
import threading
from ConfigParser import RawConfigParser

class FileTypeHandler:
    def __init__(self, path, isStream):
        self.path = path
        self.isStream = isStream

    def setupSocket(self, host, port, requestLoc):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, int(port)))
        sock.send('GET %s HTTP/1.0\r\n\r\n' % requestLoc)
        idata = sock.recv(1500)
        return sock

    def getSockFd(self):
        scheme, dest, realpath, params, query, frag = urlparse.urlparse(self.path)
        try:
            host, port = dest.split(":")
        except ValueError:
            host, port = dest, 80
        if not realpath:
            realpath = '/'
        return self.setupSocket(host, port, realpath).makefile()

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
    def loadStreamFile(self):
        sockfile = self.getSockFd()
        madfile = mad.MadFile(sockfile)
        return ((madfile.bitrate, madfile.samplerate()), madfile)

    def loadNormalFile(self):
        fsfile = urllib.urlopen(self.path)
        madfile = mad.MadFile(sockfile)
        return ((madfile.bitrate, madfile.samplerate()), madfile)

class AudioHandler:
    def __init__(self, handlerInst, device):
        self.handle = handlerInst
        self.device = device
        self.shouldPlay = True

    def doStop(self):
        self.shouldPlay = False

    def doPlay(self):
        if self.device == "alsa":
            self.doPlayAlsa()
        elif self.device.find("dev") != -1:
            self.doPlayOss()

    def doPlayOss(self):
        dev = open(self.device, "wb")
        fdtuple = self.handle.loadFile()
        while self.shouldPlay:
            b = fdtuple[1].read()
            if b is None:
                break
            dev.write(b)
        dev.close()

    def doPlayAlsa(self):
        try:
            import alsaaudio
        except ImportError:
            print("Missing ALSA support, install pyalsaaudio")
            return
        pcma = alsaaudio.PCM(type=alsaaudio.PCM_PLAYBACK,
                             mode=alsaaudio.PCM_NORMAL,
                             card="default")
        fdtuple = self.handle.loadFile()
        while self.shouldPlay:
            b = fdtuple[1].read()
            if b is None:
                break
            pcma.write(b)

def playListLoop(config):
    while True:
        for plEntry in config.sections():
            if plEntry == "musplice":
                continue
            if not config.has_option(plEntry, "location") or \
                    not config.has_option(plEntry, "time") or \
                    not config.has_option(plEntry, "stream"):
                print("Skipping unknown section %s (missing option)" % plEntry)
                continue
            mp3loc = config.get(plEntry, "location")
            ttp = config.get(plEntry, "time")
            isStream = config.getboolean(plEntry, "stream")

            mp3h = MP3Handler(mp3loc, isStream)
            ah = AudioHandler(mp3h, config.get("musplice", "device"))

            if ttp != "all":
                evTimer = threading.Timer(int(ttp), ah.doStop)
                evTimer.start()
            print("%s" % plEntry)
            ah.doPlay()


if __name__ == "__main__":
    op = optparse.OptionParser()
    cp = RawConfigParser()

    op.add_option("-c", "--config", dest="config", help="Configuration File")
    (options, args) = op.parse_args()

    if options.config is not None:
        cp.read(options.config)
        playListLoop(cp)
    else:
        print("Configuration file required.")
        sys.exit(1)

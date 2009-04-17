import mad
import socket
import ossaudiodev
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
        else:
            self.doPlayOss()

    def doPlayRaw(self):
        dev = open(self.device, "wb")
        fdtuple = self.handle.loadFile()
        while self.shouldPlay:
            buf = fdtuple[1].read()
            if buf is None:
                break
            dev.write(buf)
        dev.close()

    def doPlayOss(self):
        dev = ossaudiodev.open(self.device, "w")
        fdtuple = self.handle.loadFile()
        dev.setfmt(ossaudiodev.AFMT_S16_LE)
        dev.channels(2)
        dev.speed(fdtuple[0][1])
        print("[oss] samplerate %s" % str(fdtuple[0][1]))
        while self.shouldPlay:
            buf = fdtuple[1].read()
            if buf is None:
                break
            dev.write(buf)
        dev.close()

    def doPlayAlsa(self):
        try:
            import alsaaudio
        except ImportError:
            print("Missing ALSA support, install pyalsaaudio")
            return

        framebase = 8192
        pcma = alsaaudio.PCM(type=alsaaudio.PCM_PLAYBACK,
                             mode=alsaaudio.PCM_NORMAL,
                             card="default")
        fdtuple = self.handle.loadFile()
        pcma.setrate(fdtuple[0][1])
        pcma.setformat(alsaaudio.PCM_FORMAT_S16_LE)
        pcma.setperiodsize(160)
        print("[alsa] samplerate %s" % str(fdtuple[0][1]))
        fillbuf = buffer('')
        while self.shouldPlay:
            fillbuf += fdtuple[1].read()
            if fillbuf is None:
                break
            if len(fillbuf) > framebase:
                pcma.write(fillbuf)
                fillbuf = buffer('')

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

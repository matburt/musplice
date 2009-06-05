import mad
import socket
import ossaudiodev
import urlparse
import urllib
import optparse
import sys
import threading
import time
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
        self.shouldNext = False

    def doStop(self):
        self.shouldPlay = False

    def doNext(self):
        self.shouldNext = True

    def doShow(self):
        print("Now Playing: %s" % self.handle.path)

    def doPlay(self):
        if self.device == "alsa":
            return self.doPlayAlsa()
        else:
            return self.doPlayOss()

    def doPlayRaw(self):
        dev = open(self.device, "wb")
        fdtuple = self.handle.loadFile()
        while self.shouldPlay:
            buf = fdtuple[1].read()
            if buf is None or self.shouldNext:
                break
            dev.write(buf)
        dev.close()
        fdtuple[1].close()
        if self.shouldPlay:
            return True
        else:
            return False

    def doPlayOss(self):
        dev = ossaudiodev.open(self.device, "w")
        fdtuple = self.handle.loadFile()
        dev.setfmt(ossaudiodev.AFMT_S16_LE)
        dev.channels(2)
        dev.speed(fdtuple[0][1])
        while self.shouldPlay:
            buf = fdtuple[1].read()
            if buf is None or self.shouldNext:
                break
            dev.write(buf)
        dev.close()
        return self.shouldPlay

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
        fillbuf = buffer('')
        while self.shouldPlay:
            fillbuf += fdtuple[1].read()
            if fillbuf is None or self.shouldNext:
                break
            if len(fillbuf) > framebase:
                pcma.write(fillbuf)
                fillbuf = buffer('')
        return self.shouldPlay

def playListLoop(config, commandThread=None):
    def cliThread():
        running = True
        while running:
            sys.stdout.write("musplice>> ")
            cmd = sys.stdin.readline()
            if len(cmd) < 1 or cmd[0] == 'q':
                ah.doStop()
                running = False
            elif cmd[0] == 'p':
                ah.doShow()
            elif cmd[0] == 'n':
                ah.doNext()
            elif cmd[0] == '?':
                print('q - Quit')
                print('p - Whats playing?')
                print('n - Next stream')

    if commandThread:
        cThread = threading.Thread(target=commandThread)
    else:
        cThread = threading.Thread(target=cliThread)
    cThread.start()

    while True:
        for plEntry in config.sections():
            if plEntry == "musplice":
                continue
            if not config.has_option(plEntry, "location") or \
                    not config.has_option(plEntry, "time"):
                print("Skipping unknown section %s (missing option)" % plEntry)
                continue
            mp3loc = config.get(plEntry, "location")
            ttp = config.get(plEntry, "time")
            if config.has_option(plEntry, "stream"):
                isStream = config.getboolean(plEntry, "stream")
            else:
                isStream = True

            mp3h = MP3Handler(mp3loc, isStream)
            ah = AudioHandler(mp3h, config.get("musplice", "device"))

            if ttp != "all":
                evTimer = threading.Timer(int(ttp), ah.doNext)
                evTimer.start()
            if not ah.doPlay():
                return

def main():
    op = optparse.OptionParser()
    cp = RawConfigParser()

    op.add_option("-c", "--config", dest="config", help="Configuration File")
    (options, args) = op.parse_args()

    if options.config is not None:
        cp.read(options.config)
        playListLoop(cp)
        sys.exit(0)
    else:
        print("Configuration file required.")
        sys.exit(1)

if __name__ == "__main__":
    main()

"""
GZip that doesn't include the timestamp
"""
import gzip

class GzipFile(gzip.GzipFile):

    def _write_gzip_header(self):
        self.fileobj.write('\037\213')             # magic header
        self.fileobj.write('\010')                 # compression method
        fname = self.filename[:-3]
        flags = 0
        if fname:
            flags = gzip.FNAME
        self.fileobj.write(chr(flags))
        ## This is what WebOb patches:
        gzip.write32u(self.fileobj, long(0))
        self.fileobj.write('\002')
        self.fileobj.write('\377')
        if fname:
            self.fileobj.write(fname + '\000')

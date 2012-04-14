import os 
import tarfile
import cPickle as pickle

files = os.listdir('./')
data_files = []
for ii in files:
  if 'out' in ii:
    data_files.append(ii)
for ii in data_files:
  FILE = open(ii, 'r')
  buf = FILE.read()
  data = pickle.loads(buf)
  print len(data)
  for ii in data['cols']:
    print ii[0]
    print ii


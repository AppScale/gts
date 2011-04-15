# See LICENCE file
import os, pwd, grp

def drop_privileges(uid_name='nobody', gid_name='nogroup'):
  starting_uid = os.getuid()
  starting_gid = os.getgid()
  starting_uid_name = pwd.getpwuid(starting_uid)[0]

  # If not root, return #
  if starting_uid != 0: return

  # If root, drop privs and become the specified user/group
  elif starting_uid == 0:
    # Get the uid/gid from the name #
    try: running_uid = pwd.getpwnam(uid_name)[2]
    except Exception, e: print('Could not set effective group id: %s' % e); return
    try:  running_gid = grp.getgrnam(gid_name)[2]
    except Exception, e: print('Could not set effective group id: %s' % e); return
    # Try setting the new uid/gid #
    try: os.setgid(running_gid)
    except OSError, e: print('Could not set effective group id: %s' % e); return 

    try: os.setuid(running_uid)
    except OSError, e: print('Could not set effective user id: %s' % e); return

    # Ensure a very conservative umask #
    new_umask = 700
    old_umask = os.umask(new_umask)

"""Performs a 3-way merge for GIT files
"""

__copyright__ = """
Copyright (C) 2006, Catalin Marinas <catalin.marinas@gmail.com>

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License version 2 as
published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
"""

import sys, os
from stgit.config import config
from stgit.utils import append_string


class GitMergeException(Exception):
    pass


#
# Options
#
try:
    merger = config.get('gitmergeonefile', 'merger')
except Exception, err:
    raise GitMergeException, 'Configuration error: %s' % err

if config.has_option('gitmergeonefile', 'keeporig'):
    keeporig = config.get('gitmergeonefile', 'keeporig')
else:
    keeporig = 'yes'


#
# Utility functions
#
def __str2none(x):
    if x == '':
        return None
    else:
        return x

def __output(cmd):
    f = os.popen(cmd, 'r')
    string = f.readline().rstrip()
    if f.close():
        raise GitMergeException, 'Error: failed to execute "%s"' % cmd
    return string

def __checkout_files(orig_hash, file1_hash, file2_hash,
                     path,
                     orig_mode, file1_mode, file2_mode):
    """Check out the files passed as arguments
    """
    global orig, src1, src2

    if orig_hash:
        orig = '%s.older' % path
        tmp = __output('git-unpack-file %s' % orig_hash)
        os.chmod(tmp, int(orig_mode, 8))
        os.renames(tmp, orig)
    if file1_hash:
        src1 = '%s.local' % path
        tmp = __output('git-unpack-file %s' % file1_hash)
        os.chmod(tmp, int(file1_mode, 8))
        os.renames(tmp, src1)
    if file2_hash:
        src2 = '%s.remote' % path
        tmp = __output('git-unpack-file %s' % file2_hash)
        os.chmod(tmp, int(file2_mode, 8))
        os.renames(tmp, src2)

def __remove_files(orig_hash, file1_hash, file2_hash):
    """Remove any temporary files
    """
    if orig_hash:
        os.remove(orig)
    if file1_hash:
        os.remove(src1)
    if file2_hash:
        os.remove(src2)
    pass

# GIT_DIR value cached
__base_dir = None

def __conflict(path):
    """Write the conflict file for the 'path' variable and exit
    """
    global __base_dir

    if not __base_dir:
        if 'GIT_DIR' in os.environ:
            __base_dir = os.environ['GIT_DIR']
        else:
            __base_dir = __output('git-rev-parse --git-dir')

    append_string(os.path.join(__base_dir, 'conflicts'), path)


#
# Main algorithm
#
def merge(orig_hash, file1_hash, file2_hash,
          path,
          orig_mode, file1_mode, file2_mode):
    """Three-way merge for one file algorithm
    """
    __checkout_files(orig_hash, file1_hash, file2_hash,
                     path,
                     orig_mode, file1_mode, file2_mode)

    # file exists in origin
    if orig_hash:
        # modified in both
        if file1_hash and file2_hash:
            # if modes are the same (git-read-tree probably dealt with it)
            if file1_hash == file2_hash:
                if os.system('git-update-index --cacheinfo %s %s %s'
                             % (file1_mode, file1_hash, path)) != 0:
                    print >> sys.stderr, 'Error: git-update-index failed'
                    __conflict(path)
                    return 1
                if os.system('git-checkout-index -u -f -- %s' % path):
                    print >> sys.stderr, 'Error: git-checkout-index failed'
                    __conflict(path)
                    return 1
                if file1_mode != file2_mode:
                    print >> sys.stderr, \
                          'Error: File added in both, permissions conflict'
                    __conflict(path)
                    return 1
            # 3-way merge
            else:
                merge_ok = os.system(merger % {'branch1': src1,
                                               'ancestor': orig,
                                               'branch2': src2,
                                               'output': path }) == 0

                if merge_ok:
                    os.system('git-update-index -- %s' % path)
                    __remove_files(orig_hash, file1_hash, file2_hash)
                    return 0
                else:
                    print >> sys.stderr, \
                          'Error: three-way merge tool failed for file "%s"' \
                          % path
                    # reset the cache to the first branch
                    os.system('git-update-index --cacheinfo %s %s %s'
                              % (file1_mode, file1_hash, path))
                    if keeporig != 'yes':
                        __remove_files(orig_hash, file1_hash, file2_hash)
                    __conflict(path)
                    return 1
        # file deleted in both or deleted in one and unchanged in the other
        elif not (file1_hash or file2_hash) \
               or file1_hash == orig_hash or file2_hash == orig_hash:
            if os.path.exists(path):
                os.remove(path)
            __remove_files(orig_hash, file1_hash, file2_hash)
            return os.system('git-update-index --remove -- %s' % path)
        # file deleted in one and changed in the other
        else:
            # Do something here - we must at least merge the entry in
            # the cache, instead of leaving it in U(nmerged) state. In
            # fact, stg resolved does not handle that.

            # Do the same thing cogito does - remove the file in any case.
            os.system('git-update-index --remove -- %s' % path)

            #if file1_hash:
                ## file deleted upstream and changed in the patch. The
                ## patch is probably going to move the changes
                ## elsewhere.

                #os.system('git-update-index --remove -- %s' % path)
            #else:
                ## file deleted in the patch and changed upstream. We
                ## could re-delete it, but for now leave it there -
                ## and let the user check if he still wants to remove
                ## the file.

                ## reset the cache to the first branch
                #os.system('git-update-index --cacheinfo %s %s %s'
                #          % (file1_mode, file1_hash, path))
            __conflict(path)
            return 1

    # file does not exist in origin
    else:
        # file added in both
        if file1_hash and file2_hash:
            # files are the same
            if file1_hash == file2_hash:
                if os.system('git-update-index --add --cacheinfo %s %s %s'
                             % (file1_mode, file1_hash, path)) != 0:
                    print >> sys.stderr, 'Error: git-update-index failed'
                    __conflict(path)
                    return 1
                if os.system('git-checkout-index -u -f -- %s' % path):
                    print >> sys.stderr, 'Error: git-checkout-index failed'
                    __conflict(path)
                    return 1
                if file1_mode != file2_mode:
                    print >> sys.stderr, \
                          'Error: File "s" added in both, ' \
                          'permissions conflict' % path
                    __conflict(path)
                    return 1
            # files are different
            else:
                print >> sys.stderr, \
                      'Error: File "%s" added in branches but different' % path
                __conflict(path)
                return 1
        # file added in one
        elif file1_hash or file2_hash:
            if file1_hash:
                mode = file1_mode
                obj = file1_hash
            else:
                mode = file2_mode
                obj = file2_hash
            if os.system('git-update-index --add --cacheinfo %s %s %s'
                         % (mode, obj, path)) != 0:
                print >> sys.stderr, 'Error: git-update-index failed'
                __conflict(path)
                return 1
            __remove_files(orig_hash, file1_hash, file2_hash)
            return os.system('git-checkout-index -u -f -- %s' % path)

    # Unhandled case
    print >> sys.stderr, 'Error: Unhandled merge conflict: ' \
          '"%s" "%s" "%s" "%s" "%s" "%s" "%s"' \
          % (orig_hash, file1_hash, file2_hash,
             path,
             orig_mode, file1_mode, file2_mode)
    __conflict(path)
    return 1
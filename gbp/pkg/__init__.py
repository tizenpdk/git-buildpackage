# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007 Guido Guenther <agx@sigxcpu.org>
# (C) 2012 Intel Corporation <markus.lehtonen@linux.intel.com>
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""Common functionality of the Debian/RPM package helpers"""

import os
import re
import glob

import gbp.command_wrappers as gbpc
from gbp.errors import GbpError

# compression types, extra options and extensions
compressor_opts = { 'gzip'  : [ ['-n'], 'gz' ],
                    'bzip2' : [ [], 'bz2' ],
                    'lzma'  : [ [], 'lzma' ],
                    'xz'    : [ [], 'xz' ] }

# Map frequently used names of compression types to the internal ones:
compressor_aliases = { 'bz2' : 'bzip2',
                       'gz'  : 'gzip', }

# Supported archive formats
arhive_formats = [ 'tar', 'zip' ]

# Map combined file extensions to arhive and compression format
archive_ext_aliases = { 'tgz'   : ('tar', 'gzip'),
                        'tbz2'  : ('tar', 'bzip2'),
                        'tlz'   : ('tar', 'lzma'),
                        'txz'   : ('tar', 'xz')}

def parse_archive_filename(filename):
    """
    Given an filename return the basename (i.e. filename without the
    archive and compression extensions), archive format and compression
    method used.

    @param filename: the name of the file
    @type filename: string
    @return: tuple containing basename, archive format and compression method
    @rtype: C{tuple} of C{str}

    >>> parse_archive_filename("abc.tar.gz")
    ('abc', 'tar', 'gzip')
    >>> parse_archive_filename("abc.tar.bz2")
    ('abc', 'tar', 'bzip2')
    >>> parse_archive_filename("abc.def.tbz2")
    ('abc.def', 'tar', 'bzip2')
    >>> parse_archive_filename("abc.def.tar.xz")
    ('abc.def', 'tar', 'xz')
    >>> parse_archive_filename("abc.zip")
    ('abc', 'zip', None)
    >>> parse_archive_filename("abc.lzma")
    ('abc', None, 'lzma')
    >>> parse_archive_filename("abc.tar.foo")
    ('abc.tar.foo', None, None)
    >>> parse_archive_filename("abc")
    ('abc', None, None)
    """
    (base_name, archive_fmt, compression) = (filename, None, None)

    # Split filename to pieces
    split = filename.split(".")
    if len(split) > 1:
        if split[-1] in archive_ext_aliases:
            base_name = ".".join(split[:-1])
            (archive_fmt, compression) = archive_ext_aliases[split[-1]]
        elif split[-1] in arhive_formats:
            base_name = ".".join(split[:-1])
            (archive_fmt, compression) = (split[-1], None)
        else:
            for (c, o) in compressor_opts.iteritems():
                if o[1] == split[-1]:
                    base_name = ".".join(split[:-1])
                    compression = c
                    if len(split) > 2 and split[-2] in arhive_formats:
                        base_name = ".".join(split[:-2])
                        archive_fmt = split[-2]

    return (base_name, archive_fmt, compression)


class PkgPolicy(object):
    """
    Common helpers for packaging policy.
    """
    packagename_re = None
    packagename_msg = None
    upstreamversion_re = None
    upstreamversion_msg = None

    @classmethod
    def is_valid_packagename(cls, name):
        """
        Is this a valid package name?

        >>> PkgPolicy.is_valid_packagename('doesnotmatter')
        Traceback (most recent call last):
        ...
        NotImplementedError: Class needs to provide packagename_re
        """
        if cls.packagename_re is None:
            raise NotImplementedError("Class needs to provide packagename_re")
        return True if cls.packagename_re.match(name) else False

    @classmethod
    def is_valid_upstreamversion(cls, version):
        """
        Is this a valid upstream version number?

        >>> PkgPolicy.is_valid_upstreamversion('doesnotmatter')
        Traceback (most recent call last):
        ...
        NotImplementedError: Class needs to provide upstreamversion_re
        """
        if cls.upstreamversion_re is None:
            raise NotImplementedError("Class needs to provide upstreamversion_re")
        return True if cls.upstreamversion_re.match(version) else False

    @classmethod
    def is_valid_orig_archive(cls, filename):
        "Is this a valid orig source archive"
        (base, arch_fmt, compression) =  parse_archive_filename(filename)
        if arch_fmt == 'tar' and compression:
            return True
        return False

    @staticmethod
    def has_orig(orig_file, dir):
        "Check if orig tarball exists in dir"
        try:
            os.stat( os.path.join(dir, orig_file) )
        except OSError:
            return False
        return True

    @staticmethod
    def symlink_orig(orig_file, orig_dir, output_dir, force=False):
        """
        symlink orig tarball from orig_dir to output_dir
        @return: True if link was created or src == dst
                 False in case of error or src doesn't exist
        """
        orig_dir = os.path.abspath(orig_dir)
        output_dir = os.path.abspath(output_dir)

        if orig_dir == output_dir:
            return True

        src = os.path.join(orig_dir, orig_file)
        dst = os.path.join(output_dir, orig_file)
        if not os.access(src, os.F_OK):
            return False
        try:
            if os.access(dst, os.F_OK) and force:
                os.unlink(dst)
            os.symlink(src, dst)
        except OSError:
            return False
        return True


class UpstreamSource(object):
    """
    Upstream source. Can be either an unpacked dir, a tarball or another type
    of archive

    @cvar _orig: are the upstream sources already suitable as an upstream
                 tarball
    @type _orig: boolean
    @cvar _path: path to the upstream sources
    @type _path: string
    @cvar _unpacked: path to the unpacked source tree
    @type _unpacked: string
    """
    def __init__(self, name, unpacked=None, pkg_policy=PkgPolicy):
        self._orig = False
        self._tarball = False
        self._pkg_policy = pkg_policy
        self._path = name
        self.unpacked = unpacked
        self._filename_base, \
        self._archive_fmt, \
        self._compression = parse_archive_filename(os.path.basename(self.path))

        self._check_orig()
        if self.is_dir():
            self.unpacked = self.path

    def _check_orig(self):
        """
        Check if upstream source format can be used as orig tarball.
        This doesn't imply that the tarball is correctly named.

        @return: C{True} if upstream source format is suitable
            as upstream tarball, C{False} otherwise.
        @rtype: C{bool}
        """
        if self.is_dir():
            self._orig = False
            self._tarball = False
            return

        self._tarball = True if self.archive_fmt == 'tar' else False
        self._orig = self._pkg_policy.is_valid_orig_archive(os.path.basename(self.path))

    def is_orig(self):
        """
        @return: C{True} if sources are suitable as upstream source,
            C{False} otherwise
        @rtype: C{bool}
        """
        return self._orig

    def is_tarball(self):
        """
        @return: C{True} if source is a tarball, C{False} otherwise
        @rtype: C{bool}
        """
        return self._tarball

    def is_dir(self):
        """
        @return: C{True} if if upstream sources are an unpacked directory,
            C{False} otherwise
        @rtype: C{bool}
        """
        return True if os.path.isdir(self._path) else False

    @property
    def path(self):
        return self._path.rstrip('/')

    @property
    def archive_fmt(self):
        """
        >>> UpstreamSource('foo/bar.tar.gz').archive_fmt
        'tar'
        >>> UpstreamSource('foo.bar.zip').archive_fmt
        'zip'
        >>> UpstreamSource('foo.bar.baz').archive_fmt
        """
        return self._archive_fmt

    @property
    def compression(self):
        """
        >>> UpstreamSource('foo/bar.tar.gz').compression
        'gzip'
        >>> UpstreamSource('foo.bar.zip').compression
        >>> UpstreamSource('foo.bz2').compression
        'bzip2'
        """
        return self._compression

    def unpack(self, dir, filters=[]):
        """
        Unpack packed upstream sources into a given directory
        and determine the toplevel of the source tree.
        """
        if self.is_dir():
            raise GbpError("Cannot unpack directory %s" % self.path)

        if not filters:
            filters = []

        if type(filters) != type([]):
            raise GbpError("Filters must be a list")

        self._unpack_archive(dir, filters)
        self.unpacked = self._unpacked_toplevel(dir)

    def _unpack_archive(self, dir, filters):
        """
        Unpack packed upstream sources into a given directory.
        """
        ext = os.path.splitext(self.path)[1]
        if ext in [ ".zip", ".xpi" ]:
            self._unpack_zip(dir)
        else:
            self._unpack_tar(dir, filters)

    def _unpack_zip(self, dir):
        try:
            gbpc.UnpackZipArchive(self.path, dir)()
        except gbpc.CommandExecFailed:
            raise GbpError("Unpacking of %s failed" % self.path)

    def _unpacked_toplevel(self, dir):
        """unpacked archives can contain a leading directory or not"""
        unpacked = glob.glob('%s/*' % dir)
        unpacked.extend(glob.glob("%s/.*" % dir)) # include hidden files and folders
        # Check that dir contains nothing but a single folder:
        if len(unpacked) == 1 and os.path.isdir(unpacked[0]):
            return unpacked[0]
        else:
            # We can determine "no prefix" from this
            return os.path.join(dir, ".")

    def _unpack_tar(self, dir, filters):
        """
        Unpack a tarball to I{dir} applying a list of I{filters}. Leave the
        cleanup to the caller in case of an error.
        """
        try:
            unpackArchive = gbpc.UnpackTarArchive(self.path, dir, filters)
            unpackArchive()
        except gbpc.CommandExecFailed:
            # unpackArchive already printed an error message
            raise GbpError

    def pack(self, newarchive, filters=[], newprefix=None):
        """
        Recreate a new archive from the current one

        @param newarchive: the name of the new archive
        @type newarchive: string
        @param filters: tar filters to apply
        @type filters: array of strings
        @return: the new upstream source
        @rtype: UpstreamSource
        """
        if not self.unpacked:
            raise GbpError("Need an unpacked source tree to pack")

        if not filters:
            filters = []

        if type(filters) != type([]):
            raise GbpError("Filters must be a list")

        run_dir = os.path.dirname(self.unpacked.rstrip('/'))
        pack_this = os.path.basename(self.unpacked.rstrip('/'))
        transform = None
        if newprefix != None:
            newprefix = newprefix.strip('/.')
            if newprefix:
                transform = 's!%s!%s!' % (pack_this, newprefix)
            else:
                transform = 's!%s!%s!' % (pack_this, '.')
        try:
            repackArchive = gbpc.PackTarArchive(newarchive,
                                run_dir,
                                pack_this,
                                filters,
                                transform=transform)
            repackArchive()
        except gbpc.CommandExecFailed:
            # repackArchive already printed an error
            raise GbpError
        return type(self)(newarchive)

    @staticmethod
    def known_compressions():
        return [ args[1][-1] for args in compressor_opts.items() ]

    def guess_version(self, extra_regex=r''):
        """
        Guess the package name and version from the filename of an upstream
        archive.

        @param extra_regex: extra regular expression to check
        @type extra_regex: raw C{string}

        >>> UpstreamSource('foo-bar_0.2.orig.tar.gz').guess_version()
        ('foo-bar', '0.2')
        >>> UpstreamSource('foo-Bar_0.2.orig.tar.gz').guess_version()
        >>> UpstreamSource('git-bar-0.2.tar.gz').guess_version()
        ('git-bar', '0.2')
        >>> UpstreamSource('git-bar-0.2-rc1.tar.gz').guess_version()
        ('git-bar', '0.2-rc1')
        >>> UpstreamSource('git-bar-0.2:~-rc1.tar.gz').guess_version()
        ('git-bar', '0.2:~-rc1')
        >>> UpstreamSource('git-Bar-0A2d:rc1.tar.bz2').guess_version()
        ('git-Bar', '0A2d:rc1')
        >>> UpstreamSource('git-1.tar.bz2').guess_version()
        ('git', '1')
        >>> UpstreamSource('kvm_87+dfsg.orig.tar.gz').guess_version()
        ('kvm', '87+dfsg')
        >>> UpstreamSource('foo-Bar_0.2.orig.tar.gz').guess_version()
        >>> UpstreamSource('foo-Bar-a.b.tar.gz').guess_version()
        >>> UpstreamSource('foo-bar_0.2.orig.tar.xz').guess_version()
        ('foo-bar', '0.2')
        >>> UpstreamSource('foo-bar_0.2.orig.tar.lzma').guess_version()
        ('foo-bar', '0.2')

        @param extra_regex: additional regex to apply, needs a 'package' and a
                            'version' group
        @return: (package name, version) or None.
        @rtype: tuple
        """
        version_chars = r'[a-zA-Z\d\.\~\-\:\+]'
        if self.is_dir():
            extensions = ''
        else:
            extensions = r'\.tar\.(%s)' % "|".join(self.known_compressions())

        version_filters = map ( lambda x: x % (version_chars, extensions),
                           ( # Debian upstream tarball: package_'<version>.orig.tar.gz'
                             r'^(?P<package>[a-z\d\.\+\-]+)_(?P<version>%s+)\.orig%s',
                             # Upstream 'package-<version>.tar.gz'
                             # or directory 'package-<version>':
                             r'^(?P<package>[a-zA-Z\d\.\+\-]+)-(?P<version>[0-9]%s*)%s'))
        if extra_regex:
            version_filters = extra_regex + version_filters

        for filter in version_filters:
            m = re.match(filter, os.path.basename(self.path))
            if m:
                return (m.group('package'), m.group('version'))

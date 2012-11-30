%define do_unittests 0
%define with_docs 0

Name:       git-buildpackage
Summary:    Build packages from git
Version:    0.6.0git20130329
Release:    0
Group:      Development/Tools/Building
License:    GPLv2
BuildArch:  noarch
URL:        https://honk.sigxcpu.org/piki/projects/git-buildpackage/
Source0:    %{name}_%{version}.tar.gz
Requires:   %{name}-common = %{version}-%{release}
%if 0%{?fedora} || 0%{?centos_ver}
Requires:   dpkg-devel
%else
Requires:   dpkg
%endif
BuildRequires:  python
BuildRequires:  python-setuptools

%if 0%{?with_docs}
BuildRequires:  docbook-utils
BuildRequires:  gtk-doc
BuildRequires:  epydoc
%endif

%if 0%{?do_unittests}
BuildRequires:  python-coverage
BuildRequires:  python-nose
%endif

%description
Set of tools from Debian that integrate the package build system with Git.
This package contains the original Debian tools.


%package common
Summary:    Common files for git-buildpackage debian and rpm tools
Group:      Development/Tools/Building
Requires:   git-core

%if 0%{?fedora}
Requires:   man-db
%else
Requires:   man
%endif

%if 0%{?fedora} || 0%{?centos_ver} || 0%{?tizen_version:1}
Requires:   python
%else
Requires:   python-base
%endif

%description common
Common files and documentation, used by both git-buildpackage debian and rpm tools


%package rpm
Summary:    Build RPM packages from git
Group:      Development/Tools/Building
Requires:   %{name}-common = %{version}-%{release}
Requires:   rpm
%if 0%{?tizen_version:1}
Requires:   python-rpm
%else
Requires:   rpm-python
%endif
Provides:   tizen-gbp-rpm = 20130403

%description rpm
Set of tools from Debian that integrate the package build system with Git.
This package contains the tools for building RPM packages.



%prep
%setup -q -n %{name}-%{version}



%build
WITHOUT_NOSETESTS=1 python ./setup.py build

%if 0%{?with_docs}
# Prepare apidocs
epydoc -n git-buildpackage --no-sourcecode -o docs/apidocs/ \
    gbp*.py git*.py gbp/

# HTML docs
HAVE_SGML2X=0 make -C docs/
%endif


%if 0%{?do_unittests}
%check
GIT_CEILING_DIRECTORIES=%{_builddir} python setup.py nosetests
%endif


%install
rm -rf %{buildroot}
WITHOUT_NOSETESTS=1 python ./setup.py install --root=%{buildroot} --prefix=/usr
rm -rf %{buildroot}%{python_sitelib}/*info


%files
%defattr(-,root,root,-)
%dir %{python_sitelib}/gbp/deb
%{_bindir}/gbp-pq
%{_bindir}/git-buildpackage
%{_bindir}/git-dch
%{_bindir}/git-import-dsc
%{_bindir}/git-import-dscs
%{_bindir}/git-import-orig
%{_bindir}/git-pbuilder
%{_bindir}/gbp-create-remote-repo
%{python_sitelib}/gbp/deb/
%{python_sitelib}/gbp/scripts/pq.py*
%{python_sitelib}/gbp/scripts/buildpackage.py*
%{python_sitelib}/gbp/scripts/dch.py*
%{python_sitelib}/gbp/scripts/import_dsc.py*
%{python_sitelib}/gbp/scripts/import_dscs.py*
%{python_sitelib}/gbp/scripts/import_orig.py*
%{python_sitelib}/gbp/scripts/create_remote_repo.py*

%files common
%defattr(-,root,root,-)
%{_bindir}/gbp-clone
%{_bindir}/gbp-pull
%dir %{python_sitelib}/gbp
%dir %{python_sitelib}/gbp/git
%dir %{python_sitelib}/gbp/pkg
%dir %{python_sitelib}/gbp/scripts
%dir %{python_sitelib}/gbp/scripts/common
%{python_sitelib}/gbp/*.py*
%{python_sitelib}/gbp/scripts/__init__.py*
%{python_sitelib}/gbp/scripts/clone.py*
%{python_sitelib}/gbp/scripts/pull.py*
%{python_sitelib}/gbp/scripts/common/*.py*
%{python_sitelib}/gbp/git/*.py*
%{python_sitelib}/gbp/pkg/*.py*
%config %{_sysconfdir}/git-buildpackage


%files rpm
%defattr(-,root,root,-)
%dir %{python_sitelib}/gbp/rpm
%{_bindir}/*rpm*
%{python_sitelib}/gbp/scripts/*rpm.py*
%{python_sitelib}/gbp/rpm/*py*
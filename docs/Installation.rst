Installation
************

Overview
========

CMS runs on Linux. We test it on Debian and Ubuntu, but any modern
distribution should work, too.

You can run CMS as a Docker container. If you want to do so, please
continue to the :doc:`container installation instructions <Docker image>`.

Otherwise, please follow this chapter, which explains how to install CMS
and its dependencies.

.. _installation_dependencies:


Dependencies and available compilers
====================================

These are our requirements (in particular we highlight those that are not usually installed by default) - previous versions may or may not work:

* `PostgreSQL <http://www.postgresql.org/>`_ >= 9.4;

  .. We need 9.4 because of the JSONB data type.

* `GNU compiler collection <https://gcc.gnu.org/>`_ (in particular the C compiler ``gcc``);

* `Python <http://www.python.org/>`_ >= 3.11;

* `Isolate <https://github.com/ioi/isolate/>`_ >= 2.0;

* `pathlib <https://pypi.python.org/pypi/pathlib>`_;

* `TeX Live <https://www.tug.org/texlive/>`_ (only for printing);

* `a2ps <https://www.gnu.org/software/a2ps/>`_ (only for printing).

* `asymptote <http://asymptote.sourceforge.net/>`_ (for German task format; usage now deprecated)

* `latexmk <http://www.ctan.org/pkg/latexmk/>`_ (for German task format)

* `ttf-fira-go <https://github.com/bBoxType/FiraGO>`_ (for German task format + Hebrew)

* texlive-langcyrillic (or something similar; for German task format + Cyrillic)

* cairo (for captcha)

You will also require a Linux kernel with support for `cgroupv2 <https://docs.kernel.org/admin-guide/cgroup-v2.html>`_.

.. warning::
   Previous versions of ``isolate`` worked with ``cgroups v1``, but versions since 2.0 use ``cgroups v2``.
   If you are using a version before 2.0, you may have to add ``systemd.unified_cgroup_hierarchy=0`` to your kernel parameters (usually, add them to ``GRUB_CMDLINE_LINUX_DEFAULT`` in ``/etc/default/grub``, then re-make the GRUB configuration file) as most distros now use ``cgroups v2`` by default.
   If you are using version 2.0 or later, you must enable ``isolate.service`` (on distributions without systemd, you can alternatively use ``cgroupfs`` to create a cgroup, and write the path to ``/run/isolate/cgroup``).


Then you require the compilation and execution environments for the languages you will use in your contest:

* `GNU compiler collection <https://gcc.gnu.org/>`_ (for C and C++, respectively with executables ``gcc`` and ``g++``);

* for Java, your choice of a JDK, for example OpenJDK (but any other JDK behaving similarly is fine, for example Oracle's);

* `Free Pascal <http://www.freepascal.org/>`_ (for Pascal, with executable ``fpc``);

* `Python <http://www.python.org/>`_ (for Python, with executable ``python3``; in addition you will need ``zip``);

* `PHP <http://www.php.net>`_ (for PHP, with executable ``php``);

* `Glasgow Haskell Compiler <https://www.haskell.org/ghc/>`_ (for Haskell, with executable ``ghc``);

* `Rust <https://www.rust-lang.org/>`_ (for Rust, with executable ``rustc``);

* `C# <http://www.mono-project.com/docs/about-mono/languages/csharp/>`_ (for C#, with executable ``mcs``).

All dependencies can be installed automatically on most Linux distributions.

Ubuntu
------

.. warning::
   The instructions below may be outdated.

On Ubuntu 24.04, one will need to run the following script to satisfy all dependencies:

.. sourcecode:: bash

    # Feel free to change OpenJDK packages with your preferred JDK.
    apt install build-essential openjdk-11-jdk-headless fp-compiler \
        postgresql postgresql-client python3.12 python3.12-dev python3-pip \
        python3-venv libpq-dev libyaml-dev libffi-dev shared-mime-info \
        cppreference-doc-en-html zip curl

    # Isolate from upstream package repository
    echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/isolate.asc] http://www.ucw.cz/isolate/debian/ noble-isolate main' >/etc/apt/sources.list.d/isolate.list
    curl https://www.ucw.cz/isolate/debian/signing-key.asc >/etc/apt/keyrings/isolate.asc
    apt update && apt install isolate

    # Optional
    apt install nginx-full php-cli texlive-latex-base ghc rustc mono-mcs pypy3

    # Only for compiling Hebrew statements with German task format, install the following. (TODO: Is there a package for this in Ubuntu?)
    # https://github.com/bBoxType/FiraGO

    # Only for compiling statements in Cyrillic languages with German task format
    sudo apt-get install texlive-lang-cyrillic

    # Only for captcha in contest registration interface
    sudo apt-get install libcairo2

The above commands provide a very essential Pascal environment. Consider installing the following packages for additional units: ``fp-units-base``, ``fp-units-fcl``, ``fp-units-misc``, ``fp-units-math`` and ``fp-units-rtl``.

Arch Linux
----------

On Arch Linux, unofficial AUR packages can be found: `cms-germany-git <http://aur.archlinux.org/packages/cms-germany-git`.
If using this method, we also recommend installing ``isolate`` from ``isolate-git <http://aur.archlinux.org/packages/isolate-git>`` (as the other package does not include the systemd services).
Remember to ``systemctl enable --now isolate.service``.

However, if you do not want to use them, the following command will install almost all dependencies (some of them can be found in the AUR):

.. sourcecode:: bash

    pacman -S base-devel jdk8-openjdk fpc postgresql postgresql-client \
        python python-pip postgresql-libs libyaml shared-mime-info

    # Install the following from AUR.
    # https://aur.archlinux.org/packages/cppreference/
    # https://aur.archlinux.org/packages/isolate

    # Optional
    pacman -S --needed nginx php php-fpm phppgadmin texlive-core ghc rust mono pypy3

    # Only for compiling Hebrew statements with German task format, install the following from AUR.
    # https://aur.archlinux.org/packages/ttf-fira-go/

    # Only for compiling statements in Cyrillic languages with German task format
    sudo pacman -S --needed texlive-langcyrillic

    # Only for captcha in contest registration interface
    sudo pacman -S --needed cairo

Preparation steps
=================

Clone :gh_clone_ssh:`CMS using SSH` or :gh_clone_https:`HTTPS`. Alternatively, download :gh_download:`CMS from GitHub as an archive`, then extract it on your filesystem.
You should then access the ``cms`` folder using a terminal.

In order to run CMS there are some preparation steps to run (like installing the sandbox, compiling localization files, creating the ``cmsuser``, and so on). You can either do all these steps by hand or you can run the following command:

.. warning::
   In previous versions, ``prerequisites.py`` also installed ``isolate``.
   This is no longer the case, as ``isolate`` is now packaged for many distributions, and users may choose different versions of ``isolate`` depending on which version of ``cgroups`` they are using.

    Note however that ``cms`` expects to be able to run ``isolate`` without root, which not all packages provide.

.. FIXME -- We should consider making the path to 'isolate' configurable, allowing users to create custom wrappers for e.g. setuid or sudo.

.. sourcecode:: bash

    sudo useradd --user-group --create-home --comment CMS cmsuser

If you are using a packaged version of Isolate, you need to add ``cmsuser``
to the ``isolate`` group:

.. sourcecode:: bash

    sudo usermod -a -G isolate cmsuser


Installing CMS
==============

The installation of CMS should be performed as the ``cmsuser``.

First obtain the source code of CMS. Download :gh_download:`CMS release`
|release| from GitHub as an archive, extract it and start a shell inside.
Alternatively, if you like living at the bleeding edge, check out the CMS
`Git repository <https://github.com/cms-dev/cms>`_ instead.

The preferred method of installation is using :samp:`./install.py --dir={install_dir} cms`,
which does the following:

* Creates an *installation directory* of the given name. It contains a Python
  virtual environment and subdirectories where CMS stores its data, logs, and caches.
  If you omit the ``--dir`` option, CMS is installed to ``~/cms`` (``cms`` in the
  home directory of the current user). Make sure that it is different from the
  source directory.

* Populates the virtual environment with CMS and Python packages on which CMS depends.

* Checks that Isolate is available.

* Installs the sample configuration files to :samp:`{install_dir}/etc/cms.toml`
  and :samp:`{install_dir}/etc/cms_ranking.toml`.

Now you can run CMS commands from the shell directly as :samp:`{install_dir}/bin/{command}`.
It is usually more convenient to activate the virtual environment, which adds
:samp:`{install_dir}/bin` to your ``$PATH``. This can be done by adding the following line
to your ``~/.profile``:

.. sourcecode:: bash

    source $TARGET/bin/activate

(with ``$TARGET`` replaced by the path to your installation directory).


Development installs
--------------------

If you want to develop CMS, you can use :samp:`./install.py --dir={install_dir} cms --devel --editable`.
This includes development dependencies. It also makes the installation linked to the
source directory, so you don't need to reinstall if you edit the source.


Configuring the worker machines
===============================

Worker machines need to be carefully set up in order to ensure that evaluation
results are valid and consistent. Just running the evaluations under Isolate
does not achieve this: for example, if the machine has CPU power management
configured, it might affect execution time in an unpredictable way.
Having an active swap partition may allow programs to evade memory limits.

We suggest following Isolate's `guidelines <https://www.ucw.cz/isolate/isolate.1.html#_reproducibility>`_ for reproducible results
and running the ``isolate-check-environment`` command which checks your system
for common issues.


.. _installation_updatingcms:

Updating CMS
============

As CMS develops, the database schema it uses to represent its data may be updated and new versions may introduce changes that are incompatible with older versions.

To preserve the data stored on the database you need to dump it on the filesystem using ``cmsDumpExporter`` **before you update CMS** (i.e. with the old version).

You can then update CMS and reset the database schema by running:

.. sourcecode:: bash

    cmsDropDB
    cmsInitDB

To load the previous data back into the database you can use ``cmsDumpImporter``: it will adapt the data model automatically on-the-fly (you can use ``cmsDumpUpdater`` to store the updated version back on disk and speed up future imports).

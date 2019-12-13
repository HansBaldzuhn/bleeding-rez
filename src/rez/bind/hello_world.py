"""
Creates the 'hello_world' testing package.

Note: Even though this is a python-based package, it does not list python as a
requirement. This is not typical! This package is intended as a very simple test
case, and for that reason we do not want any dependencies.
"""
from __future__ import absolute_import
from __future__ import print_function
from rez.package_maker__ import make_package
from rez.vendor.version.version import Version
from rez.utils.lint_helper import env
from rez.util import create_executable_script
from rez.bind._utils import make_dirs, check_version
from rez.system import system
import os
import os.path
import inspect


def commands():
    env.PATH.append('{this.root}/bin')
    env.OH_HAI_WORLD = "hello"


def hello_world_source():
    if os.name == "nt":
        code = \
        """
        @echo off

        set quiet=0
        set retcode=0
        
        :loop
        IF NOT "%1"=="" (
            IF "%1"=="-q" (
                set quiet=1
                SHIFT
            )
            IF "%1"=="-r" (
                set retcode=%2
                SHIFT
                SHIFT
            )
            GOTO :loop
        )
        
        IF %quiet%==0 (
            echo Hello Rez World!
        )
        exit %retcode%
        """
        return inspect.cleandoc(code)

    else:
        code =  \
        """
        set -e
        
        retcode=0
        
        while [ "$1" != "" ]; do
            case $1 in
                -q | --quiet )       quiet=1
                                     ;;
                -r | --retcode )     retcode="$2"
                                     shift
                                     ;;
            esac
            shift
        done
        
        if [ -z $quiet ]; then
            echo Hello Rez World!
        fi
        exit $retcode
        """
        return inspect.cleandoc(code)


def bind(path, version_range=None, opts=None, parser=None):
    version = Version("1.0")
    check_version(version, version_range)

    def make_root(variant, root):
        binpath = make_dirs(root, "bin")
        filepath = os.path.join(binpath, "hello_world")
        program = "bash"
        if os.name == "nt":
            program = "cmd"
        create_executable_script(filepath, hello_world_source(), program=program)
        
    with make_package("hello_world", path, make_root=make_root) as pkg:
        pkg.version = version
        pkg.tools = ["hello_world"]
        pkg.commands = commands

    return pkg.installed_variants


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

"""Windows PowerShell 5+"""

from rez.config import config
from rez.rex import RexExecutor, OutputStyle, EscapedString
from rez.shells import Shell
from rez.utils.system import popen
from rez.utils.platform_ import platform_
from rezplugins.shell.cmd import CMD
import os

try:
    basestring
except NameError:
    # Python 3+
    basestring = str


class PowerShell(CMD):
    syspaths = None
    _executable = None
    stdin_arg_name = "in_stdin"

    @property
    def executable(cls):
        if cls._executable is None:
            cls._executable = Shell.find_executable('powershell')
        return cls._executable

    @classmethod
    def name(cls):
        return 'powershell'

    @classmethod
    def file_extension(cls):
        return 'ps1'

    @classmethod
    def startup_capabilities(cls, rcfile=False, norc=False, stdin=False,
                             command=False):
        cls._unsupported_option('norc', norc)
        norc = False
        
        if command not in (None, False):
            cls._overruled_option('stdin', 'command', stdin)
            cls._overruled_option('rcfile', 'command', rcfile)
            stdin = False
            rcfile = False
        if stdin:
            cls._overruled_option('rcfile', 'stdin', rcfile)
            rcfile = False
        
        return (rcfile, norc, stdin, command)

    @classmethod
    def get_startup_sequence(cls, rcfile, norc, stdin, command):
        rcfile, norc, stdin, command = \
            cls.startup_capabilities(rcfile, norc, stdin, command)
            
        files = []
        do_rcfile = False
        
        if rcfile:
            do_rcfile = True
            if rcfile and os.path.exists(os.path.expanduser(rcfile)) and rcfile.endswith(".ps1"):
                files.append(rcfile)

        return dict(
            stdin=stdin,
            command=command,
            do_rcfile=do_rcfile,
            envvar=None,
            files=files,
            bind_files=[],
            source_bind_files=(not norc)
        )
    
    def add_argument_parser(self, arg_dict={}):
        """
        dict is of form:
        arg_dict= { argument1: {"type": type,
                                "default_value": default_value
                                },
                    argument2: {"type": type,
                                "default_value": default_value
                                }
                    }
        """
        self._addline('param (')
        for arg in arg_dict:
            self._addline('\t[{}]${}={}'.format( arg_dict[arg]["type"],
                                                 arg,
                                                 arg_dict[arg]["default_value"])
            )
        self._addline(')')
        
    def invoke(self, expr):
        self._addline('Invoke-Expression {}'.format(expr))

    def _bind_interactive_rez(self):
        if config.set_prompt and self.settings.prompt:
            self._addline('Function prompt {"%s"}' % self.settings.prompt)

    def spawn_shell(self, context_file, tmpdir, rcfile=None, norc=False,
                    stdin=False, command=None, env=None, quiet=False,
                    pre_command=None, **Popen_args):

        startup_sequence = self.get_startup_sequence(rcfile, norc, bool(stdin), command)
        shell_command = None

        def _record_shell(ex, files, bind_rez=True, print_msg=False):
            if startup_sequence["stdin"]:
                # prepare the script for $input argument
                arg_data = {self.stdin_arg_name:{"type":"string", "default_value":'""'}}
                ex.interpreter.add_argument_parser(arg_data)
            ex.source(context_file)
            if startup_sequence["envvar"]:
                ex.unsetenv(startup_sequence["envvar"])
            if bind_rez:
                ex.interpreter._bind_interactive_rez()
            # The "files" item can only be fed by the rcfile argument, it should contain only one element
            for f in startup_sequence["files"]:
                ex.source(f)
            if print_msg and not quiet:
                ex.info('You are now in a rez-configured environment.')

                # Rez may not be available.
                # Or it may not have an associated Python interpreter
                # available, in which case the command will succeed
                # but output to stderr, muted with 2>$null
                ex.command("Try { rez context 2>$null } Catch { }")
            if startup_sequence["stdin"]:
                # Invoke what was passed to stdin
                ex.interpreter.invoke("${}".format(self.stdin_arg_name))

        executor = RexExecutor(interpreter=self.new_shell(),
                               parent_environ={},
                               add_default_namespaces=False)

        if startup_sequence["command"] is not None:
            _record_shell(executor, files=startup_sequence["files"])
            shell_command = startup_sequence["command"]
        elif startup_sequence["stdin"]:
            _record_shell(executor,
                          files=startup_sequence["files"])
        else:
            _record_shell(executor,
                          files=startup_sequence["files"],
                          print_msg=(not quiet))

        if shell_command:
            executor.command(shell_command)

        # Forward exit call to parent PowerShell process
        executor.command("exit $LastExitCode")

        code = executor.get_output()
        target_file = os.path.join(
            tmpdir, "rez-shell.%s" % self.file_extension()
        )

        with open(target_file, 'w') as f:
            f.write(code)

        cmd = []
        if pre_command:
            cmd = pre_command

            if not isinstance(cmd, (tuple, list)):
                cmd = pre_command.rstrip().split()
                
                
        target_file_execute_string = '. "{}"'.format(target_file)        
        if startup_sequence["stdin"]:
            target_file_execute_string += " -in_stdin $input"
        if shell_command or startup_sequence["stdin"]:
            # We force powershell to return the exit code of the target file
            # Without this, the return code is the one from powershell.exe
            # For "stdin" if we don't force to quit, the shell will never end.
            # That also means that stdin will work only once
            target_file_execute_string += ";exit $LASTEXITCODE"

        cmd += [
            self.executable,
            "-NoLogo ",

            # Prevent custom user profile from leaking into
            # the resulting environment.
            "-NoProfile ",

            # Establish a session within which arbitrary
            # PowerShell scripts may be run.
            "-ExecutionPolicy", "Unrestricted",

            # Start from this script
            target_file_execute_string
        ]

        if shell_command is None or startup_sequence["stdin"] is None:
            cmd.insert(1, "-NoExit")
            
        if startup_sequence["stdin"] and stdin and (stdin is not True):
            Popen_args["stdin"] = stdin

        # No environment was explicity passed
        if not env and not config.inherit_parent_environment:
            env = self.environment()

        p = popen(cmd,
                  env=env,
                  universal_newlines=True,
                  **Popen_args)
        return p

    def get_output(self, style=OutputStyle.file):
        if style == OutputStyle.file:
            script = '\n'.join(self._lines) + '\n'
        else:
            lines = []
            for line in self._lines:
                if line.startswith('#'):
                    continue

                line = line.rstrip()
                lines.append(line)

            script = '&& '.join(lines)
        return script

    def escape_string(self, value):
        """Escape the <, >, ^, and & special characters reserved by Windows.

        Args:
            value (str/EscapedString): String or already escaped string.

        Returns:
            str: The value escaped for Windows.

        """
        if isinstance(value, EscapedString):
            return value.formatted(self._escaper)
        return self._escaper(value)

    def setenv(self, key, value):
        value = self.escape_string(value)
        self._addline('$env:{0} = "{1}"'.format(key, value))

    def unsetenv(self, key):
        self._addline(r"Remove-Item Env:\%s" % key)

    def resetenv(self, key, value, friends=None):
        self._addline(self.setenv(key, value))

    def alias(self, key, value):
        value = EscapedString.disallow(value)
        cmd = "function {key}() {{ {value} $args }}"
        self._addline(cmd.format(key=key, value=value))

    def comment(self, value):
        for line in value.split('\n'):
            self._addline('# %s' % line)

    def info(self, value):
        for line in value.split('\n'):
            self._addline('Write-Host %s' % line)

            # Prefer Write-Host to Write-Output
            # See https://github.com/mottosso/bleeding-rez/issues/48

    def error(self, value):
        for line in value.split('\n'):
            self._addline('Write-Error "%s"' % line)

    def source(self, value):
        self._addline(". \"%s\"" % value)

    def command(self, value):
        self._addline(value)

    def get_key_token(self, key):
        return "$env:%s" % key

    def join(self, command):
        return " ".join(command)


def register_plugin():
    if platform_.name == "windows":
        return PowerShell


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

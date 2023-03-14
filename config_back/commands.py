# This is a sample commands.py.  You can add your own commands here.
#
# Please refer to commands_full.py for all the default commands and a complete
# documentation.  Do NOT add them all here, or you may end up with defunct
# commands when upgrading ranger.

# A simple command for demonstration purposes follows.
# -----------------------------------------------------------------------------
from __future__ import (absolute_import, division, print_function)

# You can import any python module as needed.
import os
import sys
from PyQt5 import QtWidgets, QtGui

# You always need to import ranger.api.commands here to get the Command class:
from ranger.api.commands import Command
from ranger.core.loader import CommandLoader
from ranger.container.file import File
from ranger.container.directory import sort_by_basename


# -----------------------------------------------------------------------------
class fzfSelect(Command):
    """:fzf_select
    See: https://github.com/junegunn/fzf
    """
    def execute(self):
        import subprocess
        import os.path
        if self.quantifier:
            # match only directories
            command="find -L . \( -path '*/\.*' -o -fstype 'dev' -o -fstype 'proc' \) -prune \
            -o -type d -print 2> /dev/null | sed 1d | cut -b3- | fzf +m"
        else:
            # match files and directories
            command="find -L . \( -path '*/\.*' -o -fstype 'dev' -o -fstype 'proc' \) -prune \
            -o -print 2> /dev/null | sed 1d | cut -b3- | fzf +m"
        fzf = self.fm.execute_command(command, universal_newlines=True, stdout=subprocess.PIPE)
        stdout, stderr = fzf.communicate()
        if fzf.returncode == 0:
            fzf_file = os.path.abspath(stdout.rstrip('\n'))
            if os.path.isdir(fzf_file):
                self.fm.cd(fzf_file)
            else:
                self.fm.select_file(fzf_file)


class fzfLocate(Command):
    """:fzf_locate
    See: https://github.com/junegunn/fzf
    """
    def execute(self):
        import subprocess
        if self.quantifier:
            command="locate home | fzf -e -i"
        else:
            command="locate home | fzf -e -i"
        fzf = self.fm.execute_command(command, stdout=subprocess.PIPE)
        stdout, stderr = fzf.communicate()
        if fzf.returncode == 0:
            fzf_file = os.path.abspath(stdout.decode('utf-8').rstrip('\n'))
            if os.path.isdir(fzf_file):
                self.fm.cd(fzf_file)
            else:
                self.fm.select_file(fzf_file)


# -----------------------------------------------------------------------------
class edgeFinderSelect(Command):
    class suppress_stdout_stderr(object):
        '''
        A context manager for doing a "deep suppression" of stdout and stderr in 
        Python, i.e. will suppress all print, even if the print originates in a 
        compiled C/Fortran sub-function.
        This will not suppress raised exceptions, since exceptions are printed
        to stderr just before a script exits, and after the context manager has
        exited (at least, I think that is why it lets exceptions through).      

        '''
        def __init__(self):
            # Open a pair of null files
            self.null_fds =  [os.open(os.devnull,os.O_RDWR) for x in range(2)]
            # Save the actual stdout (1) and stderr (2) file descriptors.
            self.save_fds = [os.dup(1), os.dup(2)]

        def __enter__(self):
            # Assign the null pointers to stdout and stderr.
            os.dup2(self.null_fds[0],1)
            os.dup2(self.null_fds[1],2)

        def __exit__(self, *_):
            # Re-assign the real stdout/stderr back to (1) and (2)
            os.dup2(self.save_fds[0],1)
            os.dup2(self.save_fds[1],2)
            # Close all file descriptors
            for fd in self.null_fds + self.save_fds:
                os.close(fd)

    def execute(self):
        # Select Files
        with self.suppress_stdout_stderr():
            app = QtWidgets.QApplication(sys.argv)
            os.system('''/usr/bin/osascript -e 'tell app "Finder" to set frontmost of process "python" to true' ''')
            fileNames, _ = QtWidgets.QFileDialog.getOpenFileNames(None, "QFileDialog.getOpenFileName()", self.fm.thisdir.path, "All Files (*);;Python Files (*.py)", )

            app.exit()
            os.system('''/usr/bin/osascript -e 'tell app "Finder" to set frontmost of process "iTerm2" to true' ''')
        if len(fileNames) == 0:
            return

        # Sort 
        fileNames.sort()
        self.fm.cd(fileNames[0])
        sortFunc_prev = self.fm.thisdir.sort_dict[self.fm.thisdir.settings.sort]
        self.fm.thisdir.sort_dict[self.fm.thisdir.settings.sort] = sort_by_basename
        self.fm.thisdir.sort()
        files = self.fm.thisdir.files

        # Mark selected files
        cnum, flag = 0, 0
        for fileName in fileNames:
            while not flag:
                if fileName == files[cnum].path:
                    self.fm.thisdir.mark_item(files[cnum], val=True)
                    flag = 1
                cnum += 1
            flag = 0

        # Aftermath
        self.fm.ui.need_redraw = True
        self.fm.thisdir.sort_dict[self.fm.thisdir.settings.sort] = sortFunc_prev
        self.fm.thisdir.sort()
        self.fm.select_file(fileNames[0])


class edgeDragonDrop(Command):
    def execute(self):
        cwd = self.fm.thisdir
        target_files = cwd.get_selection()
        files = []
        # Get Original Paths of Selected Files(target_paths)
        for file in target_files:
            files.append('./'+file.path.split('/')[-1])

        command = CommandLoader(args=['open'] + ['-a'] + ['yoink'] + files, descr="")
        self.fm.loader.add(command)


# -----------------------------------------------------------------------------
class bulkrename(Command):
    """:bulkrename

    This command opens a list of selected files in an external editor.
    After you edit and save the file, it will generate a shell script
    which does bulk renaming according to the changes you did in the file.

    This shell script is opened in an editor for you to review.
    After you close it, it will be executed.
    """

    def execute(self):
        # pylint: disable=too-many-locals,too-many-statements,too-many-branches
        import sys
        import tempfile
        from ranger.container.file import File
        from ranger.ext.shell_escape import shell_escape as esc
        py3 = sys.version_info[0] >= 3

        # Create and edit the file list
        filenames = [f.relative_path for f in self.fm.thistab.get_selection()]
        with tempfile.NamedTemporaryFile(delete=False) as listfile:
            listpath = listfile.name
            if py3:
                listfile.write("\n".join(filenames).encode(
                    encoding="utf-8", errors="surrogateescape"))
            else:
                listfile.write("\n".join(filenames))
            self.fm.notify(listpath)
        self.fm.execute_file([File(listpath)], app='editor')
        with (open(listpath, 'r', encoding="utf-8", errors="surrogateescape") if
              py3 else open(listpath, 'r')) as listfile:
            new_filenames = listfile.read().split("\n")
        os.unlink(listpath)
        if all(a == b for a, b in zip(filenames, new_filenames)):
            self.fm.notify("No renaming to be done!")
            return

        # Generate script
        with tempfile.NamedTemporaryFile() as cmdfile:
            script_lines = []
            new_dirs = []
            for old, new in zip(filenames, new_filenames):
                if old != new:
                    basepath, _ = os.path.split(new)
                    if (basepath and basepath not in new_dirs
                            and not os.path.isdir(basepath)):
                        script_lines.append("mkdir -vp -- {dir}".format(
                            dir=esc(basepath)))
                        new_dirs.append(basepath)
                    script_lines.append("mv -vi -- {old} {new}".format(
                        old=esc(old), new=esc(new)))
            # Make sure not to forget the ending newline
            script_content = "\n".join(script_lines) + "\n"
            if py3:
                cmdfile.write(script_content.encode(encoding="utf-8",
                                                    errors="surrogateescape"))
            else:
                cmdfile.write(script_content)
            cmdfile.flush()

            # Open the script and let the user review it, then check if the
            # script was modified by the user
            # self.fm.execute_file([File(cmdfile.name)], app='editor')
            # cmdfile.seek(0)
            # script_was_edited = (script_content != cmdfile.read())
            # script_was_edited = False
            # Do the renaming
            self.fm.notify(cmdfile.name)
            self.fm.run(['/bin/sh', cmdfile.name], flags='w')   # edgeEdit (runner.py, wait_for_enter=false)

        # Retag the files, but only if the script wasn't changed during review,
        # because only then we know which are the source and destination files.
        tags_changed = False
        for old, new in zip(filenames, new_filenames):
            if old != new:
                oldpath = self.fm.thisdir.path + '/' + old
                newpath = self.fm.thisdir.path + '/' + new
                if oldpath in self.fm.tags:
                    old_tag = self.fm.tags.tags[oldpath]
                    self.fm.tags.remove(oldpath)
                    self.fm.tags.tags[newpath] = old_tag
                    tags_changed = True
        if tags_changed:
            self.fm.tags.dump()


class mkdir(Command):
    """:mkdir <dirname>

    Creates a directory with the name <dirname>.
    """

    def execute(self):
        from os.path import join, expanduser, lexists
        from os import makedirs

        dirname = join(self.fm.thisdir.path, expanduser(self.rest(1)))
        if not lexists(dirname):
            makedirs(dirname)
        else:
            self.fm.notify("file/directory exists!", bad=True)

    def tab(self, tabnum):
        return self._tab_directory_content()


class edgeCodehere(Command):
    def execute(self):
        path = self.fm.thisdir.path
        command = CommandLoader(args=['code']+[path], descr="")
        self.fm.loader.add(command)


class edgeCompress(Command):
    def execute(self):
        cwd = self.fm.thisdir
        target_files = cwd.get_selection()
        files = []
        # Get Original Paths of Selected Files(target_paths)
        for file in target_files:
            files.append('./'+file.path.split('/')[-1])

        command = CommandLoader(args=['open'] + ['-a'] + ['Keka'] + files, descr="")
        self.fm.loader.add(command)
            

class edgeTrashRestore(Command):
    def execute(self):
        import linecache

        cwd = self.fm.thisdir
        target_files = cwd.get_selection()

        # Get Original Paths of Selected Files(target_paths)
        for file in target_files:
            file_name = file.path.split('/')[-1]
            info_name = file_name + '.trashinfo'
            info_path = os.path.join(cwd.path, '../info', info_name)

            temp = linecache.getline(info_path, 2).strip()  # "Path=Desktop/users/..."
            file_path_ori = '/'.join(temp.split('/')[1:-1])
            file_name_ori = temp.split('/')[-1]

            command = CommandLoader(args=['mv'] + [cwd.path+'/'+file.path.split('/')[-1]] + ['/'+file_path_ori+'/'+file_name_ori], descr="")
            self.fm.loader.add(command)
            command = CommandLoader(args=['rm'] + [cwd.path+'/../info/'+info_name], descr="")
            self.fm.loader.add(command)
        self.fm.notify(file_path_ori)

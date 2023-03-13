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

# You always need to import ranger.api.commands here to get the Command class:
from ranger.api.commands import Command
from ranger.container.file import File
from ranger.container.directory import sort_by_basename

import sys
from PyQt5 import QtWidgets, QtGui




# Any class that is a subclass of "Command" will be integrated into ranger as a
# command.  Try typing ":my_edit<ENTER>" in ranger!
class my_edit(Command):
    # The so-called doc-string of the class will be visible in the built-in
    # help that is accessible by typing "?c" inside ranger.
    """:my_edit <filename>

    A sample command for demonstration purposes that opens a file in an editor.
    """

    # The execute method is called when you run this command in ranger.
    def execute(self):
        # self.arg(1) is the first (space-separated) argument to the function.
        # This way you can write ":my_edit somefilename<ENTER>".
        if self.arg(1):
            # self.rest(1) contains self.arg(1) and everything that follows
            target_filename = self.rest(1)
        else:
            # self.fm is a ranger.core.filemanager.FileManager object and gives
            # you access to internals of ranger.
            # self.fm.thisfile is a ranger.container.file.File object and is a
            # reference to the currently selected file.
            target_filename = self.fm.thisfile.path

        # This is a generic function to print text in ranger.
        self.fm.notify("Let's edit the file " + target_filename + "!")

        # Using bad=True in fm.notify allows you to print error messages:
        if not os.path.exists(target_filename):
            self.fm.notify("The given file does not exist!", bad=True)
            return

        # This executes a function from ranger.core.acitons, a module with a
        # variety of subroutines that can help you construct commands.
        # Check out the source, or run "pydoc ranger.core.actions" for a list.
        self.fm.edit_file(target_filename)

    # The tab method is called when you press tab, and should return a list of
    # suggestions that the user will tab through.
    # tabnum is 1 for <TAB> and -1 for <S-TAB> by default
    def tab(self, tabnum):
        # This is a generic tab-completion function that iterates through the
        # content of the current directory.
        return self._tab_directory_content()

class fzf_select(Command):
    """
    :fzf_select

    Find a file using fzf.

    With a prefix argument select only directories.

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

class codehere(Command):
    def execute(self):
        path = self.fm.thisdir.path
        command = CommandLoader(args=['code']+[path], descr="")
        self.fm.loader.add(command)



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

class quicklook(Command):
    def execute(self):
        # from AppKit import NSBundle
        # bundle = NSBundle.mainBundle()
        # info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
        # info['NSUIElement'] = '1'

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

        with suppress_stdout_stderr():
        #     default_path = self.fm.thisdir.path
            app = QtWidgets.QApplication(sys.argv)
            os.system('''/usr/bin/osascript -e 'tell app "Finder" to set frontmost of process "python" to true' ''')
            fileNames, _ = QtWidgets.QFileDialog.getOpenFileNames(None,"QFileDialog.getOpenFileName()", "","All Files (*);;Python Files (*.py)", )

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
        fnum, cnum = len(files), 0
        flag = 0
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
            


# class quicklook(Command):
#     """:bulkrename

#     This command opens a list of selected files in an external editor.
#     After you edit and save the file, it will generate a shell script
#     which does bulk renaming according to the changes you did in the file.

#     This shell script is opened in an editor for you to review.
#     After you close it, it will be executed.
#     """

#     def execute(self):
#         filenames = [f.path for f in self.fm.thistab.get_selection()]
#         filenames += ['>/dev/null']
#         filenames += ['2>/dev/null']
#         command = CommandLoader(args=['qlmanage'] + ['-p'] + filenames, descr="showing preview")
#         self.fm.loader.add(command)

#         # # Create and edit the file list
#         # filenames = [f.relative_path for f in self.fm.thistab.get_selection()]
#         # with tempfile.NamedTemporaryFile(delete=False) as listfile:
#         #     listpath = listfile.name
#         #     if py3:
#         #         listfile.write("\n".join(filenames).encode(
#         #             encoding="utf-8", errors="surrogateescape"))
#         #     else:
#         #         listfile.write("\n".join(filenames))
#         # self.fm.execute_file([File(listpath)], app='code')
#         # with (open(listpath, 'r', encoding="utf-8", errors="surrogateescape") if
#         #       py3 else open(listpath, 'r')) as listfile:
#         #     new_filenames = listfile.read().split("\n")
#         # os.unlink(listpath)
#         # if all(a == b for a, b in zip(filenames, new_filenames)):
#         #     self.fm.notify("No renaming to be done!")
#         #     return

#         # # Generate script
#         # with tempfile.NamedTemporaryFile() as cmdfile:
#         #     script_lines = []
#         #     new_dirs = []
#         #     for old, new in zip(filenames, new_filenames):
#         #         if old != new:
#         #             basepath, _ = os.path.split(new)
#         #             if (basepath and basepath not in new_dirs
#         #                     and not os.path.isdir(basepath)):
#         #                 script_lines.append("mkdir -vp -- {dir}".format(
#         #                     dir=esc(basepath)))
#         #                 new_dirs.append(basepath)
#         #             script_lines.append("mv -vi -- {old} {new}".format(
#         #                 old=esc(old), new=esc(new)))
#         #     # Make sure not to forget the ending newline
#         #     script_content = "\n".join(script_lines) + "\n"
#         #     if py3:
#         #         cmdfile.write(script_content.encode(encoding="utf-8",
#         #                                             errors="surrogateescape"))
#         #     else:
#         #         cmdfile.write(script_content)
#         #     cmdfile.flush()

#         #     # Open the script and let the user review it, then check if the
#         #     # script was modified by the user
#         #     # self.fm.execute_file([File(cmdfile.name)], app='editor')
#         #     cmdfile.seek(0)
#         #     script_was_edited = (script_content != cmdfile.read())
#         #     script_was_edited = False
#         #     # Do the renaming
#         #     self.fm.run(['/bin/sh', cmdfile.name], flags='w')

#         # # Retag the files, but only if the script wasn't changed during review,
#         # # because only then we know which are the source and destination files.
#         # tags_changed = False
#         # for old, new in zip(filenames, new_filenames):
#         #     if old != new:
#         #         oldpath = self.fm.thisdir.path + '/' + old
#         #         newpath = self.fm.thisdir.path + '/' + new
#         #         if oldpath in self.fm.tags:
#         #             old_tag = self.fm.tags.tags[oldpath]
#         #             self.fm.tags.remove(oldpath)
#         #             self.fm.tags.tags[newpath] = old_tag
#         #             tags_changed = True
#         # if tags_changed:
#         #     self.fm.tags.dump()

import os
from ranger.core.loader import CommandLoader


class tobedelete(Command):
    def execute(self):
        """ Compress marked files to current directory """
        cwd = self.fm.thisdir
        marked_files = cwd.get_selection()

        if not marked_files:
            return

        def refresh(_):
            cwd = self.fm.get_directory(original_path)
            cwd.load_content()

        original_path = cwd.path
        parts = self.line.split()
        au_flags = parts[1:]

        obj = CommandLoader(args=['mv'] + [os.path.relpath(f.path, cwd.path) for f in marked_files] + ['/Users/edge/Desktop/temp/tobeDeleted'], descr="")
        obj.signal_bind('after', refresh)
        self.fm.loader.add(obj)

class myCompress(Command):
    def execute(self):
        cwd = self.fm.thisdir
        target_files = cwd.get_selection()
        files = []
        # Get Original Paths of Selected Files(target_paths)
        for file in target_files:
            files.append('./'+file.path.split('/')[-1])

        command = CommandLoader(args=['open'] + ['-a'] + ['Keka'] + files, descr="")
        self.fm.loader.add(command)
            

class trash_restore(Command):
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


class DragonDrop(Command):
    def execute(self):
        cwd = self.fm.thisdir
        target_files = cwd.get_selection()
        files = []
        # Get Original Paths of Selected Files(target_paths)
        for file in target_files:
            files.append('./'+file.path.split('/')[-1])

        command = CommandLoader(args=['open'] + ['-a'] + ['yoink'] + files, descr="")
        self.fm.loader.add(command)

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
# This file is part of ranger, the console file manager.
# License: GNU GPL version 3, see the file "AUTHORS" for details.

"""The titlebar is the widget at the top, giving you broad overview.

It displays the current path among other things.
"""

from __future__ import (absolute_import, division, print_function)

import os
from os.path import basename
from os import getuid, readlink
from pwd import getpwuid
from grp import getgrgid
from time import time, strftime, localtime  # edgeEdit

from ranger.gui.bar import Bar
from ranger.ext.human_readable import human_readable

from . import Widget


class TitleBar(Widget):
    old_thisfile = None
    old_keybuffer = None
    old_wid = None
    result = None
    right_sumsize = 0
    throbber = ' '
    need_redraw = False
    msg = None  # edgeEdit
    owners = {} # edgeEdit
    groups = {} # edgeEdit
    hint, old_hint = None, None   # edgeEdit

    def __init__(self, *args, **keywords):
        Widget.__init__(self, *args, **keywords)
        self.fm.signal_bind('tab.change', self.request_redraw, weak=True)

    def request_redraw(self):
        self.need_redraw = True

    def draw(self):
        if self.need_redraw or \
                self.fm.thisfile != self.old_thisfile or\
                str(self.fm.ui.keybuffer) != str(self.old_keybuffer) or\
                self.wid != self.old_wid:
            self.need_redraw = False
            self.old_wid = self.wid
            self.old_thisfile = self.fm.thisfile
            self._calc_bar()
        self._print_result(self.result)
        if self.wid > 2:
            self.color('in_titlebar', 'throbber')
            self.addnstr(self.y, self.wid - self.right_sumsize, self.throbber, 1)

        if self.hint and isinstance(self.hint, str):    # edgeEdit
            if self.old_hint != self.hint:
                self.need_redraw = True
            if self.need_redraw:
                self._draw_hint()
            return

        if self.old_hint and not self.hint: # edgeEdit
            self.old_hint = None
            self.need_redraw = True

        if self.msg:    # edgeEdit {}
            if self.msg.is_alive():
                self._draw_message()
                return
            else:
                self.msg = None
                self.need_redraw = True

    def click(self, event):
        """Handle a MouseEvent"""
        direction = event.mouse_wheel_direction()
        if direction:
            self.fm.tab_move(direction)
            self.need_redraw = True
            return True

        if not event.pressed(1) or not self.result:
            return False

        pos = self.wid - 1
        for tabname in reversed(self.fm.get_tab_list()):
            tabtext = self._get_tab_text(tabname)
            pos -= len(tabtext)
            if event.x > pos:
                self.fm.tab_open(tabname)
                self.need_redraw = True
                return True

        pos = 0
        for i, part in enumerate(self.result):
            pos += len(part)
            if event.x < pos:
                if self.settings.hostname_in_titlebar and i <= 2:
                    self.fm.enter_dir("~")
                else:
                    if 'directory' in part.__dict__:
                        self.fm.enter_dir(part.directory)
                return True
        return False

    def notify(self, text, duration=0, bad=False):  # edgeEdit {}
        self.msg = Message(text, duration, bad)

    def clear_message(self):
        self.msg = None

    def _calc_bar(self):
        bar = Bar('in_titlebar')
        self._get_left_part(bar)
        self._get_right_part(bar)
        try:
            bar.shrink_from_the_left(self.wid)
        except ValueError:
            bar.shrink_by_removing(self.wid)
        self.right_sumsize = bar.right.sumsize()
        self.result = bar.combine()

    def _get_left_part(self, bar):  # edgeNote username
        # TODO: Properly escape non-printable chars without breaking unicode
        if self.settings.hostname_in_titlebar:
            if self.fm.username == 'root':
                clr = 'bad'
            else:
                clr = 'good'

            bar.add(self.fm.username, 'directory', clr, fixed=True)  # edgeEdit
            # bar.add('@', 'hostname', clr, fixed=True)
            # bar.add(self.fm.hostname, 'hostname', clr, fixed=True)
            bar.add(':', 'directory', clr, fixed=True)

        pathway = self.fm.thistab.pathway
        if self.settings.tilde_in_titlebar \
           and (self.fm.thisdir.path.startswith(self.fm.home_path + "/")
                or self.fm.thisdir.path == self.fm.home_path):
            pathway = pathway[self.fm.home_path.count('/') + 1:]
            bar.add('~/', 'directory', fixed=True)

        for path in pathway:
            if path.is_link:
                clr = 'link'
            else:
                clr = 'directory'

            bidi_basename = self.bidi_transpose(path.basename)
            bar.add(bidi_basename, clr, directory=path)
            bar.add('/', clr, fixed=True, directory=path)

        if self.fm.thisfile is not None and \
                self.settings.show_selection_in_titlebar:
            bidi_file_path = self.bidi_transpose(self.fm.thisfile.relative_path)
            bar.add(bidi_file_path, 'file')

    def _get_right_part(self, bar):
        # TODO: fix that pressed keys are cut off when chaining CTRL keys
        kbuf = str(self.fm.ui.keybuffer)
        self.old_keybuffer = kbuf
        right = bar.right
        right.add(' ', 'space', fixed=True)
        right.add(kbuf, 'keybuffer', fixed=True)
        right.add(' ', 'space', fixed=True)
        if len(self.fm.tabs) > 1:
            for tabname in self.fm.get_tab_list():
                tabtext = self._get_tab_text(tabname)
                clr = 'good' if tabname == self.fm.current_tab else 'bad'
                right.add(tabtext, 'tab', clr, fixed=True)


        # edgeEdit {allafter}
        if self.column is None: # edgeEdit {allafter}
            return

        if self.column is not None and self.column.target is not None\
                and self.column.target.is_directory:
            target = self.column.target.pointed_obj
        else:
            directory = self.fm.thistab.at_level(0)
            if directory:
                target = directory.pointed_obj
            else:
                return
        try:
            stat = target.stat
        except AttributeError:
            return
        if stat is None:
            return

        if self.fm.mode != 'normal':
            perms = '--%s--' % self.fm.mode.upper()
        else:
            perms = target.get_permission_string()
        how = 'good' if getuid() == stat.st_uid else 'bad'
        right.add(perms, 'info', how)    # edgeEdit
        # right.add_space()
        # right.add(str(stat.st_nlink), 'nlink')
        # right.add_space()
        # right.add(self._get_owner(target), 'owner')
        # right.add_space()
        # right.add(self._get_group(target), 'group')

        if target.is_link:
            how = 'good' if target.exists else 'bad'
            try:
                dest = readlink(target.path)
            except OSError:
                dest = '?'
            right.add(' -> ' + dest, 'link', how)
        # else:
        #     right.add_space()

        #     if self.settings.display_size_in_status_bar and target.infostring:
        #         right.add(target.infostring.replace(" ", ""))
        #         right.add_space()

        #     try:
        #         date = strftime(self.timeformat, localtime(stat.st_mtime))
        #     except OSError:
        #         date = '?'
        #     right.add(date, 'mtime')

        # directory = target if target.is_directory else \
        #     target.fm.get_directory(os.path.dirname(target.path))
        # if directory.vcs and directory.vcs.track:
        #     if directory.vcs.rootvcs.branch:
        #         vcsinfo = '({0:s}: {1:s})'.format(
        #             directory.vcs.rootvcs.repotype, directory.vcs.rootvcs.branch)
        #     else:
        #         vcsinfo = '({0:s})'.format(directory.vcs.rootvcs.repotype)
        #     right.add_space()
        #     right.add(vcsinfo, 'vcsinfo')

        #     right.add_space()
        #     if directory.vcs.rootvcs.obj.vcsremotestatus:
        #         vcsstr, vcscol = self.vcsremotestatus_symb[
        #             directory.vcs.rootvcs.obj.vcsremotestatus]
        #         right.add(vcsstr.strip(), 'vcsremote', *vcscol)
        #     if target.vcsstatus:
        #         vcsstr, vcscol = self.vcsstatus_symb[target.vcsstatus]
        #         right.add(vcsstr.strip(), 'vcsfile', *vcscol)
        #     if directory.vcs.rootvcs.head:
        #         right.add_space()
        #         right.add(directory.vcs.rootvcs.head['date'].strftime(self.timeformat), 'vcsdate')
        #         right.add_space()
        #         summary_length = self.settings.vcs_msg_length or 50
        #         right.add(
        #             directory.vcs.rootvcs.head['summary'][:summary_length],
        #             'vcscommit'
        #         )


        target = self.column.target
        if target is None \
                or not target.accessible \
                or (target.is_directory and target.files is None):
            return

        pos = target.scroll_begin
        max_pos = len(target) - self.column.hei
        base = 'info'

        right.add(" ", "space")

        if self.fm.thisdir.flat:
            right.add("flat=", base, 'flat')
            right.add(str(self.fm.thisdir.flat), base, 'flat')
            right.add(", ", "space")

        if self.fm.thisdir.narrow_filter:
            right.add("narrowed")
            right.add(", ", "space")

        if self.fm.thisdir.filter:
            right.add("f=`", base, 'filter')
            right.add(self.fm.thisdir.filter.pattern, base, 'filter')
            right.add("', ", "space")

        if target.marked_items:
            if len(target.marked_items) == target.size:
                right.add(human_readable(target.disk_usage, separator=''), 'info')
            else:
                sumsize = sum(f.size for f in target.marked_items
                              if not f.is_directory or f.cumulative_size_calculated)
                right.add(human_readable(sumsize, separator=''), 'info')
            right.add("/" + str(len(target.marked_items)), 'info')
        else:
            right.add(human_readable(target.disk_usage, separator=''), 'info')
            # if self.settings.display_free_space_in_status_bar:  # edgeEdit
            #     try:
            #         free = get_free_space(target.path)
            #     except OSError:
            #         pass
            #     else:
            #         right.add(", ", "space")
            #         right.add(human_readable(free, separator='') + " free")
        right.add("  ", "space")

        if target.marked_items:
            # Indicate that there are marked files. Useful if you scroll
            # away and don't see them anymore.
            right.add('Mrk', base, 'marked')
        elif target.files:
            right.add(str(target.pointer + 1) + '/' + str(len(target.files)) + '  ', base)
            if max_pos <= 0:
                right.add('All', base, 'all')
            elif pos == 0:
                right.add('Top', base, 'top')
            elif pos >= max_pos:
                right.add('Bot', base, 'bot')
            else:
                right.add('{0:0.0%}'.format((pos / max_pos)),
                          base, 'percentage')
        else:
            right.add('0/0  All', base, 'all')

        if self.settings.freeze_files:
            # Indicate that files are frozen and will not be loaded
            right.add("  ", "space")
            right.add('FROZEN', base, 'frozen')

    def _get_tab_text(self, tabname):
        result = ' ' + str(tabname)
        if self.settings.dirname_in_tabs:
            dirname = basename(self.fm.tabs[tabname].path)
            if not dirname:
                result += ":/"
            elif len(dirname) > 15:
                result += ":" + dirname[:14] + self.ellipsis[self.settings.unicode_ellipsis]
            else:
                result += ":" + dirname
        return result

    def _print_result(self, result):
        self.win.move(0, 0)
        for part in result:
            self.color(*part.lst)
            y, x = self.win.getyx()
            self.addstr(y, x, str(part))
        self.color_reset()

        if self.settings.draw_progress_bar_in_status_bar:   # edgeEdit {}
            queue = self.fm.loader.queue
            states = []
            for item in queue:
                if item.progressbar_supported:
                    states.append(item.percent)
            if states:
                state = sum(states) / len(states)
                barwidth = (state / 100) * self.wid
                self.color_at(0, 0, int(barwidth), ("in_statusbar", "loaded"))
                self.color_reset()

    # edgeEdit {allafter}
    def _draw_message(self):
        self.win.erase()
        self.color('in_statusbar', 'message',
                   self.msg.bad and 'bad' or 'good')
        self.addnstr(0, 0, self.msg.text, self.wid)

    def _draw_hint(self):
        self.win.erase()
        highlight = True
        space_left = self.wid
        starting_point = self.x
        for string in self.hint.split('*'):
            highlight = not highlight
            if highlight:
                self.color('in_statusbar', 'text', 'highlight')
            else:
                self.color('in_statusbar', 'text')

            try:
                self.addnstr(0, starting_point, string, space_left)
            except curses.error:
                break
            space_left -= len(string)
            starting_point += len(string)

    def _get_owner(self, target):
        uid = target.stat.st_uid

        try:
            return self.owners[uid]
        except KeyError:
            try:
                self.owners[uid] = getpwuid(uid)[0]
                return self.owners[uid]
            except KeyError:
                return str(uid)

    def _get_group(self, target):
        gid = target.stat.st_gid

        try:
            return self.groups[gid]
        except KeyError:
            try:
                self.groups[gid] = getgrgid(gid)[0]
                return self.groups[gid]
            except KeyError:
                return str(gid)

class Message(object):  # pylint: disable=too-few-public-methods    # edgeEdit
    elapse = None
    text = None
    bad = False

    def __init__(self, text, duration, bad):
        self.text = text
        self.bad = bad
        self.elapse = time() + duration

    def is_alive(self):
        return time() <= self.elapse
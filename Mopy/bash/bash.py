# -*- coding: utf-8 -*-
#
# GPL License and Copyright Notice ============================================
#  This file is part of Wrye Bash.
#
#  Wrye Bash is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  Wrye Bash is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Wrye Bash; if not, write to the Free Software Foundation,
#  Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
#  Wrye Bash copyright (C) 2005-2009 Wrye, 2010-2015 Wrye Bash Team
#  https://github.com/wrye-bash
#
# =============================================================================

"""This module starts the Wrye Bash application in console mode. Basically,
it runs some initialization functions and then starts the main application
loop."""

# Imports ---------------------------------------------------------------------
import atexit
import codecs
import os
from time import time, sleep
import sys
import platform
import traceback

import bass
import exception
# NO LOCAL IMPORTS HERE !
basher = balt = barb = bolt = None
_wx = None
is_standalone = hasattr(sys, 'frozen')


def _import_wx():
    """Import wxpython or show a tkinter error and exit if unsuccessful."""
    global _wx
    try:
        # noinspection PyUnresolvedReferences
        import wx as _wx
    except ImportError:
        but_kwargs = {'text': _(u"QUIT"),
                      'fg': 'red'}  # foreground button color
        msg = u'\n'.join(
            [_(u'Unable to locate wxpython installation. Exiting.'), u'',
             dump_environment()])
        _tkinter_error_dial(msg, but_kwargs)
        sys.exit(1)


def _import_bolt(opts):
    """Import bolt or show a tkinter error and exit if unsuccessful.

    :param opts: command line arguments
    :type opts: Namespace"""
    global bolt
    try:
        # First of all set the language, set on importing bolt
        bass.language = opts.language
        import bolt  # bass.language must be set
    except Exception:
        but_kwargs = {'text': u"QUIT", 'fg': 'red'}  # foreground button color
        msg = u'\n'.join(
            [u'Unable to load bolt. Exiting.', u'', dump_environment()])
        _tkinter_error_dial(msg, but_kwargs)
        sys.exit(1)


#------------------------------------------------------------------------------
def SetHomePath(homePath):
    drive,path = os.path.splitdrive(homePath)
    os.environ['HOMEDRIVE'] = drive
    os.environ['HOMEPATH'] = path

#------------------------------------------------------------------------------
def SetUserPath(iniPath=None, uArg=None):
#if uArg is None, then get the UserPath from the ini file
    if uArg:
        SetHomePath(uArg)
    else:
        bashIni = bass.GetBashIni(iniPath=iniPath, reload_=iniPath is not None)
        if bashIni and bashIni.has_option(u'General', u'sUserPath')\
                   and not bashIni.get(u'General', u'sUserPath') == u'.':
            SetHomePath(bashIni.get(u'General', u'sUserPath'))

# Backup/Restore --------------------------------------------------------------
def _new_bash_version_prompt_backup():
    # return False if old version == 0 (as in not previously installed)
    if bass.settings['bash.version'] == 0: return False
    # return True if not same app version and user opts to backup settings
    return not barb.SameAppVersion() and balt.askYes(balt.Link.Frame, _(
        u'A different version of Wrye Bash was previously installed.') + u'\n'+
        _(u'Previous Version: ') + (u'%s\n' % bass.settings['bash.version']) +
        _(u'Current Version: ') + (u'%s\n' % bass.AppVersion) + _(
        u'Do you want to create a backup of your Bash settings before they '
        u'are overwritten?'))

def cmdBackup(opts):
    # backup settings if app version has changed or on user request
    global basher, balt, barb
    if not basher: import basher, balt, barb
    path = (opts.backup and opts.filename) or None
    should_quit = opts.backup and opts.quietquit
    if _new_bash_version_prompt_backup() or opts.backup:
        frame = balt.Link.Frame
        backup = barb.BackupSettings(frame, path, should_quit,
                                     opts.backup_images)
        try:
            backup.Apply()
        except exception.StateError:
            if barb.SameAppVersion():
                backup.WarnFailed()
            elif balt.askYes(frame, u'\n'.join([
            _(u'There was an error while trying to backup the Bash settings!'),
            _(u'If you continue, your current settings may be overwritten.'),
            _(u'Do you want to quit Wrye Bash now?')]),
                             title=_(u'Unable to create backup!')):
                return False # Quit
        except exception.BackupCancelled:
            if not barb.SameAppVersion() and balt.askYes(frame, u'\n'.join([
            _(u'You did not create a backup of the Bash settings.'),
            _(u'If you continue, your current settings may be overwritten.'),
            _(u'Do you want to quit Wrye Bash now?')]),
                            title=_(u'No backup created!')):
                return False # Quit
    return should_quit

def cmdRestore(opts):
    # restore settings on user request
    global basher, balt, barb
    if not basher: import basher, balt, barb
    path = (opts.restore and opts.filename) or None
    should_quit = opts.restore and opts.quietquit
    if opts.restore:
        try:
            backup = barb.RestoreSettings(balt.Link.Frame, path, should_quit,
                                          opts.backup_images)
            backup.Apply()
        except exception.BackupCancelled:
            pass
    return should_quit


def assure_single_instance(instance):
    """ Ascertain that only one instance of Wrye Bash is running.

    If this is the second instance running, then display an error message and
    exit.

    :type instance: wx.SingleInstanceChecker"""
    if instance.IsAnotherRunning():
        bolt.deprint(u'Only one instance of Wrye Bash can run. Exiting.')
        msg = _(u'Only one instance of Wrye Bash can run.')
        _app = _wx.App(False)
        with _wx.MessageDialog(None, msg, _(u'Wrye Bash'), _wx.OK) as dialog:
            dialog.ShowModal()
        sys.exit(1)


def exit_cleanup():
    # Cleanup temp installers directory
    import tempfile, bolt
    tmpDir = bolt.GPath(tempfile.tempdir)
    for file_ in tmpDir.list():
        if file_.cs.startswith(u'wryebash_'):
            file_ = tmpDir.join(file_)
            try:
                if file_.isdir():
                    file_.rmtree(safety=file_.stail)
                else:
                    file_.remove()
            except:
                pass

    if basher:
        from basher import appRestart
        from basher import uacRestart
        if appRestart:
            if not is_standalone:
                exePath = bolt.GPath(sys.executable)
                sys.argv = [exePath.stail] + sys.argv
            if u'--restarting' not in sys.argv:
                sys.argv += [u'--restarting']
            #--Assume if we're restarting that they don't want to be
            #  prompted again about UAC
            if u'--no-uac' not in sys.argv:
                sys.argv += [u'--no-uac']
            def updateArgv(args):
                if isinstance(args,(list,tuple)):
                    if len(args) > 0 and isinstance(args[0],(list,tuple)):
                        for arg in args:
                            updateArgv(arg)
                    else:
                        found = 0
                        for i in xrange(len(sys.argv)):
                            if not found and sys.argv[i] == args[0]:
                                found = 1
                            elif found:
                                if found < len(args):
                                    sys.argv[i] = args[found]
                                    found += 1
                                else:
                                    break
                        else:
                            sys.argv.extend(args)
            updateArgv(appRestart)
            try:
                if uacRestart:
                    if not is_standalone:
                        sys.argv = sys.argv[1:]
                    # noinspection PyUnresolvedReferences
                    import win32api
                    if is_standalone:
                        win32api.ShellExecute(0,'runas',sys.argv[0],u' '.join(
                            '"%s"' % x for x in sys.argv[1:]),None,True)
                    else:
                        args = u' '.join(
                            [u'%s',u'"%s"'][u' ' in x] % x for x in sys.argv)
                        # noinspection PyUnboundLocalVariable
                        win32api.ShellExecute(0,'runas',exePath.s,args,None,
                                              True)
                    return
                else:
                    import subprocess
                    if is_standalone:
                        subprocess.Popen(sys.argv,close_fds=bolt.close_fds)
                    else:
                        # noinspection PyUnboundLocalVariable
                        subprocess.Popen(sys.argv,executable=exePath.s,
                                         close_fds=bolt.close_fds)
                                         #close_fds is needed for the one
                                         # instance checker
            except Exception as error:
                print error
                print u'Error Attempting to Restart Wrye Bash!'
                print u'cmd line: %s %s' %(exePath.s, sys.argv)
                print
                raise

def dump_environment():
    import locale
    fse = sys.getfilesystemencoding()
    msg = u'\n'.join([
        u'Wrye Bash starting',
        u'Using Wrye Bash Version %s%s' % (
            bass.AppVersion,
            (u' ' + _(u'(Standalone)')) if is_standalone else u''
        ),
        u'OS info: %s' % platform.platform(),
        u'Python version: %d.%d.%d' % (
            sys.version_info[0],sys.version_info[1],sys.version_info[2]
        ),
        u'wxPython version: %s' % _wx.version() if 'wx' in sys.modules else \
        u'wxPython not found',
        # Standalone: stdout will actually be pointing to stderr, which has no
        # 'encoding' attribute
        u'input encoding: %s; output encoding: %s; locale: %s' % (
            sys.stdin.encoding,getattr(sys.stdout,'encoding',None),
            locale.getdefaultlocale()
        ),
        u'filesystem encoding: %s' % fse, (
            (u' - using %s' % bolt.Path.sys_fs_enc) if 'bolt' in sys.modules
                                                       and fse else u''
        )
    ])
    print msg
    return msg


# Main ------------------------------------------------------------------------
def main(opts):
    """Run the Wrye Bash main loop.

    :param opts: command line arguments
    :type opts: Namespace"""
    # First import bolt, needed for localization of error messages
    _import_bolt(opts)
    # Then import wx so we can style our error messages nicely
    _import_wx()
    try:
        _main(opts)
    except Exception as e:
        msg = u'\n'.join([
            _(u'Wrye Bash encountered an error.'),
            _(u'Please post the information below to the official thread at:'),
            _(u'https://afkmods.iguanadons.net/index.php?/topic/4966-wrye-bash-all-games/& or '),
            _(u'https://bethesda.net/community/topic/38798/relz-wrye-bash-oblivion-skyrim-skyrim-se-fallout-4/'),
            u'',
            traceback.format_exc(e)
        ])
        _showErrorInAnyGui(msg)
        sys.exit(1)


def _main(opts):
    """Run the Wrye Bash main loop.

    This function is marked private because it should be inside a try-except
    block. Call main() from the outside.

    :param opts: command line arguments
    :type opts: Namespace
    """
    import env # env imports bolt (this needs fixing)
    bolt.deprintOn = opts.debug
    # useful for understanding context of bug reports
    if opts.debug or is_standalone:
        # Standalone stdout is NUL no matter what.   Redirect it to stderr.
        # Also, setup stdout/stderr to the debug log if debug mode /
        # standalone before wxPython is up
        # errLog = io.open(os.path.join(os.getcwdu(),u'BashBugDump.log'),'w',encoding='utf-8')
        errLog = codecs.getwriter('utf-8')(
            open(os.path.join(os.getcwdu(), u'BashBugDump.log'), 'w'))
        sys.stdout = errLog
        sys.stderr = errLog
        old_stderr = errLog

    if opts.debug:
        dump_environment()

    # ensure we are in the correct directory so relative paths will work
    # properly
    if is_standalone:
        pathToProg = os.path.dirname(
            unicode(sys.executable, bolt.Path.sys_fs_enc))
    else:
        pathToProg = os.path.dirname(
            unicode(sys.argv[0], bolt.Path.sys_fs_enc))
    if pathToProg:
        os.chdir(pathToProg)
    del pathToProg

    # Check if there are other instances of Wrye Bash running
    instance = _wx.SingleInstanceChecker('Wrye Bash')
    assure_single_instance(instance)

    # Detect the game we're running for ---------------------------------------
    import bush
    bolt.deprint (u'Searching for game to manage:')
    # set the Bash ini global in bass
    bashIni = bass.GetBashIni()
    ret = bush.detect_and_set_game(opts.oblivionPath, bashIni)
    if ret is not None: # None == success
        if len(ret) == 0:
            msgtext = _(
                u"Wrye Bash could not find a game to manage. Please use "
                u"-o command line argument to specify the game path")
        else:
            msgtext = _(
                u"Wrye Bash could not determine which game to manage.  "
                u"The following games have been detected, please select "
                u"one to manage.")
            msgtext += u'\n\n'
            msgtext += _(
                u'To prevent this message in the future, use the -o command '
                u'line argument or the bash.ini to specify the game path')
        retCode = _wxSelectGame(ret, msgtext)
        if retCode is None:
            bolt.deprint(u"No games were found or Selected. Aborting.")
            return
        # Add the game to the command line, so we use it if we restart
        sys.argv += ['-o', bush.game_path(retCode).s]
        bush.detect_and_set_game(opts.oblivionPath, bashIni, retCode)

    # from now on bush.game is set

    #--Initialize Directories and some settings
    #  required before the rest has imported
    SetUserPath(uArg=opts.userPath)

    # Force Python mode if CBash can't work with this game
    bolt.CBash = opts.mode if bush.game.esp.canCBash else 1 #1 = python mode...
    try:
        import bosh # this imports balt (DUH) which imports wx
        env.isUAC = env.testUAC(bush.gamePath.join(u'Data'))
        bosh.initBosh(opts.personalPath, opts.localAppDataPath, bashIni)

        # if HTML file generation was requested, just do it and quit
        if opts.genHtml is not None:
            msg1 = _(u"generating HTML file from: '%s'") % opts.genHtml
            msg2 = _(u'done')
            try: print msg1
            except UnicodeError: print msg1.encode(bolt.Path.sys_fs_enc)
            import belt # this imports bosh which imports wx (DUH)
            bolt.WryeText.genHtml(opts.genHtml)
            try: print msg2
            except UnicodeError: print msg2.encode(bolt.Path.sys_fs_enc)
            return
        global basher, balt, barb
        import basher
        import barb
        import balt
    except (exception.PermissionError,
            exception.BoltError, ImportError) as e:
        _showErrorInGui(e)
        return

    atexit.register(exit_cleanup)
    basher.InitSettings()
    basher.InitLinks()
    basher.InitImages()
    #--Start application
    if opts.debug:
        if is_standalone:
            # Special case for py2exe version
            app = basher.BashApp()
            # Regain control of stdout/stderr from wxPython
            # noinspection PyUnboundLocalVariable
            sys.stdout = old_stderr
            sys.stderr = old_stderr
        else:
            app = basher.BashApp(False)
    else:
        app = basher.BashApp()

    if not is_standalone and (
        not _rightWxVersion() or not _rightPythonVersion()): return

    # process backup/restore options
    # quit if either is true, but only after calling both
    should_quit = cmdBackup(opts)
    should_quit = cmdRestore(opts) or should_quit
    if should_quit: return

    if env.isUAC:
        uacRestart = False
        if not opts.noUac and not opts.uac:
            # Show a prompt asking if we should restart in Admin Mode
            message = _(
                u"Wrye Bash needs Administrator Privileges to make changes "
                u"to the %(gameName)s directory.  If you do not start Wrye "
                u"Bash with elevated privileges, you will be prompted at "
                u"each operation that requires elevated privileges.") % {
                          'gameName': bush.game.displayName}
            uacRestart = balt.ask_uac_restart(message,
                                              title=_(u'UAC Protection'),
                                              mopy=bass.dirs['mopy'])
        elif opts.uac:
            uacRestart = True
        if uacRestart:
            basher.appRestart = True
            basher.uacRestart = True
            return

    app.Init() # Link.Frame is set here !
    app.MainLoop()



# Show error in gui -----------------------------------------------------------
def _showErrorInGui(e, msg=None):
    """Try really hard to be able to show the error in the GUI."""
    if e:
        with bolt.sio() as o:
            traceback.print_exc(file=o)
            msg = o.getvalue()
    else:
        msg = msg
    if bolt.deprintOn: print msg
    title = _(u'Error! Unable to start Wrye Bash.')
    msg = _(
        u'Please ensure Wrye Bash is correctly installed.') + u'\n\n\n%s' % msg
    try: # try really hard to be able to show the error in any GUI
        _showErrorInAnyGui(title + u'\n\n' + msg)
    except StandardError:
        print 'An error has occurred with Wrye Bash, and could not be ' \
              'displayed.'
        print 'The following is the error that occurred while trying to ' \
              'display the first error:'
        try:
            traceback.print_exc()
        except:
            print '  An error occurred while trying to display the' \
                  ' second error.'
        print 'The following is the error that could not be displayed:'

def _showErrorInAnyGui(msg):
    class ErrorMessage(_wx.Frame):
        def __init__(self):
            _wx.Frame.__init__(self, None, title=_(u'Wrye Bash Error'))
            self.panel = panel = _wx.Panel(self)
            sizer = _wx.BoxSizer(_wx.VERTICAL)
            sizer.Add(_wx.TextCtrl(panel, value=msg,
                                   style=_wx.TE_MULTILINE | _wx.TE_READONLY
                                         | _wx.TE_BESTWRAP),
                      1, _wx.GROW | _wx.ALL, 5)
            button = _wx.Button(panel, _wx.ID_CANCEL, _(u'Quit'))
            button.SetDefault()
            sizer.Add(button, 0, _wx.GROW | _wx.ALL ^ _wx.TOP, 5)
            self.Bind(_wx.EVT_BUTTON, lambda __event: self.Close(True))
            panel.SetSizer(sizer)
    _app = _wx.App(False)
    frame = ErrorMessage()
    frame.Show()
    frame.Center()
    _app.MainLoop()
    del _app

def _tkinter_error_dial(msg, but_kwargs):
    import Tkinter
    root_widget = Tkinter.Tk()
    frame = Tkinter.Frame(root_widget)
    frame.pack()
    button = Tkinter.Button(frame, command=root_widget.destroy, pady=15,
                            borderwidth=5, relief=Tkinter.GROOVE, **but_kwargs)
    button.pack(fill=Tkinter.BOTH, expand=1, side=Tkinter.BOTTOM)
    w = Tkinter.Text(frame)
    w.insert(Tkinter.END, msg)
    w.config(state=Tkinter.DISABLED)
    w.pack()
    root_widget.mainloop()

class _AppReturnCode(object):
    def __init__(self, default=None): self.value = default
    def get(self): return self.value
    def set(self, value): self.value = value

def _wxSelectGame(ret, msgtext):

    class GameSelect(_wx.Frame):
        def __init__(self, gameNames, callback):
            _wx.Frame.__init__(self, None, title=u'Wrye Bash')
            self.callback = callback
            self.panel = panel = _wx.Panel(self)
            sizer = _wx.BoxSizer(_wx.VERTICAL)
            sizer.Add(_wx.TextCtrl(panel, value=msgtext,
                                   style=_wx.TE_MULTILINE | _wx.TE_READONLY |
                                         _wx.TE_BESTWRAP),
                      1, _wx.GROW | _wx.ALL, 5)
            for gameName in gameNames:
                gameName = gameName.title()
                sizer.Add(_wx.Button(panel, label=gameName), 0,
                          _wx.GROW | _wx.ALL ^ _wx.TOP, 5)
            button = _wx.Button(panel, _wx.ID_CANCEL, _(u'Quit'))
            button.SetDefault()
            sizer.Add(button, 0, _wx.GROW | _wx.ALL ^ _wx.TOP, 5)
            self.Bind(_wx.EVT_BUTTON, self.OnButton)
            panel.SetSizer(sizer)

        def OnButton(self, event):
            if event.GetId() != _wx.ID_CANCEL:
                self.callback(self.FindWindowById(event.GetId()).GetLabel())
            self.Close(True)

    _app = _wx.App(False)
    retCode = _AppReturnCode()
    frame = GameSelect(ret, retCode.set)
    frame.Show()
    frame.Center()
    _app.MainLoop()
    del _app
    return retCode.get()

# Version checks --------------------------------------------------------------
def _rightWxVersion():
    wxver = _wx.version()
    wxver_tuple = _wx.VERSION
    if wxver != '2.8.12.1 (msw-unicode)' and wxver_tuple < (2,9):
        return balt.askYes(
            None, 'Warning: you appear to be using a non-supported version '
            'of wxPython (%s).  This will cause problems!  It is highly '
            'recommended you use either version 2.8.12.1 (msw-unicode) or, '
            'at your discretion, a later version (untested). Do you still '
            'want to run Wrye Bash?' % wxver,
            'Warning: Non-Supported wxPython detected', )
    return True

def _rightPythonVersion():
    sysVersion = sys.version_info[:3]
    if sysVersion < (2, 7) or sysVersion >= (3,):
        balt.showError(None, _(u"Only Python 2.7 and newer is supported "
            u"(%s.%s.%s detected). If you know what you're doing install the "
            u"WB python version and edit this warning out. "
            u"Wrye Bash will exit.") % sysVersion,
            title=_(u"Incompatible Python version detected"))
        return False
    return True

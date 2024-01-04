
import os
import sublime_plugin
import sublime

from . import libgerrit


class CrOpenChangedFiles(sublime_plugin.WindowCommand):
  def run(self, **kwargs):
    settings = sublime.load_settings("Chromium.sublime-settings")
    checkout = settings['chromium_checkout']
    current_branch = libgerrit.Gerrit.Current(checkout)
    for file in current_branch.FileChangeList():
      self.window.open_file(fname=os.path.join(checkout, file))


class CrShowBranchStatus(sublime_plugin.WindowCommand):
  def run(self, **kwargs):
    pass


class CrUploadPatchWithComments(sublime_plugin.WindowCommand):
  def run(self, **kwargs):
    pass

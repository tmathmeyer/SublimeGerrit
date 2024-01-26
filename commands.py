
import os
import sublime_plugin
import sublime

from . import libgit
from . import libtree
from . import libmodify
from . import libcodereview


class NestableCommand(sublime_plugin.WindowCommand):
  def run(self, **kwargs):
    try:
      if self._run(**kwargs):
        for task, args in kwargs.get('then', []):
          print(f'running subtask {task}')
          self.window.run_command(task, args)
      else:
        print('command failed. not running subtasks!')
    except Exception as e:
      print(f'exception occurred running task: {e}')
      raise e


class CrOpenChangedFiles(NestableCommand):
  def _run(self, **kwargs) -> bool:
    settings = sublime.load_settings("Chromium.sublime-settings")
    checkout = settings['chromium_checkout']
    current_branch = libgit.Gerrit.Current(checkout)
    for file in current_branch.FileChangeList():
      self.window.open_file(fname=os.path.join(checkout, file))
    return True


class CrShowBranchStatus(NestableCommand):
  def _run(self, **kwargs):
    settings = sublime.load_settings("Chromium.sublime-settings")
    checkout = settings['chromium_checkout']
    html_content = libtree.RenderAllPatches(checkout)
    self.window.new_html_sheet('branch_state', html_content)
    return True


class CrCheckoutAndRebaseBranch(NestableCommand):
  def _run(self, branch, then, **kwargs):
    settings = sublime.load_settings("Chromium.sublime-settings")
    checkout = settings['chromium_checkout']
    return libmodify.CheckoutAndRebaseBranch(checkout, branch)


class CrCheckoutBranch(NestableCommand):
  def _run(self, branch, then, **kwargs):
    settings = sublime.load_settings("Chromium.sublime-settings")
    checkout = settings['chromium_checkout']
    return libmodify.CheckoutBranch(checkout, branch)


class CrCloseActiveBranchStatus(NestableCommand):
  def _run(self, **kwargs):
    self.window.active_sheet().close(on_close=lambda x:x)
    return True


class CrUploadPatchWithComments(NestableCommand):
  def _run(self, **kwargs):
    return True


class CrNopTrampoline(NestableCommand):
  def _run(self, **kwargs):
    return True


class ChangelistFileOpenListener(sublime_plugin.EventListener):
  def on_load_async(self, view:sublime.View):
    contexts = libcodereview.CreateCommentChainContextsForView(view)
    libcodereview.RenderContexts(view, contexts)

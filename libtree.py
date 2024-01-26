
import json
import typing
import sublime

from . import libgit
from . import libmodify

CLOSE_BRANCH_STATUS_TAB = 'cr_close_active_branch_status'
CHECKOUT_AND_REBASE = 'cr_checkout_and_rebase_branch'
SHOW_BRANCH_STATUS = 'cr_show_branch_status'
CHECKOUT = 'cr_checkout_branch'
OPEN_CHANGED_FILES = 'cr_open_changed_files'
CR_NOP_TRAMPOLINE = 'cr_nop_trampoline'


def _CreateCommandLink(cmd:str, **args) -> str:
  return f'<a href="{sublime.command_url(cmd, dict(args))}">'


def _MakeLinkItem(text:str, command:str, **kwargs):
  if kwargs.get('reset', True):
    kwargs['then'] = [
      (CLOSE_BRANCH_STATUS_TAB, {}),
      (SHOW_BRANCH_STATUS, {})
    ]
  yield '<li>'
  yield _CreateCommandLink(command, **kwargs)
  yield text
  yield '</a>'
  yield '</li>'


def _MakeControls():
  yield '<ul class="pst_global_control">'
  yield from _MakeLinkItem('Refresh', CR_NOP_TRAMPOLINE)
  yield '</ul>'


def _CssTemplate():
  yield '<style>'
  yield '''
  .pst_container {
    background-color: #335C67;
    padding: 10px;
    margin-bottom: 10px;
  }
  .pst_name {
    color: #F8EADD;
  }
  .pst_operations {
    margin: 0px;
  }
  .pst_current_True {
    color: #52D1DC;
  }
  .pst_fileschanged {}
  .pst_filechange {}
  .pst_filedelts {}
  .pst_children {
    padding:10px;
    margin:0px;
  }
  .pst_childwrapper {
    border-left: 3px solid #947EB0;
  }
  '''
  yield '</style>'


def _RenderHtmlStream(trees, **kwargs):
  yield '<body class="pst_render">'
  yield from _CssTemplate()
  yield from _MakeControls()
  for tree in trees:
    yield from tree.GenerateHTML(**kwargs)
  yield '</body>'


class PatchSetTree(typing.NamedTuple):
  dependent_patches: typing.List['PatchSetTree']
  branch: libgit.Gerrit

  @classmethod
  def Local(cls, branch:str, files:[str]):
    return cls([], None, None, branch, files)

  @classmethod
  def Remote(cls, number:int, title:str, files:[str]):
    return cls([], number, title, None, files)

  def Set(self, key:str, value:typing.Any) -> 'PatchSetTree':
    values = self._asdict()
    values[key] = value
    return PatchSetTree(**values)

  def GenerateHTML(self, **kwargs) -> [str]:
    ahead, behind = self.branch.AheadBehindBranch()
    current = self.branch.IsCurrent()
    clean = kwargs.get('clean', False)

    yield '<div class="pst_container">'
    yield f'<span class="pst_name pst_current_{current}">'
    yield self.branch.PatchSetTitle()
    yield '</span>'

    yield '<ul class="pst_operations">'
    if self.branch._issue:
      yield '<li>'
      yield f'<a href="{self.branch._server}/c/chromium/src/+/{self.branch._issue}">'
      yield f'Open cl #{self.branch._issue} in browser'
      yield '</a>'
      yield '</li>'

    if current:
      yield from _MakeLinkItem(
        'Open Changed Files', OPEN_CHANGED_FILES, reset=False)

    if not current and clean:
      yield from _MakeLinkItem(
        'Checkout Branch', CHECKOUT, branch=self.branch.branchname)

    if current and not clean:
      yield from _MakeLinkItem('Commit Changes to XXX files', 'CRNOTHIHNG')

    if ahead == 0:
      yield '<li>'
      yield f'<a href="remove/{self.branch.branchname}">'
      yield 'Remove this alread-merged branch'
      yield '</a>'
      yield '</li>'

    if current and ahead > 1:
      yield '<li>'
      yield f'<a href="compress/{self.branch.branchname}">'
      yield f'Squash {ahead} commits'
      yield '</a>'
      yield '</li>'

    if behind != 0:
      message = f'Rebase Forward {behind} commits'
      if not current:
        message = f'Checkout and {message}'
      yield from _MakeLinkItem(
        message, CHECKOUT_AND_REBASE, branch=self.branch.branchname)

    yield '</ul>'

    if self.dependent_patches:
      yield '<div class="pst_children">'
      for dependent in self.dependent_patches:
        yield '<div class="pst_childwrapper">'
        yield from dependent.GenerateHTML(**kwargs)
        yield '</div>'
      yield '</div>'

    yield '</div>'


def GetAllPatchSets(gitdir:str) -> typing.List[PatchSetTree]:
  root_trees:typing.List[PatchSetTree] = []

  tree_patches:typing.Dict[str, PatchSetTree] = {}
  gerrit_branches:typing.Dict[str, libgit.Gerrit] = {}

  for branch in libgit.Gerrit.GetAllNamedLocalBranches(gitdir):
    if branch.branchname != 'main':
      gerrit_branches[branch.branchname] = branch
      tree_patches[branch.branchname] = PatchSetTree([], branch)

  for branchname, branch in gerrit_branches.items():
    parent = branch.Parent()
    if parent is None or parent.branchname == 'main':
      root_trees.append(tree_patches[branchname])
    else:
      tree_patches[parent.branchname].dependent_patches.append(
        tree_patches[branchname])

  return root_trees


def RootPatchesToDescriptiveHtml(patches:typing.List[PatchSetTree]) -> str:
  def CssTemplate():
    yield '<style>'
    yield '''
    .pst_container {
      background-color: #335C67;
      padding: 10px;
      margin-bottom: 10px;
    }
    .pst_name {
      color: #F8EADD;
    }
    .pst_operations {
      margin: 0px;
    }
    .pst_current_True {
      color: #52D1DC;
    }
    .pst_fileschanged {}
    .pst_filechange {}
    .pst_filedelts {}
    .pst_children {
      padding:10px;
      margin:0px;
    }
    .pst_childwrapper {
      border-left: 3px solid #947EB0;
    }
    '''
    yield '</style>'

  def RenderHtmlStream(**kwargs):
    yield '<body class="pst_render">'
    yield from CssTemplate()
    for patch in patches:
      yield from patch.GenerateHTML(**kwargs)
    yield '</body>'

  clean = not libmodify.CurrentBranchDirty(self.branch.git_dir)

  return '\n'.join(RenderHtmlStream())


def RenderAllPatches(gitdir:str) -> str:
  root_trees:typing.List[PatchSetTree] = []

  tree_patches:typing.Dict[str, PatchSetTree] = {}
  gerrit_branches:typing.Dict[str, libgit.Gerrit] = {}

  for branch in libgit.Gerrit.GetAllNamedLocalBranches(gitdir):
    if branch.branchname != 'main':
      gerrit_branches[branch.branchname] = branch
      tree_patches[branch.branchname] = PatchSetTree([], branch)

  for branchname, branch in gerrit_branches.items():
    parent = branch.Parent()
    if parent is None or parent.branchname == 'main':
      root_trees.append(tree_patches[branchname])
    else:
      tree_patches[parent.branchname].dependent_patches.append(
        tree_patches[branchname])

  clean = not libmodify.CurrentBranchDirty(gitdir)
  return '\n'.join(_RenderHtmlStream(root_trees, clean=clean))


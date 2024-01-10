
from . import librun


def CurrentBranchDirty(gitdir) -> bool:
  status = librun.RunCommand('git status --porcelain', cwd=gitdir)
  return bool(status.returncode or status.stdout or status.stderr)


def _CleanBranch(gitdir:str):
  librun.RunCommand('git rebase --abort', cwd=gitdir)
  if not _CurrentBranchDirty(gitdir):
    return
  librun.RunCommand('git clean -f -d', cwd=gitdir)
  if not _CurrentBranchDirty(gitdir):
    return
  librun.RunCommand('git checkout main', cwd=gitdir)
  if not _CurrentBranchDirty(gitdir):
    return
  librun.RunCommand('git reset --hard main', cwd=gitdir)


def CheckoutAndRebaseBranch(gitdir:str, branchname:str) -> bool:
  librun.OutputOrError(f'git checkout {branchname}', cwd=gitdir)
  if librun.RunCommand(f'git rebase', cwd=gitdir).returncode:
    _CleanBranch()
    return False
  elif _CurrentBranchDirty(gitdir):
    _CleanBranch()
    return False
  return True


def CheckoutBranch(gitdir:str, branchname:str) -> bool:
  librun.OutputOrError(f'git checkout {branchname}', cwd=gitdir)
  return True

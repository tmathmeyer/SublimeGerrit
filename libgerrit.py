
import json
import sublime
import typing
import urllib

from . import librun


ALL_BRANCHES = 'git branch --format "%(refname:short)"'
CURRENT_BRANCH = 'git symbolic-ref -q HEAD'
DEFAULT_BRANCH = 'git symbolic-ref refs/remotes/origin/HEAD'
GET_PROPERTY = 'git config --get branch.{}.{}'
GET_PARENT = 'git rev-parse --abbrev-ref {}@{{u}}'


CRREV_DETAIL_URI = '{server}/changes/{issue}'
CRREV_COMMENTS_URI = '{server}/changes/{issue}/comments'


class Branch(typing.NamedTuple):
  branchname: str
  git_dir: str

  @classmethod
  def Current(cls, directory:str) -> 'Branch':
    branchname = librun.OutputOrError(CURRENT_BRANCH, cwd=directory)
    if not branchname.startswith('refs/heads/'):
      raise ValueError(f'not a valid branch: {branchname}')
    return cls.Get(branchname[11:], directory)

  @classmethod
  def Default(cls, directory:str) -> 'Branch':
    branchname = librun.OutputOrError(DEFAULT_BRANCH, cwd=directory)
    return cls.Get(branchname[20:], directory)

  @classmethod
  def Get(cls, branchname:str, directory:str) -> 'Branch':
    if not hasattr(cls, '__cache'):
      setattr(cls, '__cache', {})
    cache = getattr(cls, '__cache')
    if branchname not in cache:
      cache[branchname] = cls(branchname, directory)
    return cache[branchname]

  @classmethod
  def GetAllNamedLocalBranches(cls, directory:str):
    branches = librun.OutputOrError(ALL_BRANCHES, cwd=directory)
    for branch in branches.split('\n'):
      yield cls.Get(branch)

  def __getattr__(self, attr:str) -> str:
    try:
      return librun.OutputOrError(GET_PROPERTY.format(self.branchname, attr),
                                  cwd=self.git_dir)
    except:
      raise AttributeError(attr)

  def Children(self) -> typing.Iterator['Branch']:
    for child in Branch.GetAllNamedLocalBranches(self.git_dir):
      if child.Parent() == self:
        yield child

  def Parent(self) -> 'Branch':
    try:
      parent_name = OutputOrError(GET_PARENT.format(self.branchname),
                                  cwd=self.git_dir)
      if parent_name == 'heads/origin/main':
        return None
      return Branch.Get(parent_name)
    except:
      return None


class Comment(typing.NamedTuple):
  author: str
  date: str
  content: str
  message_id: str
  line: int

  @classmethod
  def MakePendingResponse(cls, message:str) -> 'Comment':
    return Comment('', '', message, '', 0)


class CommentChain(typing.NamedTuple):
  initial_message_id: str
  final_comment_open: typing.List[bool]
  line: int
  comments: typing.List[Comment]

  def Resolve(self, value):
    self.final_comment_open[0] = value

  def IsUnresolved(self):
    return self._final_comment_open[0]


class Gerrit(Branch):
  def __init__(self, *args, **kwargs):
    self._issue = getattr(self, 'gerritissue')
    self._server = getattr(self, 'gerritserver')
    self._data_crrev_detail = None

  def _query(self):
    if self._data_crrev_detail is None:
      uri = CRREV_DETAIL_URI.format(server=self._server, issue=self._issue)
      options = '&'.join([f'o={o}' for o in ('CURRENT_FILES', 'CURRENT_REVISION')])
      uri = f'{uri}?{options}'
      with urllib.request.urlopen(uri) as r:
        self._data_crrev_detail = json.loads(r.read()[5:])
    return self._data_crrev_detail

  def Flush(self):
    self._data_crrev_detail = None

  def FileChangeList(self):
    query = self._query()
    current_revision = query['revisions'][query['current_revision']]
    return list(current_revision['files'].keys())

  def GetCommentsForFileInChange(self, filename:str) -> [CommentChain]:
    if filename.startswith(self.git_dir):
      filename = filename[len(self.git_dir)+1:]
    else:
      sublime.status_message('This file is not part of the chromium project')
      return []

    uri = CRREV_COMMENTS_URI.format(server=self._server, issue=self._issue)
    with urllib.request.urlopen(uri) as r:
      comment_json = json.loads(r.read()[5:])

    if filename not in comment_json:
      sublime.status_message('filename not in comment list')
      return []

    # Map every comment id to it's chain
    comment_chains = {}

    # store all "head-of-chain" comments
    chain_heads = []

    for json_comment in comment_json[filename]:
      comment = Comment(
        json_comment['author']['name'],
        json_comment['updated'],
        json_comment['message'],
        json_comment['id'],
        json_comment['line'])

      if 'in_reply_to' in json_comment:
        parent = json_comment['in_reply_to']
        if parent not in comment_chains:
          sublime.status_message('gerrit comments out of order!')
          return []
        comment_chains[comment.message_id] = comment_chains[parent]
      else:
        chain_heads.append(comment.message_id)
        comment_chains[comment.message_id] = CommentChain(
          comment.message_id, [False], comment.line, [])

      comment_chains[comment.message_id].comments.append(comment)
      comment_chains[comment.message_id].Resolve(json_comment['unresolved'])

    return [comment_chains[cmt_id] for cmt_id in chain_heads]








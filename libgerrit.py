
import typing
from . import libgit


class ChangeRevisionInfo(typing.NamedTuple):
  kind:str
  number:int
  created:str
  #uploader:GerritAccount
  ref:str
  #fetch:ChangeFetchInfo
  branch:str
  description:str


class ChangeInfo(typing.NamedTuple):
  @staticmethod
  def GetUrlPattern():
    return '{server}/changes/{change_id}?o=CURRENT_REVISION'

  id:str
  triplet_id:str
  project:str
  branch:str
  #attention_set:dict
  #removed_from_attention_set:dict
  #hashtags:list[Hashtag]
  change_id:str
  subject:str
  status:str
  created:str
  updated:str
  submit_type:str
  insertions:int
  deletions:int
  total_comment_count:int
  has_review_started:bool
  meta_rev_id:str
  #_number:int
  #owner:GerritAccount
  current_revision:str
  revisions:typing.Mapping[str,ChangeRevisionInfo]
  #requirements:ChangeRequirements
  #submit_records:list[??]


class ChangeCommentAuthor(typing.NamedTuple):
  account_id:int
  name:str
  email:str
  display_name:str = None
  #avatars:list[UserAvatar]


class ChangeComment(typing.NamedTuple):
  @staticmethod
  def GetUrlPattern():
    return '{server}/changes/{change_id}/comments'

  author:ChangeCommentAuthor
  change_message_id:str
  unresolved:bool
  patch_set:int
  id:str
  updated:str
  message:str
  in_reply_to:str = None
  line: int = 0


class GerritProjectInfo(typing.NamedTuple):
  server:str
  branch_name:str
  upstream_change_id:int

  @staticmethod
  def FromSettings(settings):
    checkout = settings['chromium_checkout']
    branch = libgit.Branch.Current(checkout)
    return GerritProjectInfo(
      branch.gerritserver, branch.branchname, branch.gerritissue)


import sublime
import typing
from . import libfetch
from . import libgerrit
from . import libtemplate


COMMENT_CHAIN_RENDER_TEMPLATE = '''
<body class="codereview-comment">
  <style>
    .cr-widthfix \\{
      width:{context.width}px;
      margin:0 20px;
      padding:4px;
      background-color:{color};
      color:#000;
    \\}
    .cr-message-entry \\{
      border-bottom: 1px solid black;
    \\}
    .cr-control-link \\{
      padding-right: 5px;
    \\}
    .cr-message-body \\{
      border: 1px solid #333;
      background-color: #eee;
      margin-bottom: 4px;
    \\}
  </style>
  <div class="cr-message-entry-list cr-widthfix">
    {/context.comment_chain.comments}
      <div class="cr-message-entry">
        <div class="cr-message-header">
          <div class="cr-message-author">
            {.author}
          </div>
          <div class="cr-message-date">
            {.date}
          </div>
        </div>
        <div class="cr-message-body">
          {.content}
        </div>
      </div>
    {/context.comment_chain.comments}
  </div>
  <div class="cr-controls cr-widthfix">
    {/controls}
      <a href="{.control_function}" class="cr-control-link">
        {.rendername}</a>
    {/controls}
  </div>
</body>
'''


class Mut():
  def __init__(self, value):
    self._value = value
  def value(self):
    return self._value
  def set_value(self, value):
    self._value = value
  @staticmethod
  def __getitem__(key):
    return key
  def __class_getitem__(cls, key):
    return key


class Comment(typing.NamedTuple):
  author: str
  date: str
  content: str
  line: int
  is_applicable_suggestion: bool
  patch_set: int
  unresolved: bool
  upstream_message_id: int
  comment_chain: Mut['CommentChain']


class CommentChain(typing.NamedTuple):
  chain_id: int
  initial_message: Comment
  comments: typing.List[Comment]
  attached_to_latest_patchset: bool
  marked_complete_upstream: bool
  marked_complete_downstream: Mut[bool]
  render_context: Mut['CommentChainRenderContext']


class CommentChainControl(typing.NamedTuple):
  rendername: str
  control_function: str


class CommentChainRenderContext(typing.NamedTuple):
  project: libgerrit.GerritProjectInfo
  comment_chain: CommentChain
  view: sublime.View
  width: int
  region: sublime.Region
  upstream_change_info: libgerrit.ChangeInfo
  renderset: Mut[sublime.PhantomSet]

  def CreatePhantom(self, renderset:sublime.PhantomSet, contexts):
    self.renderset.set_value(renderset)
    controls = _ComputeControls(self.comment_chain)
    html = libtemplate.Render(COMMENT_CHAIN_RENDER_TEMPLATE,
      context=self,
      controls=controls,
      color=_ComputeCommentColor(self.comment_chain))
    return sublime.Phantom(self.region, html, sublime.PhantomLayout.BLOCK,
                           on_navigate=_HandleControlsClick(
                            self, controls, contexts))


def _MostRecentUpstream(comments):
  for comment in comments[::-1]:
    if comment.upstream_message_id:
      return comment
  return None


def _MostRecentLocalDraft(comments):
  for comment in comments[::-1]:
    if not comment.upstream_message_id:
      return comment
  return None


def _HandleControlsClick(context, controls, contexts):
  def OperationProcessor(href):
    for control in controls:
      if control.control_function == href:
        chain = context.comment_chain
        upstream = _MostRecentUpstream(context.comment_chain.comments)
        if href == 'done':
          _CreateDraftComment('Done', True, context)
          RenderContexts(context.view, contexts)
        else:
          print(href)



  return OperationProcessor


def RenderContexts(view:sublime.View, ctxs:'list[CommentChainRenderContext]'):
  ps_name = 'codereview_' + view.file_name().replace('/', '_')
  phantom_set = sublime.PhantomSet(view, ps_name)
  phantoms = [context.CreatePhantom(phantom_set, ctxs) for context in ctxs]
  phantom_set.update(phantoms)


def _CreateDraftComment(content:str, resolved:bool, context):
  draft = Comment(author='Ted - Draft',
                  date='',
                  content=content,
                  line=context.comment_chain.comments[0].line,
                  is_applicable_suggestion=False,
                  patch_set=context.upstream_change_info.current_revision,
                  unresolved=not resolved,
                  upstream_message_id=None,
                  comment_chain=Mut(context.comment_chain))
  context.comment_chain.comments.append(draft)
  context.comment_chain.marked_complete_downstream.set_value(True)
  _SavePendingComment(context.project.upstream_change_id,
                      context.view.file_name(), draft)



def _CreateCommentFromUpstream(upstream):
  # Do some processing on the message:
  suggestion = False
  content = upstream.message
  if content.startswith('```suggestion') and content.endswith('```'):
    suggestion = True
    content = 'Suggested Edit:\n' + content[13:-3]
  content = content.replace('\n', '<br />')
  return Comment(
    author=upstream.author.name,
    date=upstream.updated,
    content=content,
    line=upstream.line,
    is_applicable_suggestion=suggestion,
    patch_set=upstream.patch_set,
    unresolved=upstream.unresolved,
    upstream_message_id=upstream.id,
    comment_chain=Mut(None))


def _CreateCommentChainFromComments(drafts, comments, id, current_revision):
  drafts = [d for d in drafts if d.comment_chain.value() == id]
  marked_complete_upstream = not comments[-1].unresolved
  attached_to_latest_patchset = comments[-1].patch_set == current_revision
  marked_complete_downstream = bool(drafts and not drafts[-1].unresolved)
  comments += drafts
  chain = CommentChain(
    chain_id=id,
    initial_message=comments[0],
    comments=comments,
    attached_to_latest_patchset=attached_to_latest_patchset,
    marked_complete_upstream=marked_complete_upstream,
    marked_complete_downstream=Mut(marked_complete_downstream),
    render_context=Mut(None))
  for comment in comments:
    comment.comment_chain.set_value(chain)
  return chain


def _CreateContextFromChain(chain, view, project, change_info):
  context = CommentChainRenderContext(
    project=project,
    comment_chain=chain,
    view=view,
    width=int(view.viewport_extent()[0]) - 40,
    region=_ComputeCommentRegion(chain, view),
    upstream_change_info=change_info,
    renderset=Mut(None))
  chain.render_context.set_value(context)
  return context


def _ComputeCommentColor(chain):
  if chain.marked_complete_upstream:
    return '#e8eaed'
  if chain.marked_complete_downstream.value():
    return '#e8eaed'
  return '#fef7e0'


def _ComputeCommentRegion(chain, view):
  text_point = view.text_point(chain.initial_message.line - 1, 0)
  return sublime.Region(text_point, text_point)


def _ComputeControls(chain):
  controls = []
  if not chain.marked_complete_upstream:
    if chain.marked_complete_downstream.value():
      controls.append(CommentChainControl('Discard', 'discard'))
      controls.append(CommentChainControl('Edit', 'edit'))
    else:
      controls.append(CommentChainControl('Quick-Done', 'done'))
      controls.append(CommentChainControl('Reply', 'respond'))
      if chain.comments[-1].is_applicable_suggestion:
        controls.append(CommentChainControl('Apply', 'apply'))
  return controls


def CreateCommentChainContextsForView(view:sublime.View):
  settings = sublime.load_settings('Chromium.sublime-settings')
  checkout = settings['chromium_checkout']
  filename = view.file_name()
  if filename.startswith(checkout):
    filename = filename[len(checkout)+1:]
  else:
    sublime.status_message('This file is not part of the gerrit checkout')
    return []

  project = libgerrit.GerritProjectInfo.FromSettings(settings)
  change_info = libfetch.FetchInstance(libgerrit.ChangeInfo,
    server=project.server, change_id=project.upstream_change_id)
  patch_set = change_info.revisions[change_info.current_revision].number
  if change_info.total_comment_count == 0:
    sublime.status_message('This file has no upstream comments')
    return []

  comment_map = libfetch.FetchInstanceMap(libgerrit.ChangeComment,
    server=project.server, change_id=project.upstream_change_id)
  if filename not in comment_map:
    # TODO: find a good way to cache local draft comments as well, and join
    # those here in comment map before making this check
    sublime.status_message('This file has no upstream comments')
    return []

  comment_id_map = {comment.id:comment for comment in comment_map[filename]}
  comment_to_root_map = {}
  root_to_remotes_map = {}
  for comment in comment_map[filename]:
    if comment.in_reply_to == None:
      comment_to_root_map[comment.id] = comment.id
      root_to_remotes_map[comment.id] = [comment]
    else:
      assert comment.in_reply_to in comment_to_root_map
      comment_to_root_map[comment.id] = comment_to_root_map[comment.in_reply_to]
      root_to_remotes_map[comment_to_root_map[comment.id]].append(comment)

  contexts = []
  local_pending_comments = list(_LoadPendingComments(
    project.upstream_change_id, view.file_name()))
  for root_id, comment_list in root_to_remotes_map.items():
    comments = []
    for comment in comment_list:
      comments.append(_CreateCommentFromUpstream(comment))
    chain = _CreateCommentChainFromComments(
      local_pending_comments, comments, root_id, patch_set)
    if chain.attached_to_latest_patchset:
      contexts.append(_CreateContextFromChain(chain, view, project, change_info))

  return contexts


def _LoadPendingComments(change_id:int, filename:str):
  settings = sublime.load_settings('Chromium.sublime-settings')
  pending = settings['pending_responses']
  for comment in pending.get(change_id, {}).get(filename, []):
    comment['comment_chain'] = Mut(comment['comment_chain'])
    yield Comment(**comment)


def _SavePendingComment(change_id:int, filename:str, comment:Comment):
  settings = sublime.load_settings('Chromium.sublime-settings')
  pending = settings['pending_responses']
  serialized = comment._asdict()
  serialized['comment_chain'] = serialized['comment_chain'].value().chain_id
  if change_id not in pending:
    pending[change_id] = {}
  if filename not in pending[change_id]:
    pending[change_id][filename] = []
  pending[change_id][filename].append(serialized)
  # TODO: How will this ever get cleared out?
  settings.set('pending_responses', pending)
  sublime.save_settings('Chromium.sublime-settings')

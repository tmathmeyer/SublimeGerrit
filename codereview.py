
import sublime_plugin
import sublime
import typing

from . import libgerrit


class ControlsContext(typing.NamedTuple):
  chain: libgerrit.CommentChain
  view:sublime.View
  region: sublime.Region
  change_id: str
  width: int
  color: str
  controls: typing.List[str]
  additional: libgerrit.Comment

  def ToCommentContext(self):
    return CommentContext(None, self.region, self.width, self.color)

  def ToPhantom(self, phantoms:sublime.PhantomSet):
    return sublime.Phantom(self.region, _CommentChainToControls(self),
                           sublime.PhantomLayout.BLOCK,
                           on_navigate=controls(self, phantoms))


class CommentContext(typing.NamedTuple):
  comment: libgerrit.Comment
  region: sublime.Region
  width: int
  color: str

  def Clone(self, new_comment:libgerrit.Comment):
    return CommentContext(new_comment, self.region, self.width, self.color)

  def ToPhantom(self) -> sublime.Phantom:
    return sublime.Phantom(self.region, _CommentToPhantomText(self),
                           sublime.PhantomLayout.BLOCK)


def _HandleUserInput(change:typing.Callable, finished:bool):
  def Thunk(user_input:str):
    change(user_input, finished)
  return Thunk


# Bunch these together. They can't be nested inside `controls` because
# sublime won't reload them.
def _op_Done(change, **_) -> (str, bool):
  change('Done', True)
def _op_Respond(change, view, **_) -> (str, bool):
  view.window().show_input_panel('Message:', '',
    on_done=_HandleUserInput(change, True),
    on_change=None,
    on_cancel=None)
def _op_Discard(change, **_) -> (str, bool):
  change(None, None)
def _op_Edit(change, reply, finished, view) -> (str, bool):
  view.window().show_input_panel('Message:', reply,
    on_done=_HandleUserInput(change, True),
    on_change=None,
    on_cancel=None)
def _op_Completed(change, reply, **_) -> (str, bool):
  change(reply, True)
def _op_Incomplete(change, reply, **_) -> (str, bool):
  change(reply, False)


def _MakeChangeThunk(context, phantoms, chain_id):
  def _handle_change(reply, finished):
    settings = sublime.load_settings('Chromium.sublime-settings')
    show_pending_comments = settings['show_pending_comments']
    pending_responses = settings['pending_responses']
    additional = None
    if reply is None and finished is None:
      pending_responses[context.change_id].pop(chain_id)
    else:
      additional = {'reply': reply, 'finished': finished}
      pending_responses[context.change_id][chain_id] = additional
    settings.set('pending_responses', pending_responses)
    sublime.save_settings('Chromium.sublime-settings')

    new_controls = _BuildControlsContext(
      context.chain, context.view, context.change_id, additional)
    new_phantoms = []
    if not finished or show_pending_comments:
      new_phantoms = _CollectPhantoms(new_controls, phantoms)
    phantoms.update(new_phantoms)
  return _handle_change


def controls(context:ControlsContext, phantoms:sublime.PhantomSet):
  def handle(href:str):
    # Grab settings
    settings = sublime.load_settings('Chromium.sublime-settings')
    pending_responses = settings['pending_responses']

    # Compute change to comment
    chain_id, operation = href.split('/')
    old_comment = pending_responses.get(context.change_id, {}).get(chain_id, {})
    eval(f'_op_{operation}')(change=_MakeChangeThunk(context, phantoms, chain_id),
                             view=context.view, **old_comment)
  return handle


def _CommentToPhantomText(context: CommentContext) -> str:
  return f'''
    <body class='crrev-comment'>
      <style>
      .comment {{
        width: {context.width-40}px;
        margin: 0 20px;
        padding: 4px;
        background-color: {context.color};
        color: #000;
      }}
      </style>
      <div class='comment'>
        <div class='header'>
          <div class='author'>{context.comment.author}</div>
          <div class='date'>{context.comment.date}</div>
        </div>
        <div class='content'>{context.comment.content}</div>
      </div>
    </body>
  '''


def _CommentChainToControls(context: ControlsContext) -> str:
  m_id = context.chain.initial_message_id
  def ctrl2a(ctrl):
    return f'<a href="{m_id}/{ctrl}">{ctrl}</a>'

  controls = '\n'.join(ctrl2a(ctrl) for ctrl in context.controls)
  return f'''
    <body class='crrev-controls'>
      <style>
        .controls {{
          width: {context.width-40}px;
          margin: 0 20px;
          padding: 4px;
          background-color: {context.color};
          color: #000;
        }}
      </style>
      <div class='controls'>
        {controls}
      </div>
    </body>
  '''


def _CollectPhantoms(controls:ControlsContext, phantoms:sublime.PhantomSet):
  comment_context = controls.ToCommentContext()
  for comment in controls.chain.comments:
    yield comment_context.Clone(comment).ToPhantom()
  if controls.additional:
    yield comment_context.Clone(controls.additional).ToPhantom()
  yield controls.ToPhantom(phantoms)


def _BuildControlsContext(chain:libgerrit.CommentChain,
                          view:sublime.View,
                          change_id:str,
                          pending=None):
  text_point = view.text_point(chain.line - 1, 0)
  region = sublime.Region(text_point, text_point)
  width, _ = view.viewport_extent()

  controls, color, additional = _BuildControlsDetail(chain, pending)
  return ControlsContext(
    chain, view, region, change_id, width, color, controls, additional)


def _BuildControlsDetail(chain:libgerrit.CommentChain, pending):
  controls = []
  color = '#fef7e0' # Same yellow color as gerrit lol
  additional = None
  if pending:
    controls.append('Discard')
    controls.append('Edit')
    reply, finished = (pending[k] for k in ('reply', 'finished'))
    additional = libgerrit.Comment.MakePendingResponse(reply)
    if finished:
      controls.append('Incomplete')
      color = '#e8eaed'
    else:
      controls.append('Completed')
  else:
    controls.append('Done')
    controls.append('Respond')
  return controls, color, additional


def _ApplyCommentChain(chain:libgerrit.CommentChain, view:sublime.View, change_id:str, pending=None):
  phantom_set = sublime.PhantomSet(view, f'{chain.initial_message_id}')
  controls_context = _BuildControlsContext(chain, view, change_id, pending)
  phantom_set.update(_CollectPhantoms(controls_context, phantom_set))


def GetPendingChange(chain:libgerrit.CommentChain, pending:dict, change_id:str):
  if change_id not in pending:
    return None
  if chain.initial_message_id not in pending[change_id]:
    return None
  return pending[change_id][chain.initial_message_id]


class ChangelistFileOpenListener(sublime_plugin.EventListener):
  def on_load_async(self, view:sublime.View):
    settings = sublime.load_settings('Chromium.sublime-settings')
    checkout = settings['chromium_checkout']
    show_complete = settings['show_completed_comments']
    show_pending = settings['show_pending_comments']
    pending_responses = settings['pending_responses']
    current_branch = libgerrit.Gerrit.Current(checkout)
    for chain in current_branch.GetCommentsForFileInChange(view.file_name()):
      pending = GetPendingChange(chain, pending_responses, current_branch._issue)
      if pending is not None:
        if show_pending or not pending['finished']:
          _ApplyCommentChain(chain, view, current_branch._issue, pending)
      elif show_complete:
        _ApplyCommentChain(chain, view, current_branch._issue)
      elif pending.IsUnresolved():
        _ApplyCommentChain(chain, view, current_branch._issue)

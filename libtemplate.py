
import typing


class ControlEntry(typing.NamedTuple):
  text_content: str
  raw_text: bool


class LoopEntry(typing.NamedTuple):
  control_entry: ControlEntry
  repetition: typing.List[typing.Union[ControlEntry,'LoopEntry']]


class SyntaxError(Exception):
  def __init__(self, msg, line, col):
    super().__init__(f'@{line}#{col}: {msg}')

  @staticmethod
  def Assert(test, msg, line, col):
    if not test:
      raise SyntaxError(msg, line, col)


def _TemplateToControlsList(template:str):
  pending_text = ''
  expecting_close_brace = False
  is_pending_escape = False
  column = 0
  line = 1
  for character in template:
    if character == '\n':
      column = 0
      line += 1
    column += 1
    if is_pending_escape and character == '{':
      pending_text += '{'
      is_pending_escape = False
    elif is_pending_escape and character == '}':
      pending_text += '}'
      is_pending_escape = False
    elif is_pending_escape:
      pending_text += '\\'
      pending_text += character
      is_pending_escape = False
    elif character == '{':
      if pending_text:
        yield ControlEntry(pending_text, True)
        pending_text = ''
      SyntaxError.Assert(not expecting_close_brace,
        "Found `{` while expecting `}`", line, column)
      assert not expecting_close_brace
      expecting_close_brace = True
    elif character == '}':
      SyntaxError.Assert(expecting_close_brace,
        "Found `}` while not parsing control", line, column)
      SyntaxError.Assert(pending_text,
        "Found `}` with no pending control text", line, column)
      assert expecting_close_brace
      assert pending_text
      yield ControlEntry(pending_text, False)
      expecting_close_brace = False
      pending_text = ''
    elif character == '\\':
      is_pending_escape = True
    else:
      pending_text += character

  SyntaxError.Assert(not expecting_close_brace,
    "Found `{` while expecting `}`", line, column)
  assert not expecting_close_brace
  if pending_text:
    yield ControlEntry(pending_text, True)


def _DropControlsListIntoTree(ctrls: typing.Iterator[ControlEntry], init=None):
  branches = []
  for control in ctrls:
    if init and init.text_content == control.text_content:
      return branches
    if control.text_content[0] == '/':
      branches.append(LoopEntry(control, _DropControlsListIntoTree(ctrls, init=control)))
    else:
      branches.append(control)
  return branches


def _ComputeLookupPath(lookup_path:list, env):
  if not lookup_path or lookup_path == '':
    # This is either for single entries in kwargs, or from just a `.`
    return env
  if type(env) == dict:
    return _ComputeLookupPath(lookup_path[1:], env[lookup_path[0]])
  return _ComputeLookupPath(lookup_path[1:], getattr(env, lookup_path[0]))


def _ComputeLookup(lookup_key:str, env, kwargs):
  lookup_path = lookup_key.split('.')
  if lookup_path[0] == '':
    # starts with a dot, comes from env. No kwargs lookup
    return _ComputeLookupPath(lookup_path[1:], env)

  # Get the kwargs entry and continue with path
  return _ComputeLookupPath(lookup_path[1:], kwargs[lookup_path[0]])


def _RenderTreeWithScope(tree:typing.List, env, kwargs):
  for branch in tree:
    if type(branch) == LoopEntry:
      iterable = _ComputeLookup(branch.control_entry.text_content[1:], env, kwargs)
      if type(iterable) == dict:
        for key, value in iterable.items():
          entry = {'key': key, 'value': value}
          yield from _RenderTreeWithScope(branch.repetition, entry, kwargs)
      else:
        for entry in iterable:
          yield from _RenderTreeWithScope(branch.repetition, entry, kwargs)
    elif branch.raw_text:
      yield str(branch.text_content)
    else:
      yield str(_ComputeLookup(branch.text_content, env, kwargs))


def Render(template:str, **kwargs):
  ctrls = _TemplateToControlsList(template)
  ctrl_tree = _DropControlsListIntoTree(ctrls)
  output = _RenderTreeWithScope(ctrl_tree, None, kwargs)
  return ''.join(output)

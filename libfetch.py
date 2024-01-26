
import collections
import json
import urllib.request
import types
import typing


def FetchInstance(typeclass:type, **kwargs) -> 'typeclass':
  if not hasattr(typeclass, 'GetUrlPattern'):
    raise ValueError(f'Cant fetch {typeclass}')
  request_uri = typeclass.GetUrlPattern().format(**kwargs)
  with urllib.request.urlopen(request_uri) as r:
    response_json = json.loads(r.read()[5:])
  return _Json2Type(typeclass, response_json)

def FetchInstanceMap(typeclass:type, **kwargs):
  if not hasattr(typeclass, 'GetUrlPattern'):
    raise ValueError(f'Cant fetch {typeclass}')
  request_uri = typeclass.GetUrlPattern().format(**kwargs)
  with urllib.request.urlopen(request_uri) as r:
    response_json = json.loads(r.read()[5:])
  return _Json2Type(typing.Mapping[str, typeclass], response_json)


def _Json2Type(typeclass, json):
  def strunder(key):
    while key and key[0] == '_':
      key = key[1:]
    return key

  #print(f'converting {json} to {typeclass}')

  if type(json) == list:
    return [_Json2Type(typeclass, each) for each in json]

  if type(json) != dict:
    return typeclass(json)

  #if type(typeclass) in (types.GenericAlias, typing._GenericAlias):
  if type(typeclass) == typing._GenericAlias:
    if typeclass.__origin__ == list:
      assert type(json) == list
      return _Json2Type(typeclass.__args__[0], json)
    assert typeclass.__origin__ in (dict, collections.abc.Mapping)
    assert typeclass.__args__[0] == str
    return {k:_Json2Type(typeclass.__args__[1], v) for k,v in json.items()}

  hints = typing.get_type_hints(typeclass)
  clean = {strunder(k):v for k,v in json.items()}
  values = {k:_Json2Type(hints[k],v) for k,v in clean.items() if k in hints}
  return typeclass(**values)

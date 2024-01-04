
import subprocess


def RunCommand(command, cwd=None):
  return subprocess.run(command,
                        encoding='utf-8',
                        shell=True,
                        cwd=cwd,
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE)


def OutputOrError(cmd, cwd=None):
  result = RunCommand(cmd, cwd=cwd)
  if result.returncode:
    raise ValueError(f'|{cmd}|:\n {result.stderr}')
  return result.stdout.strip()

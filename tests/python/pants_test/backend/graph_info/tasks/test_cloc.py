# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

from pants.backend.graph_info.tasks.cloc import CountLinesOfCode
from pants.backend.jvm.targets.java_library import JavaLibrary
from pants.backend.python.targets.python_library import PythonLibrary
from pants.base.file_system_project_tree import FileSystemProjectTree
from pants.engine.fs import create_fs_rules
from pants.engine.isolated_process import create_process_rules
from pants_test.engine.scheduler_test_base import SchedulerTestBase
from pants_test.task_test_base import ConsoleTaskTestBase


class ClocTest(ConsoleTaskTestBase, SchedulerTestBase):
  @classmethod
  def task_type(cls):
    return CountLinesOfCode

  def test_counts(self):
    dep_py_tgt = self.make_target('src/py/dep', PythonLibrary, sources=['dep.py'])
    py_tgt = self.make_target('src/py/foo', PythonLibrary, dependencies=[dep_py_tgt],
                              sources=['foo.py', 'bar.py'])
    java_tgt = self.make_target('src/java/foo', JavaLibrary, sources=['Foo.java'])
    self.create_file('src/py/foo/foo.py', '# A comment.\n\nprint("some code")\n# Another comment.')
    self.create_file('src/py/foo/bar.py', '# A comment.\n\nprint("some more code")')
    self.create_file('src/py/dep/dep.py', 'print("a dependency")')
    self.create_file('src/java/foo/Foo.java', '// A comment. \n class Foo(){}\n')
    self.create_file('src/java/foo/Bar.java', '// We do not expect this file to appear in counts.')

    def assert_counts(res, lang, files, blank, comment, code):
      for line in res:
        fields = line.split()
        if len(fields) >= 5:
          if fields[0] == lang:
            self.assertEquals(files, int(fields[1]))
            self.assertEquals(blank, int(fields[2]))
            self.assertEquals(comment, int(fields[3]))
            self.assertEquals(code, int(fields[4]))
            return
      self.fail('Found no output line for {}'.format(lang))

    scheduler = self.mk_configured_scheduler()

    res = self.execute_console_task(
      targets=[py_tgt, java_tgt],
      options={'transitive': True},
      scheduler=scheduler,
    )
    assert_counts(res, 'Python', files=3, blank=2, comment=3, code=3)
    assert_counts(res, 'Java', files=1, blank=0, comment=1, code=1)

    res = self.execute_console_task(
      targets=[py_tgt, java_tgt],
      options={'transitive': False},
      scheduler=scheduler,
    )
    assert_counts(res, 'Python', files=2, blank=2, comment=3, code=2)
    assert_counts(res, 'Java', files=1, blank=0, comment=1, code=1)

  def test_ignored(self):
    py_tgt = self.make_target('src/py/foo', PythonLibrary, sources=['foo.py', 'empty.py'])
    self.create_file('src/py/foo/foo.py', 'print("some code")')
    self.create_file('src/py/foo/empty.py', '')

    res = self.execute_console_task(
      targets=[py_tgt],
      options={'ignored': True},
      scheduler=self.mk_configured_scheduler(),
    )
    self.assertEquals(['Ignored the following files:',
                       'src/py/foo/empty.py: zero sized file'],
                      filter(None, res)[-2:])

  def mk_configured_scheduler(self):
    return self.mk_scheduler(
      rules=create_fs_rules() + create_process_rules(),
      project_tree=FileSystemProjectTree(self.build_root),
      work_dir=self.pants_workdir
    )

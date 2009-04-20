from distutils.core import setup

setup(name='musplice',
      version='0.1',
      py_modules=['musplice'],
      scripts=['scripts/musplice'],
      data_files=[('/etc/', ['musplice.conf'])],
      author="Matthew Jones",
      author_email="mat@matburt.net")

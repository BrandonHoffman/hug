"""hug/development_runner.py

Contains logic to enable execution of hug APIS locally from the command line for development use

Copyright (C) 2016  Timothy Edmund Crosley

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.
"""
from __future__ import absolute_import

import importlib
import os
import subprocess
import sys
import tempfile
import time
from multiprocessing import Process
from os.path import exists

from hug._version import current
from hug.api import API
from hug.route import cli
from hug.types import boolean, number

INIT_MODULES = list(sys.modules.keys())


def _start_api(api_module, port, no_404_documentation, show_intro=True):
    API(api_module).http.serve(port, no_404_documentation, show_intro)


@cli(version=current)
def hug(file: 'A Python file that contains a Hug API'=None, module: 'A Python module that contains a Hug API'=None,
        port: number=8000, no_404_documentation: boolean=False,
        manual_reload: boolean=False, interval: number=1,
        command: 'Run a command defined in the given module'=None):
    """Hug API Development Server"""
    api_module = None
    if file and module:
        print("Error: can not define both a file and module source for Hug API.")
        sys.exit(1)
    if file:
        sys.path.append(os.path.dirname(os.path.abspath(file)))
        sys.path.append(os.getcwd())
        api_module = importlib.machinery.SourceFileLoader(file.split(".")[0], file).load_module()
    elif module:
        api_module = importlib.import_module(module)
    if not api_module or not hasattr(api_module, '__hug__'):
        print("Error: must define a file name or module that contains a Hug API.")
        sys.exit(1)

    api = API(api_module)
    if command:
        if command not in api.cli.commands:
            print(str(api.cli))
            sys.exit(1)

        sys.argv[1:] = sys.argv[(sys.argv.index('-c') if '-c' in sys.argv else sys.argv.index('--command')) + 2:]
        api.cli.commands[command]()
        return

    if manual_reload:
        _start_api(api_module, port, no_404_documentation)
    else:
        is_running = True
        ran = False
        while is_running:
            try:
                running = Process(target=_start_api, args=(api_module, port, no_404_documentation, not ran))
                running.start()
                files = {}
                for module in list(sys.modules.values()):
                    path = getattr(module, '__file__', '')
                    if path[-4:] in ('.pyo', '.pyc'):
                        path = path[:-1]
                    if path and exists(path):
                        files[path] = os.stat(path).st_mtime

                changed = False
                while not changed:
                    for path, last_modified in files.items():
                        if not exists(path):
                            print('\n> Reloading due to file removal: {}'.format(path))
                            changed = True
                        elif os.stat(path).st_mtime > last_modified:
                            print('\n> Reloading due to file change: {}'.format(path))
                            changed = True

                        if changed:
                            running.terminate()
                            for module in [name for name in sys.modules.keys() if name not in INIT_MODULES]:
                                del(sys.modules[module])
                            if file:
                                api_module = importlib.machinery.SourceFileLoader(file.split(".")[0],
                                                                                  file).load_module()
                            elif module:
                                api_module = importlib.import_module(module)
                            ran = True
                            break
                    time.sleep(interval)
            except KeyboardInterrupt:
                is_running = False

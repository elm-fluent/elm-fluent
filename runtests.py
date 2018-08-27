#!/usr/bin/env python

import argparse
import os
import subprocess
import sys

parser = argparse.ArgumentParser(
    description="Run the test suite, or some tests")
parser.add_argument('--coverage', "-c", action='store_true',
                    help="Run with 'coverage'")
parser.add_argument('--verbose', '-v', action='store_true')
parser.add_argument('--fast', '-f', action='store_true',
                    help="Fast test run, skip end-to-end tests")
parser.add_argument('--show-browser', action='store_true',
                    help="Don't hide web browser")
parser.add_argument('test', type=str, nargs="*",
                    help="Dotted path to a test module, case or method")

args = parser.parse_args()

cmd = ["-m", "unittest"]

if args.test:
    cmd.extend(args.test)
else:
    cmd.extend(["discover", "-t", ".", "-s", "tests"])

if args.verbose:
    cmd.append("-v")

if args.fast:
    os.environ['TEST_FAST_RUN'] = '1'

if args.show_browser:
    os.environ['TEST_SHOW_BROWSER'] = '1'

if args.coverage:
    cmd = ["-m", "coverage", "run"] + cmd

cmd.insert(0, "python")

sys.exit(subprocess.call(cmd))

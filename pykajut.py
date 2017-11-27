#!/usr/bin/python
"""
    PyKajut - Graphical Tool to generate quiz style PNGs from latex input.
    Copyright (C) 2017  Jose M. Esnaola-Acebes

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import sys
import logging
import argparse
from sconf import parser_init, log_conf
from gui import Data, Kajut, MainGui
import os
try:
    import gi
except ImportError:
    logging.exception("Requires pygobject to be installed.")
    gi = None
    exit(1)

try:
    gi.require_version("Gtk", "3.0")
except ValueError:
    logging.exception("Requires gtk3 development files to be installed.")
except AttributeError:
    logging.exception("pygobject version too old.")
gi.require_version('Gtk', '3.0')
try:
    from gi.repository import Gtk, GObject
except (ImportError, RuntimeError):
    logging.exception("Requires pygobject to be installed.")


__author__ = 'Jose M. Esnaola Acebes'

""" Graphical script to replace texts on EPS files using LaTeX engine and psfrag.
"""

print "\n\tPyKajut  Copyright (C) 2017  Jose M. Esnaola-Acebes\n" \
      "\tThis program comes with ABSOLUTELY NO WARRANTY; for details see LICENSE.txt.\n" \
      "\tThis is free software, and you are welcome to redistribute it\n" \
      "\tunder certain conditions; see LICENCE.txt for details.\n"

# -- Configuration I: parsing, debugging.
conf_file, debug, args1, hlp = parser_init()
if not hlp:
    logger = log_conf(debug)
    logger.debug('Formatting parser')
else:
    logger = None

# -- Simulation configuration II: data entry (second parser).
description = 'Utility to generate questions in PNG format to be displayed in kahoot.'
parser = argparse.ArgumentParser(
    description=description,
    usage='python %s  [-i input.tex] [-O <options>]' % sys.argv[0])

parser.add_argument('-i', '--input', default=None, dest='i', type=str,
                    help='Input .tex file containing the questions.')
parser.add_argument('-db', '--debug', default="INFO", dest='db', metavar='<debug>',
                    choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                    help='Debbuging level. Default is INFO.')
parser.add_argument('-ng', '--nogui', default=False, dest='nogui', action='store_true',
                    help='Run the programm without graphical interface (X11).')
parser.add_argument('-d', '--density', default=600, dest='d', type=int, help='Density of the png image.')
parser.add_argument('-c', '--crop', default=False, dest='crop', action='store_true',
                    help='Crop the image, erasing any white margins.')
parser.add_argument('-D', '--design', default=0, dest='design', type=int, metavar='<design>',
                    choices=[0, 1],
                    help='LaTeX design of the enumerate environment.')

args = parser.parse_args()
logger.debug('Introduced arguments: %s' % str(args))
opts = vars(args)

# Some environmental constants:
scriptpath = os.path.realpath(__file__)
scriptdir = os.path.dirname(scriptpath)
cwd = os.getcwd()
logger.debug('We are working in %s' % str(cwd))
data = Data(opts, cwd)
kajut = Kajut(data)

if opts['nogui']:
    logger.info("Non-graphical UI selected.")
    if data.inputfile is None:
        logger.error("Select a .tex file using -i option.")
        exit(-1)
    if data.qblocks:
        logger.info("Creating PNG images of the questions...")
        for name in data.qblocks.keys():
            kajut.create_png(kajut.create_latex(data.qblocks[name]))
        logger.info("All works done!")
    else:
        logger.error("The questions were not found. Check the format. Exiting.")
        exit(1)
else:
    GObject.threads_init()
    mg = MainGui(data, kajut)
    mg.window.show_all()
    Gtk.main()

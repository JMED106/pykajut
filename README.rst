PyKajut - Kahoot, python utility
================================

PyKahoot is a graphical tool to edit LaTeX questions specifically design for their use in Kahoot as PNG images.
Easy to use, modify and extend.

It is build into `Python <http://www.python.org/>`_, and the GUI is based on `GTK+ 3 <https://developer.gnome.org/gtk3/stable/>`_.
You can find a quick tutorial into `Python GTK+ 3 <https://python-gtk-3-tutorial.readthedocs.io/en/latest/index.html>`_.

The program reads the input .tex file, looks for questions in a given format, and uses them to generate PNG files of the 
correponding PDF document.


INSTALLATION
------------

Download the project and uncompress it into any directory:

https://github.com/JMED106/pykajut/archive/master.zip

It does not require installation but some python dependencies need to be fulfilled:

- gi, Gtk >= 3.10
- logging
- colorlog
- argparse
- yaml

In general, in a Debian based system is enough to run: ::
# apt-get install python-yaml python-colorlog


HOW TO USE PyKajut
------------------

PyKajut is a python script that runs in a terminal, and offers a GUI in runtime.
You need to provide the target .tex file to the program: ::

$ /path/to/pykajut.py [-i input.tex] [-O options]

where /path/to/ is the directory where kajut.py is located. ::


Example
******* 
To open an input.tex LaTeX (provided with the package, located in ./tex_files/): ::

$ ./pykajut -i tex_files/input.tex


"""
    PyPSfrag - Graphical Tool to replace selected labels in an EPS file into LaTeX format.
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

import os
import re
import threading
import urllib
import logging
from operator import add

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

try:
    gi.require_version("Gdk", "3.0")
except ValueError:
    logging.exception("Requires gdk development files to be installed.")
except AttributeError:
    logging.exception("pygobject version too old.")

try:
    gi.require_version("GObject", "2.0")
except ValueError:
    logging.exception("Requires GObject development files to be installed.")
except AttributeError:
    logging.exception("pygobject version too old.")

try:
    from gi.repository import Gtk, Gdk, GObject, GdkPixbuf
except (ImportError, RuntimeError):
    logging.exception("Requires pygobject to be installed.")

logging.getLogger('gui').addHandler(logging.NullHandler())
TARGET_TYPE_URI_LIST = 0


class Data:
    def __init__(self, opts, cwd="./"):
        self.logger = logging.getLogger('gui.Data')

        self.cwd = cwd
        self.inputfile = opts['i']
        self.density = opts['d']  # Default density for png conversion
        self.qblocks = {}
        self.texcwd = cwd
        self.crop = opts['crop']
        self.design = opts['design']
        self.app_path = os.path.dirname(__file__)
        self.logger.debug("The executable is in %s" % self.app_path)

        # LaTeX related options
        self.enumerate = ["enumerate", "tabbedenum"]
        self.extra_packages = []
        self.pagedimensions = {'A4': ['21cm', '29.7cm'], 'default': ['21cm', '10cm'], 'custom': ['21cm', '10cm']}
        self.page = 'default'
        self.margins = ['0.5cm', '0.5cm', '0.5cm', '0.5cm']

        # Paths
        if self.inputfile in (None, "None", "none", "null"):
            self.texpath = None
            self.texfile = None
            self.texname = None
            self.texdir = None
            self.pngdir = None
            self.pdfdir = None
            self.tex = None
        else:
            # Opening .tex file
            if self.open_texfile(self.inputfile):
                self.qblocks = self.read_questions(self.tex)

    def open_texfile(self, filepath):
        """ Function that sets the variables for opening the input file """
        if filepath[0] == '~':  # We expand (~/)
            self.logger.debug(filepath)
            self.texpath = os.path.expanduser(filepath)
            self.logger.debug(self.texpath)
        else:
            self.texpath = filepath
        self.logger.info("Loading %s ..." % self.texpath)
        self.texfile = os.path.basename(self.texpath)
        self.logger.debug('Tex file: %s' % self.texfile)
        self.texname = self.texfile[0:-4]
        self.logger.debug('Tex file name: %s' % self.texname)
        self.texdir = os.path.dirname(self.texpath)
        self.texdir = os.path.realpath(self.texdir)
        self.texcwd = self.texdir
        if self.texdir == "":  # If the file has local path format we add ./
            self.texdir = "./"
        self.logger.debug('Tex directory: %s' % self.texdir)
        self.pngdir = self.texdir + '/png'
        self.pdfdir = self.texdir + '/pdf'
        # We check the existance of the file at that path and the extension
        if self.check_file(self.texpath):
            if not self.check_extension(self.texfile, 'tex'):
                self.texpath = None
                return False
        else:
            self.texpath = None
            return False

        # Prepare the tex file to read (tags)
        f = open(self.texpath, 'r')
        self.tex = f.read()
        return True

    def check_file(self, fin, critical=True, warning=False):
        """
        Check if the file exists
        :param fin: input file's path.
        :param critical: forces the program to stop if the file is not found. Default is True.
        :param warning: Raise a warning instead of an error.
        :return: True if the file exists. False if it does not.
        """
        self.logger.debug("Checking %s file ..." % fin)
        if not os.path.exists(fin):
            if critical:
                raise IOError('File %s does not exist.' % fin)
            elif warning:
                self.logger.warning('File %s does not exist.' % fin)
                return False
            else:
                self.logger.error('File %s does not exist.' % fin)
                return False
        else:
            return True

    def check_extension(self, fin, extension):
        """
        Check the extension of file fin.
        :param fin: input file's path.
        :param extension: extension to be checked.
        :return: True if the extension coincides.
        """
        self.logger.debug("Checking %s extension ..." % fin)
        if not fin.endswith(extension):
            self.logger.error("File %s is not a %s file." % (fin, extension))
            return False
        else:
            return True

    def read_questions(self, ifile):
        """
        Reads the already opened questions file. Looks for questions and choices.
        :return: 'question' and 'choices'
        """
        # The questions files should have an specific format:
        # % File_name: T1_c1.1_q1
        # % Title: Pregunta 1
        # Enunciado de la pregunta.
        # \begin{enumerate}
        # \Myitem Respuesta 1.
        # \Myitem Respuesta 2.
        # \Myitem Respuesta 3.
        # \Myitem Respuesta 4. % Correct
        # \end{enumerate}

        # In case is a completely formatted .tex file we look for preambles and ends of the type:
        # % BEGIN PREAMBLE
        # % END PREAMBLE
        # % BEGIN END
        # % END END

        self.logger.info("Searching for questions ...")
        questions_pre = re.findall(r'% BEGIN PREAMBLE.*?% END PREAMBLE\n', ifile, re.DOTALL)
        questions_end = re.findall(r'% BEGIN END(.*?)% END END\n', ifile, re.DOTALL)

        # The questions should be inside these two blocks
        if questions_pre and questions_end:
            questions = re.findall(r'% END PREAMBLE.*?% BEGIN END\n', ifile, re.DOTALL)
        else:
            questions = [ifile]

        enum = "(" + "|".join(map(str, self.enumerate)) + ")"
        if questions:
            question_blocks = re.findall(r'(% File_name: )(.*?)' + enum + r'(.*?)' + enum + r'(\}\n)',
                                         questions[0], re.DOTALL)
            if question_blocks:
                for k, block in enumerate(question_blocks):
                    question_blocks[k] = "".join(map(str, block))
        else:
            self.logger.warning('Bad format for questions or empty file ...')
            return None

        self.logger.info("Number of questions detected: %d" % len(question_blocks))

        qblocks = {}

        for k, block in enumerate(question_blocks):
            self.logger.debug("Block %d" % k)
            if block:
                name = re.findall(r'% File_name: (.*?)\n', block)

                self.logger.debug("File name: %s" % name[0])
                title = re.findall(r'% Title: (.*?)\n', block)
                self.logger.debug("Title: %s" % title[0])
                question = re.findall(title[0] + r'\n(.*?)\\begin\{enumerate\}\n', block, re.DOTALL)
                if not question:
                    question = re.findall(title[0] + r'\n(.*?)\\begin\{tabbedenum\}\{2\}\n', block, re.DOTALL)
                if not question:
                    self.logger.warning('Bad format for questions or empty file ...')
                    return None
                self.logger.debug("Question: %s" % question[0])
                choices = re.findall(r'\\Myitem (.*?)\n', block, re.DOTALL)
                self.logger.debug("Choices:")
                self.logger.debug(choices)
                correct = None
                for j, choice in enumerate(choices):
                    if re.findall(r'% Correct', choice):
                        self.logger.debug("Correct choice is %d." % (j + 1))
                        correct = j
                qblocks[name[0]] = ({'name': name[0], 'title': title[0], 'question': question[0],
                                     'choices': choices, 'correct': correct})

        self.logger.debug(qblocks)
        return qblocks


class Kajut(object):
    def __init__(self, data):
        self.logger = logging.getLogger('gui.Kajut')
        self.d = data

        # Basic configuration for LaTeX
        self.preamble = None
        self.ending = "\\end{document}\n"

    def create_latex(self, qblock):
        if not self.preamble:
            self.set_preamble(self.d.page)
        if not self.d.texdir:
            self.logger.warning("There is no path defined ...")
            # TODO: ask for a path to save files
            exit(-1)
        filename = "%s/tex-%s" % (self.d.texdir, qblock['name'])
        filepath = filename + '.tex'
        self.logger.debug("Writing latex file for question %s in %s ..." % (qblock['name'], filepath))

        f = open(filepath, 'w')
        f.write(self.preamble)
        # % File_name: T1_c1.1_q1
        # % Title: Pregunta 1
        f.write("% File_name: " + qblock['name'] + "\n")
        f.write("% Title: " + qblock['name'] + "\n")
        f.write(qblock['question'])
        if self.d.design == 1:
            f.write("\\\\\n\\newline\n\\begin{tabbedenum}{2}\n")
        elif self.d.design == 0:
            f.write("\\begin{enumerate}\n")
        for k, choice in enumerate(qblock['choices']):
            f.write("\\Myitem " + choice + "\n")
        if self.d.design == 1:
            f.write("\\end{tabbedenum}\n")
        elif self.d.design == 0:
            f.write("\\end{enumerate}\n")
        f.write(self.ending)
        f.close()
        self.logger.debug("LaTeX file created!")
        return filename

    def create_png(self, filename):
        filename = os.path.realpath(filename)
        # Compile latex file
        self.logger.debug("Using latex file  %s ..." % (filename + '.tex'))
        filedir = os.path.realpath(self.d.texdir)
        # Check for the necessary paths
        if not os.path.exists(self.d.pngdir):
            try:
                os.mkdir(self.d.pngdir)
            except:
                raise IOError('Path %s does not exist.' % self.d.pngdir)
        if not os.path.exists(self.d.pdfdir):
            try:
                os.mkdir(self.d.pdfdir)
            except:
                raise IOError('Path %s does not exist.' % self.d.pdfdir)

        # Compile latex file
        self.logger.debug("Compiling LaTeX ...")
        os.chdir(self.d.texdir)
        p = os.popen('pdflatex -output-directory=%s -interaction=nonstopmode -file-line-error  %s '
                     '| grep ".*:[0-9]*:.*"' % (filedir, (filename + '.tex')))
        p.close()
        self.logger.debug("Done!")
        if self.d.crop:
            p = os.popen('pdfcrop --noverbose %s.pdf | grep nothing' % filename)
            p.close()
            p = os.popen('mv %s-crop.pdf %s.pdf' % (filename, filename))
            p.close()

        self.logger.debug("Removing auxiliary files ...")
        p = os.popen('rm %s.aux %s.log' % (filename, filename))
        p.close()
        self.logger.debug("Done!")

        self.logger.info("Creating png file, with density %d ..." % self.d.density)
        p = os.popen('convert -density %d %s.pdf %s.png' % (self.d.density, filename, filename))
        p.close()
        self.logger.info("Done!")

        p = os.popen('mv %s.png %s' % (filename, self.d.pngdir))
        png = p.close()

        if png:
            p = os.popen('mv %s/*.png %s' % (self.d.texdir, self.d.pngdir))
            p.close()

        p = os.popen('mv %s.pdf %s' % (filename, self.d.pdfdir))
        p.close()
        self.logger.debug("All jobs finished.")
        return True, png

    def geometry(self, pagestyle='default'):
        (width, height) = self.d.pagedimensions[pagestyle]
        self.logger.debug("Paper dimensions: (W, H) = (%s, %s)." % (width, height))
        margins = "".join(map(str, map(add, [',left=', ',right=', ',top=', ',bottom='], self.d.margins)))
        self.logger.debug("Text margins:  %s." % margins)
        geom = "\\usepackage[paperwidth=" + width + ",paperheight=" + height + margins + "]{geometry}\n"
        return geom

    def set_preamble(self, pagestyle='default', external=None):
        self.logger.debug("Generating LaTeX preamble...")
        if not external:
            geom = self.geometry(pagestyle)
            self.preamble = "\\documentclass[12pt]{article}\n" \
                            "\\usepackage[english, catalan]{babel}\n" \
                            "\\usepackage[utf8]{inputenc}\n" \
                            "\\usepackage{amsmath, amssymb, amsthm}\n" \
                            "\\usepackage{color}\n" \
                            "\\usepackage{graphicx}\n"
            self.preamble = self.preamble + geom
            self.preamble = self.preamble + "" \
                                            "\\usepackage{adjustbox}\n" \
                                            "\\setlength{\parindent}{0mm}\n" \
                                            "\\usepackage{paralist}\n" \
                                            "\\usepackage{tabto}\n" \
                                            "\\usepackage{intcalc}\n" \
                                            "\\usepackage{enumerate, letltxmacro}\n"
            for package in self.d.extra_packages:
                self.preamble += "\\usepackage{" + package + "}\n"
            self.preamble = self.preamble + "" \
                                            "\\graphicspath{{" + self.d.app_path + "/}}\n" \
                                            "\\newcommand*{\Myitem}{ %\n" \
                                            "\\item[{\\adjustbox{valign = c}{\includegraphics[width = " \
                                            "1cm]{art/image\intcalcMod{\\value{enumi}}{4}}}}]\stepcounter{enumi} %\n" \
                                            "}\n" \
                                            "\\LetLtxMacro\itemold\Myitem\n" \
                                            "\\renewcommand{\Myitem}{\itemindent1cm\itemold}\n" \
                                            "\\newenvironment{tabbedenum}[1]\n" \
                                            "{\NumTabs{#1}\inparaenum\let\latexitem\Myitem\n" \
                                            "\\def\Myitem{\def\Myitem{\\tab\latexitem}\latexitem}}\n" \
                                            "{\endinparaenum}\n" \
                                            "\\begin{document}\n" \
                                            "\\pagestyle{empty}\n" \
                                            "\\noindent\n"
        else:
            self.logger.debug("Loading preamble from %s..." % external)
            with open(external, "r") as f:
                content = f.read()
                preamble = re.findall(r'% BEGIN PREAMBLE\n(.*?)% END PREAMBLE\n', content, re.DOTALL)
            if preamble:
                self.preamble = preamble[0]
            else:
                self.logger.error("Bad format of the latex document. I could not detect any clear preamble.\n"
                                  "Use:\n"
                                  "% BEGIN PREAMBLE\n"
                                  "[preamble]\n"
                                  "% END PREAMBLE\n")
                self.logger.warning("Using default preamble...")
                self.set_preamble(self.d.page)
        self.logger.debug("Done!")


class MainGui:
    def __init__(self, data, kajut=None):
        if kajut is None:
            self.kj = Kajut(data)
        else:
            self.kj = kajut
        self.d = data
        self.logger = logging.getLogger('gui.MainGui')
        scriptpath = os.path.realpath(__file__)
        scriptdir = os.path.dirname(scriptpath)

        self.builder = Gtk.Builder()
        self.builder.add_from_file("%s/v0.1.1.glade" % scriptdir)

        self.window = self.builder.get_object("window1")
        self.window.connect("delete-event", Gtk.main_quit)

        self.densityspin = self.builder.get_object("density")
        self.densityspin.set_value(self.d.density)

        self.treeview = self.builder.get_object("questions")
        self.namelist = self.builder.get_object("question_store")
        self.im_add = self.builder.get_object("add")
        self.im_remove = self.builder.get_object("remove")
        self.im_edit = self.builder.get_object("edit")

        self.open = self.builder.get_object("inputfile")

        if self.d.texpath is not None:
            self.open.set_text(self.d.texpath)

        signals = {"on_exit_clicked": self.on_exit_clicked,
                   "gtk_main_quit": Gtk.main_quit,
                   "on_density_value_changed": self.on_density_value_changed,
                   "on_entry_activate": self.on_entry_activate,
                   "on_question_selected": self.on_selected,
                   "on_add_clicked": self.on_add_clicked,
                   "on_remove_clicked": self.on_remove_clicked,
                   "on_edit_clicked": self.on_edit_clicked,
                   "on_generate_clicked": self.on_generate_clicked,
                   "on_generate_all_clicked": self.on_generate_all_clicked,
                   "on_open_clicked": self.on_open_clicked,
                   "on_crop_toggled": self.on_crop_toggled,
                   "on_toggled": self.on_design_toggled,
                   "on_dimension_toggled": self.on_dimensions_toggled,
                   "on_margins_set_clicked": self.on_margins_set_clicked,
                   "on_inputfile_activate": self.on_inputfile_activate,
                   "on_inputfile_drag_data_received": self.on_drag_data}

        dnd_list = [Gtk.TargetEntry.new("text/uri-list", 0, TARGET_TYPE_URI_LIST)]

        self.window.drag_dest_set(Gtk.DestDefaults.MOTION |
                                  Gtk.DestDefaults.HIGHLIGHT | Gtk.DestDefaults.DROP,
                                  dnd_list, Gdk.DragAction.COPY)
        self.builder.connect_signals(signals)
        self.pbar = self.builder.get_object("progressbar1")
        self.pngbutton = self.builder.get_object("generate")
        self.cropbutton = self.builder.get_object("crop")
        self.cropbutton.set_active(self.d.crop)
        designbutton = self.builder.get_object("design" + ("%d" % data.design))
        designbutton.set_active(True)
        papersize = self.builder.get_object("dimension2")
        papersize.set_active(True)
        for k in xrange(2):
            size = self.builder.get_object("size" + str(k))
            size.set_text(self.d.pagedimensions['custom'][k])
        self.margins = []
        margins = ('lm', 'rm', 'tm', 'bm')
        for k, margin in enumerate(margins):
            self.margins.append(self.builder.get_object(margin))
            self.margins[k].set_text(self.d.margins[k])

        self.allpngbutton = self.builder.get_object("generate_all")
        self.png_image = self.builder.get_object("png_image")
        self.png_image.set_from_icon_name('gtk-missing-image', Gtk.IconSize.DIALOG)
        color = Gdk.Color(red=65535, green=65535, blue=65535)
        self.png_image.modify_bg(Gtk.StateFlags.NORMAL, color)
        self.timeout_id = None
        self.selected_name = None
        self.all = False

        # We create the listbox store for the questions
        if self.d.qblocks:
            for k, key in enumerate(self.d.qblocks.keys()):
                self.namelist.append([k, key])
            self.treeview.set_cursor(0)
            model, iteration = self.treeview.get_selection().get_selected()
            self.selected_name = model[iteration][1]
            self.logger.debug("Default selection: %s" % self.selected_name)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Name", renderer, text=1)
        self.treeview.append_column(column)
        column.set_sort_column_id(1)
        # Sort the quetions
        sorted_model = self.builder.get_object("question_sort")
        sorted_model.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        self.treeview.set_cursor(0)
        self.window.show_all()

    def on_exit_clicked(self, event):
        self.logger.debug('Button %s pressed' % event)
        Gtk.main_quit()

    def on_open_clicked(self, event):
        self.logger.debug('Button %s pressed' % event)
        dialog = Gtk.FileChooserDialog("Please choose a file", self.window, Gtk.FileChooserAction.OPEN,
                                       (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        dialog.set_current_folder(self.d.texcwd)
        self.add_filters(dialog)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.logger.debug("Open clicked")
            self.logger.debug("File selected: " + dialog.get_filename())
            self.update_liststore(dialog.get_filename())
        elif response == Gtk.ResponseType.CANCEL:
            self.logger.debug("Cancel clicked")

        self.logger.debug(self.d.qblocks)

        dialog.destroy()

    def on_inputfile_activate(self, event):
        self.logger.debug('Text on %s modified' % event)
        filename = event.get_text()
        self.update_liststore(filename)

    def on_drag_data(self, event, context, x, y, selection, target_type, timestamp):
        self.logger.debug('Something dropped on %s' % event)
        self.logger.debug('Target type: %s' % target_type)
        if target_type == TARGET_TYPE_URI_LIST:
            self.logger.debug(selection.get_data())
            uri = selection.get_data().strip('\r\n\x00')
            uri_splitted = uri.split()  # we may have more than one file dropped
            for uri in uri_splitted:
                path = self.get_file_path_from_dnd_dropped_uri(uri)
                if os.path.isfile(path):  # is it file?
                    self.logger.debug("Dropped file name: %s" % path)
                    # If the drag is done on the input file
                    self.update_liststore(path)

    def update_liststore(self, path):
        if self.d.open_texfile(path):
            new_qblocks = self.d.read_questions(self.d.tex)
            if new_qblocks:
                self.d.qblocks.update(new_qblocks)
                # Add the new blocks to the listbox (store, etc.)
                self.namelist.clear()
                for k, key in enumerate(self.d.qblocks):
                    self.namelist.append([k, key])
                # Sort the quetions
                sorted_model = self.builder.get_object("question_sort")
                sorted_model.set_sort_column_id(1, Gtk.SortType.ASCENDING)
                self.treeview.set_cursor(0)
                model, iteration = self.treeview.get_selection().get_selected()
                self.selected_name = model[iteration][1]
                self.logger.debug("Default selection: %s" % self.selected_name)

    @staticmethod
    def get_file_path_from_dnd_dropped_uri(uri):
        # get the path to file
        path = ""
        if uri.startswith('file:\\\\\\'):  # windows
            path = uri[8:]  # 8 is len('file:///')
        elif uri.startswith('file://'):  # nautilus, rox
            path = uri[7:]  # 7 is len('file://')
        elif uri.startswith('file:'):  # xffm
            path = uri[5:]  # 5 is len('file:')

        path = urllib.url2pathname(path)  # escape special chars
        path = path.strip('\r\n\x00')  # remove \r\n and NULL
        return path

    @staticmethod
    def find_widget_down(source, target):
        """ Method to find a successor child of a given source widget"""
        for child in source.get_children():
            if child.get_name() == target:
                logging.debug("Target child found.")
                return child
            else:
                try:
                    targetchild = MainGui.find_widget_down(child, target)
                    if targetchild:
                        return targetchild
                except AttributeError:
                    logging.debug("Target child not found in this branch.")

    @staticmethod
    def find_widget_up(source, target):
        """ Method for finding an ancestor widget from a source widget."""
        parent = source
        while parent.get_name() != target:
            parent = parent.get_parent()
            try:
                parent.get_name()
            except AttributeError:
                logging.warning("Target widget %s not in this branch." % target)
                return None
        return parent

    def on_density_value_changed(self, event):
        self.logger.debug('Value at %s modified' % event)
        self.d.density = self.densityspin.get_value()
        self.logger.debug('Density for PNG conversion: %d' % self.d.density)

    def on_crop_toggled(self, event):
        self.logger.debug('RadioButton %s toggled.' % event)
        self.d.crop = not self.d.crop

    def on_design_toggled(self, button):
        name = button.get_name()
        self.logger.debug('RadioButton %s with name %s toggled.' % (button, name))
        design = int(name[len("design"):])
        self.logger.debug("Design is %d" % design)
        if button.get_active():
            self.d.design = design
        else:
            pass

    def on_dimensions_toggled(self, button):
        name = button.get_name()
        self.logger.debug('RadioButton %s with name %s toggled.' % (button, name))
        if button.get_active():
            self.logger.debug("Selected page style is %s" % name)
            self.d.page = name
            self.kj.set_preamble(self.d.page)
        else:
            pass

    def on_entry_activate(self, entry):
        self.logger.debug('Text on %s modified' % entry)
        name = entry.get_name()
        self.logger.debug('Entry widget name: %s' % name)
        if re.match("margin", name):
            margin = int(name[len("margin"):])
            self.d.margins[margin] = entry.get_text()
        elif re.match("size", name):
            size = int(name[len("size"):])
            self.d.pagedimensions['custom'][size] = entry.get_text()
        self.kj.set_preamble(self.d.page)

    def on_margins_set_clicked(self, event):
        """ Set margins."""
        self.logger.debug('Button %s pressed' % event)
        for k, entry in enumerate(self.margins):
            self.d.margins[k] = entry.get_text()
        self.kj.set_preamble(self.d.page)

    def on_selected(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter is None:
            return 1
        self.logger.debug('Element %s selected in % s' % (treeiter, model))
        # Get the name of the question
        name = model[treeiter][1]
        # Store the selected element, for editing or removing
        self.selected_name = name
        self.logger.debug('Selected question: %s' % name)
        filename = self.d.pngdir + '/tex-' + name + '.png'
        filename2 = self.d.pngdir + '/tex-' + name + '-0.png'
        # Check whether a PNG file exists for the selected question
        if self.d.check_file(filename, critical=False, warning=True):
            # Display the PNG in the canvas area
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(filename, 880, -1, True)
            self.png_image.set_from_pixbuf(pixbuf)
        elif self.d.check_file(filename2, critical=False, warning=True):  # Check if the png is in multiple files
            self.logger.warning("The file needs more than one page. Multiple PNG files created.")
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(filename2, 880, -1, True)
            self.png_image.set_from_pixbuf(pixbuf)
        else:
            self.png_image.set_from_icon_name('gtk-missing-image', Gtk.IconSize.DIALOG)

    def on_add_clicked(self, event):
        """ Add a new row to the list box."""
        self.logger.debug('Button %s pressed' % event)
        # Open the dialog for creating a new question
        dialog = EditDialog(self.d, parent=self.window)
        dialog.run()
        if dialog.accept and dialog.new:
            self.selected_name = dialog.name
            self.on_generate_clicked(None)
            newfile = self.d.texdir + '/tex-' + self.selected_name + '.tex'
            self.update_liststore(newfile)
        dialog.hide()

        # Modify the tree_store if the dialog is accepted

        return None

    def on_remove_clicked(self, event):
        """ Remove the selected question."""
        self.logger.debug('Button %s pressed' % event)
        if len(self.d.qblocks) > 0:
            self.d.qblocks.pop(self.selected_name)
            self.namelist.clear()
            if len(self.d.qblocks) > 0:
                for k, key in enumerate(self.d.qblocks):
                    self.namelist.append([k, key])
                # Sort the quetions
                sorted_model = self.builder.get_object("question_sort")
                sorted_model.set_sort_column_id(1, Gtk.SortType.ASCENDING)
                self.treeview.set_cursor(0)
                model, iteration = self.treeview.get_selection().get_selected()
                self.selected_name = model[iteration][1]
                self.logger.debug("Default selection: %s" % self.selected_name)
        if len(self.d.qblocks) == 0:
            self.selected_name = None

    def on_edit_clicked(self, event):
        """ Edit the selected question """
        self.logger.debug('Button %s pressed' % event)
        # Open the edition dialog
        if self.selected_name:
            dialog = EditDialog(self.d, selection=self.selected_name, parent=self.window)
            dialog.run()
            if dialog.accept and dialog.new:
                self.selected_name = dialog.name
                self.on_generate_clicked(None)
                newfile = self.d.texdir + '/tex-' + self.selected_name + '.tex'
                self.update_liststore(newfile)
            dialog.hide()

    def on_generate_clicked(self, event):
        self.logger.debug('Button %s pressed' % event)
        if self.d.texpath:
            self.timeout_id = GObject.timeout_add(50, self.on_timeout, True)
            self.thread = threading.Thread(target=self.outside_task)
            self.thread.start()
            self.watch = GObject.timeout_add(500, self.watch_thread, True)
        else:
            self.logger.warning("There is no TEX file loaded.")
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.ERROR, Gtk.ButtonsType.CANCEL,
                                       "Load or create a TEX file first.")
            dialog.run()
            dialog.destroy()

    def on_generate_all_clicked(self, event):
        self.all = True
        self.logger.info("Generating PNG images for all questions...")
        self.on_generate_clicked(event)

    def on_timeout(self, user_data):
        self.pbar.pulse()
        return user_data

    def watch_thread(self, user_data):
        if not self.thread.isAlive():
            self.thread.join()
            return False
        else:
            return user_data

    def outside_task(self):
        if self.all:
            for name in self.d.qblocks.keys():
                filename = self.kj.create_latex(self.d.qblocks[name])
                self.kj.create_png(filename)
            self.all = False
        else:
            filename = self.kj.create_latex(self.d.qblocks[self.selected_name])
            self.png_image.set_from_icon_name('gtk-missing-image', Gtk.IconSize.DIALOG)
            success, png = self.kj.create_png(filename)
            if success:
                if not png:
                    pngfile = self.d.pngdir + '/tex-' + self.selected_name + '.png'
                else:
                    pngfile = self.d.pngdir + '/tex-' + self.selected_name + '-0.png'
                # Check whether a PNG file exists for the selected question
                if self.d.check_file(pngfile, critical=False, warning=True):
                    # Display the PNG in the canvas area
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(pngfile, 880, -1, True)
                    self.png_image.set_from_pixbuf(pixbuf)
                    if png:
                        self.logger.warning("The file needs more than one page. Multiple PNG files created.")
        self.logger.info("Done.")
        GObject.source_remove(self.timeout_id)
        self.pbar.set_fraction(0.0)

    @staticmethod
    def add_filters(dialog):
        filter_text = Gtk.FileFilter()
        filter_text.set_name("TeX Files")
        filter_text.add_mime_type("text/x-tex")
        dialog.add_filter(filter_text)

        filter_any = Gtk.FileFilter()
        filter_any.set_name("Any files")
        filter_any.add_pattern("*")
        dialog.add_filter(filter_any)


# noinspection PyAttributeOutsideInit
class EditDialog(Gtk.Dialog):
    __gtype_name__ = 'EditDialog'

    def __new__(self, data, selection=None, parent=None):

        app_path = os.path.dirname(__file__)
        data.app_path = app_path
        try:
            builder = Gtk.Builder()
            builder.add_from_file(os.path.join(app_path, "edit_dialog.glade"))
        except:
            print "Failed to load XML GUI file edit_dialog.glade"
            return -1
        new_object = builder.get_object('edit_dialog')
        new_object.finish_initializing(builder, data, selection, parent)
        return new_object

    def finish_initializing(self, builder, data, selection=None, parent=None):

        self.logger = logging.getLogger('gui.EditDialog')
        self._builder = builder
        self.qblocks = data.qblocks

        signals = {"on_cancel": self._on_cancel,
                   "on_accept": self._on_accept}

        builder.connect_signals(signals)
        self.connect("delete-event", self._on_cancel)

        # Obtain the entry and text objects
        self.entry = self._builder.get_object("entry")
        self.text_sentence = self._builder.get_object("textsentence")
        self.sentence = self._builder.get_object("sentence")
        self.choices = []
        for k in xrange(4):
            self.choices.append(self._builder.get_object(("choice%d" % (k + 1))))

        # Change icons
        for k in xrange(4):
            gtkimage = self._builder.get_object(("icon%d" % (k + 1)))
            icon = data.app_path + ('/art/icon%d.png' % k)
            self.logger.debug("Setting icon %s in %s" % (icon, gtkimage))
            gtkimage.set_from_file(icon)

        # If the dialog is for editing, modify the text in the buffers
        if selection:
            self.entry.set_text(selection)
            self.sentence.set_text(data.qblocks[selection]['question'])
            for k, choice in enumerate(self.choices):
                choice.set_text(data.qblocks[selection]['choices'][k])

        # Link to the parent window
        if parent:
            self.logger.debug("Linking the dialog to the parent.")
            self.set_transient_for(parent)

        self.accept = False
        self.new = False
        self.name = selection

    def _on_accept(self, event):
        # If the dialog is for editing, modify the text in the buffers
        name = self.entry.get_text()
        self.name = name
        # Check if the name is new
        if name not in self.qblocks:
            self.new = True
        if name not in (None, ""):
            sentence = self.get_text(self.sentence)
            choices = []
            for k, choice in enumerate(self.choices):
                choices.append(self.get_text(choice))
            self.qblocks[name] = {'question': sentence, 'name': name, 'choices': choices}
            self.hide()
            self.accept = True
        else:
            self.logger.debug("You must provide a name.")

    def _on_cancel(self, event, *args, **kwargs):
        self.hide()
        self.accept = False

    @staticmethod
    def get_text(textbuffer):
        start_iter = textbuffer.get_start_iter()
        end_iter = textbuffer.get_end_iter()
        text = textbuffer.get_text(start_iter, end_iter, True)
        return text

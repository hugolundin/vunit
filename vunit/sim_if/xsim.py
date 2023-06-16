# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2014-2022, Lars Asplund lars.anders.asplund@gmail.com

"""
Interface for Vivado XSim simulator
"""

from __future__ import print_function
import copy
import logging
import os
from os.path import join
from pathlib import Path
import re
import shutil
import sys
import threading
from shutil import copyfile
from ..ostools import Process
from . import SimulatorInterface, StringOption, BooleanOption, ListOfStringOption
from ..exceptions import CompileError
LOGGER = logging.getLogger(__name__)


class XSimInterface(SimulatorInterface):
    """
    Interface for Vivado xsim simulator
    """

    name = "xsim"
    executable = os.environ.get("XSIM", "xsim")

    package_users_depend_on_bodies = True
    supports_gui_flag = True

    sim_options = [
        StringOption("xsim.timescale"),
        BooleanOption("xsim.enable_glbl"),
        ListOfStringOption("xsim.xelab_flags"),
        StringOption("xsim.view")
    ]

    @staticmethod
    def add_arguments(parser):
        """
        Add command line arguments
        """
        group = parser.add_argument_group("xsim", description="Xsim specific flags")
        group.add_argument(
            "--xsim-vcd-path",
            default="",
            help="VCD waveform output path.",
        )
        group.add_argument("--xsim-vcd-enable", action="store_true", help="Enable VCD waveform generation.")
        group.add_argument(
            "--xsim-xelab-limit", action="store_true", help="Limit the xelab current processes to 1 thread."
        )
        group.add_argument(
            "--xsim-view",
            default="",
            help="Path to a wave configuration file that should be loaded in Vivado on GUI simulation.",
        )            


    @classmethod
    def from_args(cls, args, output_path, **kwargs):
        """
        Create instance from args namespace
        """
        prefix = cls.find_prefix()

        return cls(
            prefix=prefix,
            output_path=output_path,
            gui=args.gui,
            vcd_path=args.xsim_vcd_path,
            vcd_enable=args.xsim_vcd_enable,
            xelab_limit=args.xsim_xelab_limit,
            view=args.xsim_view
        )

    @classmethod
    def find_prefix_from_path(cls):
        """
        Find first valid xsim toolchain prefix
        """
        return cls.find_toolchain(["xsim"])

    def _format_command_for_os(cls, cmd):
        """
        xsim for windows requires some arguments to be in quotes, which
        have been added in libraries_command. However, the check_output
        function will escape these when calling xsim (as it should),
        meaning that xsim doesn't understand its input arguments.
        The workaround is to create one string here and use that one for windows.
        """
        if (sys.platform == "win32" or os.name == "os2"):
            cmd = " ".join(cmd)
        return cmd

    def check_tool(self, tool_name):
        """
        Checks to see if a tool exists, with extensions both gor Windows and Linux
        """
        if os.path.exists(os.path.join(self._prefix, tool_name + ".bat")):
            return tool_name + ".bat"
        if os.path.exists(os.path.join(self._prefix, tool_name)):
            return tool_name
        raise Exception(f"Cannot find {tool_name}")

    def __init__(self, prefix, output_path, gui=False, vcd_path="", vcd_enable=False, xelab_limit=False, view=""):
        super().__init__(output_path, gui)
        self._prefix = prefix
        self._libraries = {}
        self._xvlog = self.check_tool("xvlog")
        self._xvhdl = self.check_tool("xvhdl")
        self._xelab = self.check_tool("xelab")
        self._vivado = self.check_tool("vivado")
        self._xsim = self.check_tool("xsim")
        self._xsim_initfile = os.path.join(self._prefix, "..", "data", "xsim", "xsim.ini")
        self._vcd_path = vcd_path
        self._vcd_enable = vcd_enable
        self._xelab_limit = xelab_limit
        self._lock = threading.Lock()
        self._view = view

    def setup_library_mapping(self, project):
        """
        Setup library mapping
        """

        for library in project.get_libraries():
            self._libraries[library.name] = library.directory


        # For Windows, if a library is added with -L <libname>=<libpath>, xsim actually puts (and looks for)
        # the library in <libname>=<libpath>/xsim.dir/work
        #
        # For precompiled libraries, we therefore cannot add them with a path, because xsim will still
        # look in the xsim.dir/work folder, which doesn't exist in the precompiled sources.
        #
        # The workaround is to find any user added precompiled libraries, and remove the path to them,
        # which will later mean that the library will only be added as -L <libname>, i.e. without the path.
        if (sys.platform == "win32" or os.name == "os2"):
            lib_pattern = re.compile(r"(?P<name>\w+)\s*=\s*(?P<path>.+)")
            std_lib_init_file = []
            # Search the xsim_ip.ini file to see if user-added libraries are precompiled
            with open(
                self._xsim_initfile, "r"
            ) as ips:
                for line in ips:
                    m = lib_pattern.match(line)
                    if m:
                        # We have found a precompiled version
                        std_lib_init_file.append(m.group("name"))

            new_sel_library = copy.deepcopy(self._libraries)

            # Remove the path for any precompiled libraries
            for library_name, _ in self._libraries.items():
                if library_name in std_lib_init_file:
                    new_sel_library[library_name] = None

            self._libraries = copy.deepcopy(new_sel_library)

    def compile_source_file_command(self, source_file):
        """
        Returns the command to compile a single source_file
        """
        if source_file.file_type == "vhdl":
            return self.compile_vhdl_file_command(source_file)
        if source_file.file_type == "verilog":
            cmd = [join(self._prefix, self._xvlog), source_file.name]
            return self.compile_verilog_file_command(source_file, cmd)
        if source_file.file_type == "systemverilog":
            cmd = [join(self._prefix, self._xvlog), "--sv", source_file.name]
            return self.compile_verilog_file_command(source_file, cmd)

        LOGGER.error("Unknown file type: %s", source_file.file_type)
        raise CompileError

    def libraries_command(self):
        """
        Adds libraries on the command line
        """
        cmd = []
        for library_name, library_path in self._libraries.items():
            if library_path:
                if (sys.platform == "win32" or os.name == "os2"):
                    # xsim for Windows requires:
                    #     1) extra quotes around the library path argument
                    #     2) the library to be in  <something>/xsim.dir/work
                    cmd += ["-L", f'"{library_name}={os.path.join(library_path, "xsim.dir", "work")}"']
                else:
                    cmd += ["-L", f"{library_name}={library_path}"]
            else:
                cmd += ["-L", library_name]
        return cmd

    @staticmethod
    def work_library_argument(source_file):
        if (sys.platform == "win32" or os.name == "os2"):
            # xsim for Windows requires:
            #     1) extra quotes around the library path argument
            #     2) the library to be in  <something>/xsim.dir/work
            return ["-work", f'"{source_file.library.name}={os.path.join(source_file.library.directory, "xsim.dir", "work")}"']
        else:
            return ["-work", f"{source_file.library.name}={source_file.library.directory}"]

    def compile_vhdl_file_command(self, source_file):
        """
        Returns the command to compile a vhdl file
        """
        cmd = [join(self._prefix, self._xvhdl), source_file.name, "-2008"]
        cmd += self.work_library_argument(source_file)
        cmd += self.libraries_command()
        return self._format_command_for_os(cmd)

    def compile_verilog_file_command(self, source_file, cmd):
        """
        Returns the command to compile a vhdl file
        """
        cmd += self.work_library_argument(source_file)
        cmd += self.libraries_command()
        for include_dir in source_file.include_dirs:
            cmd += ["--include", f"{include_dir}"]
        for define_name, define_val in source_file.defines.items():
            cmd += ["--define", f"{define_name}={define_val}"]
        return self._format_command_for_os(cmd)

    @staticmethod
    def _xelab_extra_args(config):
        """
        Determine xelab_extra_args
        """
        xelab_extra_args = []
        xelab_extra_args = config.sim_options.get("xsim.xelab_flags", xelab_extra_args)

        return xelab_extra_args

    def simulate(self, output_path, test_suite_name, config, elaborate_only):
        """
        Simulate with entity as top level using generics
        """
        runpy_dir = os.path.abspath(str(Path(output_path)) + "../../../../")

        if self._vcd_path == "":
            vcd_path = os.path.abspath(str(Path(output_path))) + "/wave.vcd"
        else:
            if os.path.isabs(self._vcd_path):
                vcd_path = self._vcd_path
            else:
                vcd_path = os.path.abspath(str(Path(runpy_dir))) + "/" + self._vcd_path

        if self._view:
            if os.path.isabs(self._view):
                view = self._view
            else:
                view = os.path.abspath(str(Path(runpy_dir))) + "/" + self._view
        else:
            view = None

        cmd = [join(self._prefix, self._xelab)]
        cmd += ["-debug", "typical"]
        cmd += self.libraries_command()

        cmd += ["--notimingchecks"]
        cmd += ["--nospecify"]
        cmd += ["--nolog"]
        cmd += ["--relax"]
        cmd += ["--incr"]
        cmd += ["--sdfnowarn"]
        cmd += ["--stats"]
        cmd += ["--O0"]

        snapshot = "vunit_test"
        cmd += ["--snapshot", snapshot]

        enable_glbl = config.sim_options.get(self.name + ".enable_glbl", None)

        cmd += [f"{config.library_name}.{config.entity_name}"]

        if enable_glbl:
            cmd += [f"{config.library_name}.glbl"]

        timescale = config.sim_options.get(self.name + ".timescale", None)
        if timescale:
            cmd += ["-timescale", timescale]
        dirname = os.path.dirname(self._libraries[config.library_name])
        shutil.copytree(dirname, os.path.join(output_path, os.path.basename(dirname)))
        for generic_name, generic_value in config.generics.items():
            if (sys.platform == "win32" or os.name == "os2"):
                # xsim for windows require extra quotation around this argument
                cmd += ["--generic_top", f'"{generic_name}={generic_value}"']
            else:
                cmd += ["--generic_top", f"{generic_name}={generic_value}"]
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        cmd += self._xelab_extra_args(config)

        status = True
        try:
            resources = config.get_resources()
            for resource in resources:
                file_name = os.path.basename(resource)
                copyfile(resource, output_path + "/" + file_name)

            cmd = self._format_command_for_os(cmd)

            if self._xelab_limit is True:
                with self._lock:
                    proc = Process(cmd, cwd=output_path)
                    proc.consume_output()
            else:
                proc = Process(cmd, cwd=output_path)
                proc.consume_output()

        except Process.NonZeroExitCode:
            status = False

        try:
            # Execute XSIM
            if not elaborate_only:
                tcl_file = os.path.join(output_path, "xsim_startup.tcl")

                # Gui support
                if self._gui:
                    # XSIM binary
                    vivado_cmd = [join(self._prefix, self._xsim)]
                    # Snapshot
                    vivado_cmd += [snapshot]
                    # Mode GUI
                    vivado_cmd += ["--gui"]
                    # Include tcl
                    vivado_cmd += ['--tclbatch', str(Path(tcl_file).as_posix())]
                # Command line
                else:
                    # XSIM binary
                    vivado_cmd = [join(self._prefix, self._xsim)]
                    # Snapshot
                    vivado_cmd += [snapshot]
                    # Include tcl
                    vivado_cmd += ['--tclbatch', str(Path(tcl_file).as_posix())]

                if view:
                    vivado_cmd += ['--view', str(Path(view).as_posix())]

                with open(tcl_file, "w+") as xsim_startup_file:
                    if os.path.exists(vcd_path):
                        os.remove(vcd_path)

                    if self._gui:
                        if self._vcd_enable:
                            xsim_startup_file.write(f"open_vcd {vcd_path}\n")
                            xsim_startup_file.write("log_vcd *\n")
                    else:
                        if self._vcd_enable:
                            xsim_startup_file.write(f"open_vcd {vcd_path}\n")
                            xsim_startup_file.write("log_vcd *\n")
                        xsim_startup_file.write("run all\n")
                        xsim_startup_file.write("quit\n")

                print(" ".join(vivado_cmd))

                vivado_cmd = self._format_command_for_os(vivado_cmd)

                proc = Process(vivado_cmd, cwd=output_path)
                proc.consume_output()

        except Process.NonZeroExitCode:
            status = False
        return status

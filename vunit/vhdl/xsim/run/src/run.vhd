-- Run package provides test runner functionality to VHDL 2002+ testbenches
--
-- This Source Code Form is subject to the terms of the Mozilla Public
-- License, v. 2.0. If a copy of the MPL was not distributed with this file,
-- You can obtain one at http://mozilla.org/MPL/2.0/.
--
-- Copyright (c) 2014-2022, Lars Asplund lars.anders.asplund@gmail.com

use work.dictionary.all;
use work.core_pkg;

package body run_pkg is

  impure function enabled_test_cases (
    constant runner_cfg : string)
    return string is
  begin
    return get(runner_cfg, "enabled_test_cases");
  end;

  impure function enabled_test_cases_size (
    constant runner_cfg : string)
    return integer is
  begin
    return get(runner_cfg, "enabled_test_cases")'length;
  end;

  impure function run (
    constant name : string)
    return boolean is
    variable aux : line;
  begin

    if (current_test'length /= name'length) then
      return false;
    end if;
    if ( string(current_test) /= name ) then
      return false;
    end if;

    core_pkg.test_start(name);

    return true;
  end;

  procedure test_runner_setup (
    signal runner : inout runner_sync_t;
    constant runner_cfg : in string := runner_cfg_default) is
    variable current_test_length : integer := 0;
    variable pepe : line;
  begin
      core_pkg.setup(output_path(runner_cfg) & "vunit_results");

      write(current_test, enabled_test_cases(runner_cfg));
  end test_runner_setup;

  procedure test_runner_cleanup (
    signal runner: inout runner_sync_t;
    external_failure : boolean := false;
    allow_disabled_errors : boolean := false;
    allow_disabled_failures : boolean := false;
    fail_on_warning : boolean := false) is
  begin
    runner(runner_exit_status_idx) <= runner_exit_without_errors;

      core_pkg.test_suite_done;

      core_pkg.stop(0);
  end procedure test_runner_cleanup;

  impure function output_path (
    constant runner_cfg : string)
    return string is
  begin
    return get(runner_cfg, "output path");
  end;

end package body run_pkg;

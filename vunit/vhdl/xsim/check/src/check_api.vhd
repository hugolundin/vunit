-- This file contains the API for the check package. The API is
-- common to all implementations of the check functionality (VHDL 2002+ and VHDL 1993)
--
-- This Source Code Form is subject to the terms of the Mozilla Public
-- License, v. 2.0. If a copy of the MPL was not distributed with this file,
-- You can obtain one at http://mozilla.org/MPL/2.0/.
--
-- Copyright (c) 2014-2022, Lars Asplund lars.anders.asplund@gmail.com

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.textio.all;

package check_pkg is

  function to_char (
    constant bit : std_logic)
    return character;

  function to_string (
    constant data : std_logic)
    return string;

  function to_string (
    constant data : boolean)
    return string;

  function to_string (
    constant data : integer)
    return string;

  function to_string (
    constant data : string)
    return string;

  function to_string (
    constant data : time)
    return string;

end package;

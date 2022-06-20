-- The check package provides the primary checking functionality.
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
use work.string_ops.all;

package body check_pkg is

  function to_char (
    constant bit : std_logic)
    return character is
    constant chars : string(1 to 9) := "UX01ZWLH-";
  begin
    return chars(std_logic'pos(bit) + 1);
  end function to_char;

  function to_string (
    constant data : std_logic)
    return string is
    variable ret_val : string(1 to 1);
  begin
    ret_val(1) := to_char(data);
    return ret_val;
  end function to_string;

  function to_string (
    constant data : boolean)
    return string is
  begin
    if data then
      return "true";
    else
      return "false";
    end if;
  end function to_string;

  function to_string (
    constant data : integer)
    return string is
  begin
    return integer'image(data);
  end function to_string;

  function to_string (
    constant data : string)
    return string is
  begin
    return data;
  end function to_string;

  function to_string (
    constant data : time)
    return string is
  begin
    return time'image(data);
  end function to_string;

  function max (
    constant value_1 : integer;
    constant value_2 : integer)
    return integer is
  begin
    if value_1 > value_2 then
      return value_1;
    else
      return value_2;
    end if;
  end max;

end package body check_pkg;

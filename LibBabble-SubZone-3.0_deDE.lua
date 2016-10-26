--[[
$Id$
Name: LibBabble-SubZone-3.0
Revision: $Rev$
Maintainers: arith, dynaletik
Last updated by: $Author$
Website: http://www.wowace.com/addons/libbabble-subzone-3-0/
Dependencies: None
License: MIT
]]

local _, private = ...
local lib = private["LibBabble-SubZone-3.0-LoadingLib"]
if not lib or GetLocale() ~= "deDE" then return end
lib:SetCurrentTranslations 
--@do-not-package@
{ }
--@end-do-not-package@
--@localization(locale="deDE", format="lua_table")@

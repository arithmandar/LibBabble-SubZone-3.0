--[[
$Id$
Name: LibBabble-SubZone-3.0
Revision: $Rev$
Maintainers: arith
Last updated by: $Author$
Website: http://www.wowace.com/addons/libbabble-subzone-3-0/
Dependencies: None
License: MIT
]]

local MAJOR_VERSION = "LibBabble-SubZone-3.0"
local MINOR_VERSION = 90000 + tonumber(("$Rev$"):match("%d+"))

if not LibStub then error(MAJOR_VERSION .. " requires LibStub.") end
local _, private = ...
local lib = LibStub("LibBabble-3.0"):New(MAJOR_VERSION, MINOR_VERSION)
if not lib then return end

-- Notes: Do not manually edit the translation here, as it may be overwritten by WoWAce localization automation tool
-- To revise translation, please visit: http://www.wowace.com/addons/libbabble-subzone-3-0/localization/

private["LibBabble-SubZone-3.0-LoadingLib"] = lib

lib:SetBaseTranslations 
--@localization(locale="enUS", format="lua_table")@

if GetLocale() == "enUS" then
	lib:SetCurrentTranslations(true)
end


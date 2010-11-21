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
local lib = LibStub("LibBabble-3.0"):New(MAJOR_VERSION, MINOR_VERSION)
if not lib then return end

local GAME_LOCALE = GetLocale()

-- Notes: Do not manually edit the translation here, as it may be overwritten by WoWAce localization automation tool
-- To revise translation, please visit: http://www.wowace.com/addons/libbabble-subzone-3-0/localization/

lib:SetBaseTranslations 
--@localization(locale="enUS", format="lua_table")@

if GAME_LOCALE == "enUS" then
	lib:SetCurrentTranslations(true)

elseif GAME_LOCALE == "frFR" then
	lib:SetCurrentTranslations 
--@localization(locale="frFR", format="lua_table")@

elseif GAME_LOCALE == "deDE" then
	lib:SetCurrentTranslations 
--@localization(locale="deDE", format="lua_table")@

elseif GAME_LOCALE == "koKR" then
	lib:SetCurrentTranslations 
--@localization(locale="koKR", format="lua_table")@

elseif GAME_LOCALE == "esMX" then
	lib:SetCurrentTranslations 
--@localization(locale="esMX", format="lua_table")@

elseif GAME_LOCALE == "esES" then
	lib:SetCurrentTranslations 
--@localization(locale="esES", format="lua_table")@

elseif GAME_LOCALE == "ruRU" then
	lib:SetCurrentTranslations 
--@localization(locale="ruRU", format="lua_table")@

elseif GAME_LOCALE == "zhCN" then
	lib:SetCurrentTranslations 
--@localization(locale="zhCN", format="lua_table")@

elseif GAME_LOCALE == "zhTW" then
	lib:SetCurrentTranslations 
--@localization(locale="zhTW", format="lua_table")@

else
	error(("%s: Locale %q not supported"):format(MAJOR_VERSION, GAME_LOCALE))
end

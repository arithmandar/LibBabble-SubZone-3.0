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

lib:SetBaseTranslations {

}


if GAME_LOCALE == "enUS" then
	lib:SetCurrentTranslations(true)
elseif GAME_LOCALE == "deDE" then
	lib:SetCurrentTranslations {
}
elseif GAME_LOCALE == "frFR" then
	lib:SetCurrentTranslations {
}
elseif GAME_LOCALE == "koKR" then
	lib:SetCurrentTranslations {
}
elseif GAME_LOCALE == "esES" then
	lib:SetCurrentTranslations {
}
elseif GAME_LOCALE == "esMX" then
	lib:SetCurrentTranslations {
}
elseif GAME_LOCALE == "ruRU" then
	lib:SetCurrentTranslations {
}
elseif GAME_LOCALE == "zhCN" then
	lib:SetCurrentTranslations {
}
elseif GAME_LOCALE == "zhTW" then
	lib:SetCurrentTranslations {
}

else
	error(("%s: Locale %q not supported"):format(MAJOR_VERSION, GAME_LOCALE))
end

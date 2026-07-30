-- Autotracking Archipelago pour Yo-kai Watch 2 (généré une fois, stable).
-- synchronise le compteur logique « rang » ET la lettre affichée (E..S)
local function setRang(n)
    local o = Tracker:FindObjectForCode("rang")
    if o then o.AcquiredCount = n end
    local d = Tracker:FindObjectForCode("rang_e")
    if d then d.CurrentStage = n end
end

local function resetAll()
    setRang(0)
    local chap = Tracker:FindObjectForCode("chapitre")
    if chap then chap.AcquiredCount = 0 end
    for _, spec in pairs(AP_ITEMS) do
        if spec.action == "toggle" then
            local o = Tracker:FindObjectForCode(spec.code)
            if o then o.Active = false end
        end
    end
    for _, path in pairs(AP_LOCATIONS) do
        local s = Tracker:FindObjectForCode(path)
        if s then
            s.AvailableChestCount = s.ChestCount
            -- surlignage de hint remis à zéro (il sera reposé par onHints)
            if Highlight and s.Highlight ~= nil then
                s.Highlight = Highlight.None
            end
        end
    end
end

local function setStat(code, n)
    local o = Tracker:FindObjectForCode(code)
    if o then
        o:SetOverlay(tostring(n))
        o:SetOverlayFontSize(26)
        o:SetOverlayAlign("center")
    end
end

-- sections ABSENTES de la seed (options YAML off) : exclues des comptes
local ABSENT = {}

local function updateStats()
    local checked, accessible, remaining = 0, 0, 0
    local groups = {
        ["@Chapters/"] = {done = 0, total = 0, code = "stat_chapitres"},
        ["@Yo-criminals/"] = {done = 0, total = 0, code = "stat_criminels"},
    }
    for _, p in ipairs(AP_ALL_SECTIONS) do
        local s = Tracker:FindObjectForCode(p)
        if s and not ABSENT[p] then
            local done = s.ChestCount - s.AvailableChestCount
            checked = checked + done
            remaining = remaining + s.AvailableChestCount
            if s.AvailableChestCount > 0
               and s.AccessibilityLevel >= AccessibilityLevel.Normal then
                accessible = accessible + s.AvailableChestCount
            end
            for prefix, g in pairs(groups) do
                if p:sub(1, #prefix) == prefix then
                    g.done = g.done + done
                    g.total = g.total + s.ChestCount
                end
            end
        end
    end
    setStat("stat_checked", checked)
    setStat("stat_accessible", accessible)
    setStat("stat_remaining", remaining)
    for _, g in pairs(groups) do
        local o = Tracker:FindObjectForCode(g.code)
        if o then
            o:SetOverlay(g.done .. "/" .. g.total)
            o:SetOverlayFontSize(34)
            o:SetOverlayAlign("center")
        end
    end
end

local function markLocation(id)
    local path = AP_LOCATIONS[id]
    if path then
        local s = Tracker:FindObjectForCode(path)
        if s then s.AvailableChestCount = 0 end
    end
    local chapN = AP_CHAPTER_LOCATIONS[id]
    if chapN then
        local chap = Tracker:FindObjectForCode("chapitre")
        if chap and chap.AcquiredCount < chapN then
            chap.AcquiredCount = chapN
        end
    end
end

-- ---------------------------------------------------------------------------
-- HINTS : un check dont l'item a été « hint » par quelqu'un est SURLIGNÉ
-- (demande Doteos 2026-07-27). Le serveur AP publie les hints du monde du joueur
-- dans la clé de data storage « _read_hints_<team>_<slot> ». On s'y abonne
-- (SetNotify) + on la lit une fois (Get) à la connexion, et on traduit le statut
-- du hint en LocationSection.Highlight (supporté depuis PopTracker 0.32).
-- ⚠️ Ces fonctions DOIVENT être définies AVANT les handlers qui les utilisent
-- (une closure Lua ne voit pas un `local` déclaré plus bas).
-- ---------------------------------------------------------------------------
local HINT_STATUS_TO_HIGHLIGHT = {}
if Highlight then
    HINT_STATUS_TO_HIGHLIGHT = {
        [0]  = Highlight.Unspecified,   -- non spécifié
        [10] = Highlight.NoPriority,    -- sans priorité
        [20] = Highlight.Avoid,         -- à éviter
        [30] = Highlight.Priority,      -- prioritaire
        [40] = Highlight.None,          -- trouvé -> plus de surlignage
    }
end

local function hintsKey()
    if Archipelago.TeamNumber == nil or Archipelago.PlayerNumber == nil
            or Archipelago.TeamNumber < 0 or Archipelago.PlayerNumber < 0 then
        return nil
    end
    return string.format("_read_hints_%s_%s",
                         Archipelago.TeamNumber, Archipelago.PlayerNumber)
end

local function onHints(hints)
    if not Highlight or type(hints) ~= "table" then return end
    local me = Archipelago.PlayerNumber
    for _, hint in ipairs(hints) do
        -- on ne surligne que les hints portant sur NOTRE monde
        if hint.finding_player == me then
            local hl = hint.status and HINT_STATUS_TO_HIGHLIGHT[hint.status]
            if hl == nil then                 -- serveur AP sans hint.status
                if hint.found == true then hl = Highlight.None
                elseif hint.found == false then hl = Highlight.Unspecified end
            end
            local path = AP_LOCATIONS[hint.location]
            if hl ~= nil and path then
                local s = Tracker:FindObjectForCode(path)
                if s and s.Highlight ~= nil then s.Highlight = hl end
            end
        end
    end
end

local function onDataStorage(key, value)
    if key == hintsKey() then onHints(value) end
end

Archipelago:AddClearHandler("ykw2_clear", function(slot_data)
    Tracker.BulkUpdate = true
    local ok, err = pcall(function()
        resetAll()
        -- checks ABSENTS de la seed (options désactivées côté YAML) :
        -- neutralisés pour ne pas fausser Accessible/Remaining.
        local valid = {}
        if Archipelago.MissingLocations then
            for _, id in ipairs(Archipelago.MissingLocations) do
                valid[id] = true
            end
        end
        if Archipelago.CheckedLocations then
            for _, id in ipairs(Archipelago.CheckedLocations) do
                valid[id] = true
            end
        end
        ABSENT = {}
        if next(valid) ~= nil then
            for id, path in pairs(AP_LOCATIONS) do
                if not valid[id] then
                    ABSENT[path] = true
                    local s = Tracker:FindObjectForCode(path)
                    if s then s.AvailableChestCount = 0 end
                end
            end
        end
        if Archipelago.CheckedLocations then
            for _, id in ipairs(Archipelago.CheckedLocations) do
                markLocation(id)
            end
        end
    end)
    Tracker.BulkUpdate = false
    updateStats()
    -- HINTS : s'abonner à la clé de data storage du slot + la lire une fois
    -- (les hints déjà émis avant la connexion sont ainsi récupérés).
    local hk = hintsKey()
    if hk then
        Archipelago:SetNotify({hk})
        Archipelago:Get({hk})
    end
end)

-- recompte à chaque changement de section (auto OU clic manuel)
ScriptHost:AddOnLocationSectionChangedHandler("ykw2_stats", function(_)
    updateStats()
end)

-- affichage initial (avant toute connexion AP)
updateStats()

Archipelago:AddItemHandler("ykw2_item", function(index, item_id, item_name)
    local spec = AP_ITEMS[item_id]
    if not spec then return end
    if spec.action == "toggle" then
        local o = Tracker:FindObjectForCode(spec.code)
        if o then o.Active = true end
    elseif spec.action == "rang_inc" then
        local o = Tracker:FindObjectForCode("rang")
        if o then setRang(o.AcquiredCount + 1) end
    elseif spec.action == "rang_set" then
        local o = Tracker:FindObjectForCode("rang")
        if o and o.AcquiredCount < spec.n then setRang(spec.n) end
    elseif spec.action == "chapitre_inc" then
        local o = Tracker:FindObjectForCode("chapitre")
        if o then o.AcquiredCount = o.AcquiredCount + 1 end
    end
end)

Archipelago:AddLocationHandler("ykw2_loc", function(location_id, name)
    markLocation(location_id)
end)

Archipelago:AddRetrievedHandler("ykw2_hints_get", onDataStorage)
Archipelago:AddSetReplyHandler("ykw2_hints_set", onDataStorage)

local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrTasks = import 'LrTasks'
local LrProgressScope = import 'LrProgressScope'

-- Standard color labels and non-species custom tags to ignore
local EXCLUDED_LABELS = {
    ["Red"] = true,
    ["Yellow"] = true,
    ["Green"] = true,
    ["Blue"] = true,
    ["Purple"] = true,
    ["People"] = true,
    ["Wildlife"] = true,
    ["Ice"] = true,
    ["Landscape"] = true,
    ["Plant"] = true,
    ["Lichen"] = true,
    ["Pet"] = true,
    ["Wedding"] = true,
}

LrTasks.startAsyncTask(function()
    local catalog = LrApplication.activeCatalog()
    local selectedPhotos = catalog:getTargetPhotos()
    
    if #selectedPhotos == 0 then
        LrDialogs.showError("No photos selected. Please select one or more photos to process.")
        return
    end

    -- 1. Find the eBird taxonomy root keyword
    -- ID 25689457 is 'eBird taxonomy v2024' (or we can look it up by name to be robust)
    local birdRoot = catalog:getKeywordsByLocalId({25689457})[1]
    
    if not birdRoot then
        -- Fallback: find by traversing top level keywords
        local rootKeywords = catalog:getKeywords()
        for _, kw in ipairs(rootKeywords) do
            if kw:getName() == "eBird taxonomy v2024" or kw:getName() == "eBird taxonomy v2025" then
                birdRoot = kw
                break
            end
        end
    end
    
    if not birdRoot then
        LrDialogs.showError("Could not find the 'eBird taxonomy v2024' or 'eBird taxonomy v2025' root keyword in the catalog.")
        return
    end

    -- 2. Build the species keyword lookup map recursively
    local speciesMap = {}
    local function buildMap(keyword)
        local name = keyword:getName()
        speciesMap[name:lower()] = keyword
        
        local children = keyword:getChildren()
        for _, child in ipairs(children) do
            buildMap(child)
        end
    end
    
    buildMap(birdRoot)

    -- 3. Process selected photos
    local progress = LrProgressScope({
        title = "Auto-Tagging Species...",
        caption = "Scanning photos...",
        canCancel = true
    })
    
    local taggedCount = 0
    local skippedCount = 0
    
    catalog:withWriteAccessDo("Auto-Tag Species from Color Labels", function(context)
        for i, photo in ipairs(selectedPhotos) do
            if progress:isCanceled() then break end
            
            progress:setPortionComplete(i, #selectedPhotos)
            
            local colorLabel = photo:getFormattedMetadata('label')
            if colorLabel and colorLabel ~= "" and not EXCLUDED_LABELS[colorLabel] then
                local targetKeyword = speciesMap[colorLabel:lower()]
                if targetKeyword then
                    -- Check if photo already has this keyword
                    local hasKeyword = false
                    local photoKeywords = photo:getRawMetadata('keywords')
                    for _, pk in ipairs(photoKeywords) do
                        if pk == targetKeyword then
                            hasKeyword = true
                            break
                        end
                    end
                    
                    if not hasKeyword then
                        photo:addKeyword(targetKeyword)
                        taggedCount = taggedCount + 1
                        progress:setCaption("Tagged: " .. colorLabel .. " (" .. taggedCount .. ")")
                    else
                        skippedCount = skippedCount + 1
                    end
                else
                    skippedCount = skippedCount + 1
                end
            else
                skippedCount = skippedCount + 1
            end
        end
    end)
    
    progress:done()
    
    LrDialogs.message(
        "Auto-Tagging Complete!", 
        string.format("Processed %d photos:\n• Automatically tagged: %d\n• Skipped (already tagged or invalid): %d", 
            #selectedPhotos, taggedCount, skippedCount
        ), 
        "info"
    )
end)

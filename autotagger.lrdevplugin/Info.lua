return {
    LrSdkVersion = 5.0,
    LrSdkMinimumVersion = 1.3,

    LrToolkitIdentifier = 'com.birdwalker.autotagger',
    LrPluginName = 'Auto-Tag Species from Color Labels',
    LrPluginInfoUrl = 'https://www.birdwalker.com',

    LrEnabled = true,

    LrLibraryMenuItems = {
        {
            title = 'Auto-Tag Selected Photos from Color Labels',
            file = 'AutoTagAction.lua',
        },
    },

    Version = { major=1, minor=0, revision=0 },
}

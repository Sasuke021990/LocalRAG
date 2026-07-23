module.exports = function (api) {
  api.cache(true)
  return {
    presets: ['babel-preset-expo'],
    // Reanimated 4 (SDK 54) moved its Babel plugin out to react-native-worklets.
    // It must stay last in the plugins list.
    plugins: ['react-native-worklets/plugin'],
  }
}

#!/bin/bash
# A script to build, prune, and package a Toga app for a specific platform.

set -e # Exit immediately if a command fails

PLATFORM=$1
APP_NAME="beanquick"

if [ -z "$PLATFORM" ]; then
    echo "Usage: ./build_and_prune.sh <platform>"
    echo "Example: ./build_and_prune.sh macOS"
    exit 1
fi

echo "--- Building for $PLATFORM ---"
briefcase create $PLATFORM
briefcase build $PLATFORM

# Determine the path to app_packages
case $PLATFORM in
  macOS)
    PACKAGES_PATH="build/$APP_NAME/macos/app/$APP_NAME.app/Contents/Resources/app_packages"
    ;;
  "macOS Xcode")
    PACKAGES_PATH="build/$APP_NAME/macos/xcode/$APP_NAME/app_packages"
    ;;
  windows)
    PACKAGES_PATH="windows/app/$APP_NAME/app_packages" # TODO
    ;;
  linux)
    PACKAGES_PATH="linux/appimage/$APP_NAME/app_packages" # TODO
    ;;
  android)
    PACKAGES_PATH="android/gradle/$APP_NAME/app/src/main/python/app_packages" # TODO
    ;;
  iOS)
    PACKAGES_PATH="iOS/Xcode/$APP_NAME/app_packages" # TODO
    ;;
  *)
    echo "Unknown platform: $PLATFORM"
    exit 1
    ;;
esac

echo "--- Pruning Babel locales in $PACKAGES_PATH ---"
python prune_briefcase_babel.py "$PACKAGES_PATH"

# echo "--- Packaging for $PLATFORM ---"
# briefcase package $PLATFORM

echo "--- Done! ---"
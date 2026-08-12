#!/usr/bin/env bash
# uninstall.sh - Standalone uninstaller script for gif2ascii

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

PURGE=false
YES=false

for arg in "$@"; do
    case $arg in
        --purge)
            PURGE=true
            shift
            ;;
        -y|--yes)
            YES=true
            shift
            ;;
        -h|--help)
            echo "Usage: ./uninstall.sh [--purge] [-y|--yes]"
            echo ""
            echo "Options:"
            echo "  --purge    Remove user config (~/.config/gif2ascii) and library data (~/.local/share/gif2ascii)"
            echo "  -y, --yes  Automatic yes to prompts"
            exit 0
            ;;
    esac
done

echo -e "${YELLOW}=== gif2ascii Uninstaller ===${NC}"

if [ "$YES" = false ]; then
    if [ "$PURGE" = false ]; then
        read -p "Do you also want to remove user data (~/.config/gif2ascii & ~/.local/share/gif2ascii)? [y/N]: " purge_ans
        case "$purge_ans" in
            [yY][eE][sS]|[yY])
                PURGE=true
                ;;
            *)
                PURGE=false
                ;;
        esac
    fi

    read -p "Are you sure you want to uninstall gif2ascii? [y/N]: " confirm_ans
    case "$confirm_ans" in
        [yY][eE][sS]|[yY])
            ;;
        *)
            echo -e "${RED}Uninstallation cancelled.${NC}"
            exit 0
            ;;
    esac
fi

# Remove user configuration and library data if requested
if [ "$PURGE" = true ]; then
    echo -e "${CYAN}Removing user data directories...${NC}"
    rm -rf "$HOME/.config/gif2ascii" "$HOME/.local/share/gif2ascii"
    echo -e "${GREEN}Removed ~/.config/gif2ascii and ~/.local/share/gif2ascii${NC}"
fi

# Uninstall python package
echo -e "${CYAN}Uninstalling python package...${NC}"
if command -v python3 &>/dev/null; then
    python3 -m pip uninstall -y gif2ascii || true
elif command -v pip &>/dev/null; then
    pip uninstall -y gif2ascii || true
fi

# Clean leftover local binaries if present
rm -f "$HOME/.local/bin/gif2ascii" "$HOME/.local/bin/gif2ascii-player"

echo -e "${GREEN}gif2ascii has been successfully uninstalled!${NC}"

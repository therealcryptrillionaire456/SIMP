#!/bin/bash
# Script to permanently fix goose PATH issue for all shells

echo "=== Fixing Goose PATH Issue ==="
echo "Goose is installed at: /Users/kaseymarcelle/.local/bin/goose"

# Check current PATH
echo -e "\nCurrent PATH:"
echo $PATH | tr ':' '\n' | grep -n ".local/bin" || echo "  .local/bin NOT in PATH"

# Fix for bash
echo -e "\n=== Fixing for bash ==="
if [ -f ~/.bashrc ]; then
    if grep -q "\.local/bin" ~/.bashrc; then
        echo "  .local/bin already in ~/.bashrc"
    else
        echo 'export PATH="/Users/kaseymarcelle/.local/bin:$PATH"' >> ~/.bashrc
        echo "  Added .local/bin to ~/.bashrc"
    fi
else
    echo 'export PATH="/Users/kaseymarcelle/.local/bin:$PATH"' > ~/.bashrc
    echo "  Created ~/.bashrc with .local/bin in PATH"
fi

# Fix for zsh
echo -e "\n=== Fixing for zsh ==="
if [ -f ~/.zshrc ]; then
    if grep -q "\.local/bin" ~/.zshrc; then
        echo "  .local/bin already in ~/.zshrc"
    else
        echo 'export PATH="/Users/kaseymarcelle/.local/bin:$PATH"' >> ~/.zshrc
        echo "  Added .local/bin to ~/.zshrc"
    fi
else
    echo 'export PATH="/Users/kaseymarcelle/.local/bin:$PATH"' > ~/.zshrc
    echo "  Created ~/.zshrc with .local/bin in PATH"
fi

echo -e "\n=== Summary ==="
echo "1. Updated ~/.bashrc for bash shells"
echo "2. Updated ~/.zshrc for zsh shells"
echo "3. To apply changes:"
echo "   - For bash: source ~/.bashrc"
echo "   - For zsh: source ~/.zshrc"
echo "4. Or open a new terminal window"

echo -e "\n=== Quick Test ==="
echo "Testing goose access:"
/Users/kaseymarcelle/.local/bin/goose --version && echo "✓ Full path works"
which goose && echo "✓ PATH lookup works" || echo "✗ PATH lookup fails (reload shell)"
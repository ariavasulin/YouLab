#!/bin/bash

# create_worktree.sh - Create a new worktree for development work
# Usage: ./create_worktree.sh [--no-thoughts] [worktree_name] [base_branch]
# If no name provided, generates a unique human-readable one
# If no base branch provided, uses current branch

set -e  # Exit on any error


# Function to generate a unique worktree name
generate_unique_name() {
    local adjectives=("swift" "bright" "clever" "smooth" "quick" "clean" "sharp" "neat" "cool" "fast")
    local nouns=("fix" "task" "work" "dev" "patch" "branch" "code" "build" "test" "run")

    local adj=${adjectives[$RANDOM % ${#adjectives[@]}]}
    local noun=${nouns[$RANDOM % ${#nouns[@]}]}
    local timestamp=$(date +%H%M)

    echo "${adj}_${noun}_${timestamp}"
}

# Parse flags
INIT_THOUGHTS=true
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-thoughts)
            INIT_THOUGHTS=false
            shift
            ;;
        *)
            break
            ;;
    esac
done

# Get worktree name from parameter or generate one
WORKTREE_NAME=${1:-$(generate_unique_name)}

# Get base branch from second parameter or use current branch
BASE_BRANCH=${2:-$(git branch --show-current)}

# Get repository root
REPO_ROOT=$(git rev-parse --show-toplevel)

if [ ! -z "$HUMANLAYER_WORKTREE_OVERRIDE_BASE" ]; then
    WORKTREES_BASE="${HUMANLAYER_WORKTREE_OVERRIDE_BASE}"
else
    WORKTREES_BASE="${REPO_ROOT}/.trees"
fi

WORKTREE_PATH="${WORKTREES_BASE}/${WORKTREE_NAME}"

echo "🌳 Creating worktree: ${WORKTREE_NAME}"
echo "📁 Location: ${WORKTREE_PATH}"

# Create worktrees directory if it doesn't exist
if [ ! -d "$WORKTREES_BASE" ]; then
    echo "Creating worktrees directory: $WORKTREES_BASE"
    mkdir -p "$WORKTREES_BASE"
fi

# Check if worktree already exists
if [ -d "$WORKTREE_PATH" ]; then
    echo "❌ Error: Worktree directory already exists: $WORKTREE_PATH"
    exit 1
fi

# Display base branch info
echo "🔀 Creating from branch: ${BASE_BRANCH}"

# Create worktree (creates branch if it doesn't exist)
if git show-ref --verify --quiet "refs/heads/${WORKTREE_NAME}"; then
    echo "📋 Using existing branch: ${WORKTREE_NAME}"
    git worktree add "$WORKTREE_PATH" "$WORKTREE_NAME"
else
    echo "🆕 Creating new branch: ${WORKTREE_NAME}"
    git worktree add -b "$WORKTREE_NAME" "$WORKTREE_PATH" "$BASE_BRANCH"
fi

# Copy .claude directory if it exists
if [ -d ".claude" ]; then
    echo "📋 Copying .claude directory..."
    cp -r .claude "$WORKTREE_PATH/"
fi

# Change to worktree directory
cd "$WORKTREE_PATH"

echo "🔧 Setting up worktree dependencies..."
if ! make setup; then
    echo "❌ Setup failed. Cleaning up worktree..."
    cd - > /dev/null
    git worktree remove --force "$WORKTREE_PATH"
    git branch -D "$WORKTREE_NAME" 2>/dev/null || true
    echo "❌ Not allowed to create worktree from a branch that isn't passing setup."
    exit 1
fi

echo "Verifying worktree with full checks..."
temp_output=$(mktemp)
if make verify > "$temp_output" 2>&1; then
    rm "$temp_output"
    echo "All checks pass!"
else
    cat "$temp_output"
    rm "$temp_output"
    echo "Verification failed. Cleaning up worktree..."
    cd - > /dev/null
    git worktree remove --force "$WORKTREE_PATH"
    git branch -D "$WORKTREE_NAME" 2>/dev/null || true
    echo "Cannot create worktree from a branch that fails verification."
    exit 1
fi

# Initialize thoughts (non-interactive mode with hardcoded directory)
if [ "$INIT_THOUGHTS" = true ]; then
    echo "🧠 Initializing thoughts..."
    cd "$WORKTREE_PATH"
    if humanlayer thoughts init --directory YouLab > /dev/null 2>&1; then
        echo "✅ Thoughts initialized!"
        # Run sync to create searchable directory
        if humanlayer thoughts sync > /dev/null 2>&1; then
            echo "✅ Thoughts searchable index created!"
        else
            echo "⚠️  Could not create searchable index. Run 'humanlayer thoughts sync' manually."
        fi
    else
        echo "⚠️  Could not initialize thoughts automatically. Run 'humanlayer thoughts init' manually."
    fi
fi

# Return to original directory
cd - > /dev/null

echo "✅ Worktree created successfully!"
echo "📁 Path: ${WORKTREE_PATH}"
echo "🔀 Branch: ${WORKTREE_NAME}"
echo ""
echo "To work in this worktree:"
echo "  cd ${WORKTREE_PATH}"
echo ""
echo "To remove this worktree later:"
echo "  git worktree remove ${WORKTREE_PATH}"
echo "  git branch -D ${WORKTREE_NAME}"

-- Launch Claude Desktop via Option+Option quick add
-- Assumes clipboard already has the prompt (set via pbcopy)
-- Usage: osascript hack/launch-claude-research.applescript
-- Or run the compiled ClaudeResearch.app

on run
    tell application "System Events"
        -- Option+Option (double-tap) to open Claude quick add
        key code 58 -- Left Option
        delay 0.1
        key code 58 -- Left Option again
        delay 0.3 -- Wait for quick add to open

        -- Paste the prompt
        keystroke "v" using command down
        delay 0.1

        -- Submit
        keystroke return
    end tell

    return "Research launched in Claude Desktop"
end run

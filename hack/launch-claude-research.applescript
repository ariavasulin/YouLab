-- Launch Claude Desktop with a research prompt
-- Usage: osascript hack/launch-claude-research.applescript "Your research query here"

on run argv
    if (count of argv) < 1 then
        return "Error: No prompt provided"
    end if

    set thePrompt to item 1 of argv

    -- Copy prompt to clipboard
    set the clipboard to thePrompt

    -- Activate Claude and create new conversation
    tell application "Claude" to activate
    delay 0.5

    tell application "System Events"
        tell process "Claude"
            -- Cmd+N for new conversation
            keystroke "n" using command down
            delay 0.3
            -- Paste the prompt
            keystroke "v" using command down
            delay 0.1
            -- Submit
            keystroke return
        end tell
    end tell

    return "Research launched in Claude Desktop"
end run

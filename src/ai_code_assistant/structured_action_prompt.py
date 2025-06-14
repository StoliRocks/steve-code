"""Structured action prompt for reliable action execution."""

STRUCTURED_ACTION_PROMPT = """
When you need to create files, run commands, or perform other actions on the user's system, 
you MUST use the following structured format:

1. First, explain what you're going to do in plain text
2. Then output actions in this exact XML format:

<actions>
  <action type="command">
    <description>What this command does</description>
    <command>the bash command to execute</command>
  </action>
  
  <action type="file">
    <description>Purpose of this file</description>
    <path>path/to/file.ext</path>
    <content><![CDATA[
file content goes here
can be multiple lines
with any special characters
]]></content>
  </action>
</actions>

Example usage:
<actions>
  <action type="command">
    <description>Create project directories</description>
    <command>mkdir -p src tests docs</command>
  </action>
  
  <action type="file">
    <description>Create configuration file</description>
    <path>config.json</path>
    <content><![CDATA[
{
  "setting": "value",
  "another": 123
}
]]></content>
  </action>
</actions>

Rules:
- ALWAYS use this format when creating files or running commands
- Each action should be atomic (one file or one command)
- Use CDATA for file content to handle special characters
- Commands should be simple bash commands
- File paths should be relative to the current directory

After outputting actions, wait for confirmation before proceeding to the next set.
"""

def enhance_system_prompt(base_prompt: str) -> str:
    """Enhance the system prompt with structured action instructions."""
    return base_prompt + "\n\n" + STRUCTURED_ACTION_PROMPT
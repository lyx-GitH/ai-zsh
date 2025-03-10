from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import Completer, Completion, PathCompleter, ExecutableCompleter, WordCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
import os
import shlex
import subprocess
import pexpect


class ShellCompleter(Completer):
    """Completer that uses the system's shell completion"""
    def __init__(self, shell='bash'):
        self.shell = shell
        
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        
        # Handle 'ai' command completion separately
        if text.startswith('ai '):
            ai_suggestions = [
                'find large files', 'compress images', 'list processes',
                'check disk space', 'find duplicates', 'backup directory',
                'monitor resources', 'search for text', 'update system'
            ]
            
            ai_query = text[3:].strip()
            for suggestion in ai_suggestions:
                if suggestion.startswith(ai_query):
                    completion_text = suggestion[len(ai_query):]
                    if completion_text:
                        yield Completion(completion_text, start_position=0)
            return
        
        # For shell commands, use the system's completion
        try:
            if self.shell == 'bash':
                completions = self._get_bash_completions(text)
            elif self.shell == 'zsh':
                completions = self._get_zsh_completions(text)
            else:
                # Fallback to simple file completion
                completions = self._get_basic_completions(text)
                
            # Get the last word to determine what to replace
            last_word = text.split()[-1] if text.split() else ""
            
            for completion in completions:
                # Only yield the part after what's already typed
                if completion.startswith(last_word):
                    completion_text = completion[len(last_word):]
                    if completion_text:
                        yield Completion(completion_text, start_position=0)
        except Exception as e:
            # In case of errors, fall back to basic completion
            for completion in self._get_basic_completions(text):
                yield Completion(completion, start_position=0)
                
    def get_shell_completions(text):
        # Start a bash process
        child = pexpect.spawn('bash --norc')
        child.sendline(f'{text}\t\t')  # Send text with double tab
        child.expect('.*\r\n')  # Wait for response
        
        # Extract completions from the output
        output = child.before.decode('utf-8')
        child.close()
        
        # Parse the output to get completions
        # This requires additional parsing logic
    
        return completions
    
    def _get_bash_completions(self, text):
        """Get completions using bash's built-in completion mechanism"""
        # Create a command that uses bash completion
        cmd = f'compgen -A file -A command -A alias -A function -- "{text.split()[-1] if text.split() else ""}"'
        
        # Execute bash with our completion command
        result = subprocess.run(
            ['bash', '-c', cmd],
            capture_output=True,
            text=True
        )
        
        # Return all completions
        if result.stdout:
            return result.stdout.strip().split('\n')
        return []
    
    def _get_zsh_completions(self, text):
        """Get completions using zsh's completion mechanism"""
        # This is more complex - zsh's completion system is more advanced
        # This is a simplified version that provides basic completions
        cmd = f'print -l -- {shlex.quote(text.split()[-1] if text.split() else "")}*(N)'
        
        result = subprocess.run(
            ['zsh', '-c', cmd],
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            return result.stdout.strip().split('\n')
        return []
    
    def _get_basic_completions(self, text):
        """Fallback completion for files and directories"""
        # Get the last word
        words = text.split()
        if not words:
            return []
            
        last_word = words[-1]
        
        # Handle paths with ~
        if last_word.startswith('~'):
            last_word = os.path.expanduser(last_word)
        
        # Determine directory to look in
        if os.path.isdir(last_word):
            directory = last_word
            prefix = ""
        elif '/' in last_word:
            directory = os.path.dirname(last_word) or '.'
            prefix = os.path.basename(last_word)
        else:
            directory = '.'
            prefix = last_word
        
        try:
            files = os.listdir(directory)
            return [f for f in files if f.startswith(prefix)]
        except (FileNotFoundError, NotADirectoryError):
            return []

